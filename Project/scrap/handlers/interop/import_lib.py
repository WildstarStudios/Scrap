import os, re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import (
    register_library_alias, register_owned_creator,
    register_outparam_creator, register_variable_library,
    register_imported_function
)
from scrap.core.cheader_parser import parse_cheader as parse_cheader_pure
from scrap.core.debug import DEBUG
from scrap.core.utils import _OUTPARAM_CREATORS

class ImportLibHandler(StatementHandler):
    keywords = ['import lib ']
    _parsed_data = {}

    def can_handle(self, line):
        return line.strip().startswith('import lib ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^import lib\s+"([^"]+)"(?:\s+as\s+([a-zA-Z_]\w*))?$', line)
        if not m:
            raise SyntaxError('Expected: import lib "path" [as Alias]')
        header = m.group(1)
        alias = m.group(2)

        # ----- Detect C vs C++ header -----
        is_cpp = header.endswith(('.hpp', '.hxx', '.h++', '.hh', '.HPP', '.H'))
        if alias is None:
            base = os.path.splitext(os.path.basename(header))[0]
            alias = re.sub(r'[^a-zA-Z0-9_]', '_', base)
            alias = re.sub(r'^\d+', '', alias) or 'clib'

        if is_cpp:
            # C++ header → just register as a namespace alias
            if DEBUG:
                print(f"[DEBUG import_lib] C++ header detected: '{header}' -> alias '{alias}' (namespace mode)")
            # We'll attempt to guess the namespace from the alias (capitalize first letter)
            # But user can also specify the namespace explicitly by adding a special syntax,
            # for simplicity we assume alias IS the namespace name (e.g., "ImGui")
            cpp_ns = alias  # user can write "import lib "imgui.h" as ImGui" → namespace ImGui
            # Wildcard function map: any method name maps to (cpp_ns::method, False)
            func_map = {}
            # We don't have a prefix, so all suffixed calls just use the exact method name
            # We'll set up a special key '*' to indicate wildcard
            register_library_alias(alias, '', {})   # empty map, but the alias is registered
            # We'll store the namespace for direct use
            self._parsed_data[header] = (alias, {}, [], '')
            if DEBUG:
                print(f"[DEBUG import_lib] registered C++ alias '{alias}' as namespace '{cpp_ns}'")
            return ('IMPORT_CPP', alias, cpp_ns, header), start_index + 1

        # ----- Original C library handling (unchanged) -----
        functions, ownership = parse_cheader_pure(header)

        # ---------- robust prefix detection ----------
        names = [f['name'] for f in functions]
        if names:
            prefix = names[0]
            for n in names[1:]:
                while not n.startswith(prefix):
                    prefix = prefix[:-1]
                    if not prefix:
                        break
                if not prefix:
                    break
            if prefix and len(names[0]) > len(prefix) and names[0][len(prefix)] == '_':
                prefix = prefix + '_'
        else:
            prefix = ''
        if DEBUG:
            print(f"[DEBUG import_lib] final prefix = '{prefix}'")
        # -------------------------------------------------------

        # Register all imported functions for later auto‑fill
        for f in functions:
            register_imported_function(f['full_name'], f['param_types'])

        func_map = {}
        handle_type = None
        for info in ownership.values():
            if isinstance(info, tuple) and len(info) >= 2:
                handle_type = info[1]
                break

        for f in functions:
            full = f['name']
            suffix = full[len(prefix):] if full.startswith(prefix) else full
            if not suffix:
                continue
            takes_handle = False
            if handle_type and f['param_types']:
                first = f['param_types'][0].replace('const', '').replace('*', '').strip()
                if first == handle_type.strip():
                    takes_handle = True
            func_map[suffix] = (full, takes_handle)

        # ---------- ownership → smart‑pointer registration ----------
        for creator, info in ownership.items():
            if isinstance(info, tuple):
                destroyer, base_type, *rest = info
                is_outparam = bool(rest) and rest[0]
                if is_outparam:
                    register_outparam_creator(creator, base_type, destroyer, alias)
                    suffix = creator[len(prefix):] if creator.startswith(prefix) else creator
                    if suffix:
                        func_map[suffix] = (creator, False)
            else:
                destroyer = info
                creator_func = next((f for f in functions if f['name'] == creator), None)
                if creator_func and creator_func['is_pointer_return']:
                    wrapper = f'Unique{alias}{creator}'
                    register_owned_creator(creator, wrapper)

        register_library_alias(alias, prefix, func_map)
        self._parsed_data[header] = (alias, ownership, functions, prefix)

        if DEBUG:
            print(f"[DEBUG import_lib] alias={alias}, prefix='{prefix}'")
            print(f"[DEBUG import_lib] func_map sample: {dict(list(func_map.items())[:5])}")

        return ('IMPORT', alias, header), start_index + 1

    def generate(self, node, indent=''):
        return ''

    def required_headers(self, node=None):
        if node is None:
            return set()
        # For C++ headers, we just need to include the header (no extern "C")
        if len(node) == 4 and node[0] == 'IMPORT_CPP':
            return {f'"{node[3]}"'}
        # For C headers, include is placed inside extern "C" via generate_pre_main
        return set()

    def generate_pre_main(self, node):
        if len(node) == 4 and node[0] == 'IMPORT_CPP':
            # C++ header – already included via required_headers, so skip duplicate
            return ''
        # Original C logic (unchanged)
        alias, header = node[1], node[2]
        if header not in self._parsed_data:
            return ''
        _, ownership, functions, prefix = self._parsed_data[header]
        lines = []
        lines.append('extern "C" {')
        lines.append(f'#include "{header}"')
        lines.append('}')
        lines.append('#include <memory>')
        return '\n'.join(lines)
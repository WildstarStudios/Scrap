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

        functions, ownership = parse_cheader_pure(header)

        if alias is None:
            base = os.path.splitext(os.path.basename(header))[0]
            alias = re.sub(r'[^a-zA-Z0-9_]', '_', base)
            alias = re.sub(r'^\d+', '', alias) or 'clib'

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
        # We only need outparam creators (e.g., sqlite3_open) for automatic unique_ptr wrapping.
        # Normal owned creators (pointer‑return) are not used automatically, so we skip wrapper generation.
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
                # plain string destroyer -> normal owned creator, ignored for now
                pass

        register_library_alias(alias, prefix, func_map)
        self._parsed_data[header] = (alias, ownership, functions, prefix)

        if DEBUG:
            print(f"[DEBUG import_lib] alias={alias}, prefix='{prefix}'")
            print(f"[DEBUG import_lib] func_map sample: {dict(list(func_map.items())[:5])}")

        return ('IMPORT', alias, header), start_index + 1

    def generate(self, node, indent=''):
        return ''

    def required_headers(self, node=None):
        return set()

    def generate_pre_main(self, node):
        alias, header = node[1], node[2]
        if header not in self._parsed_data:
            return ''
        # We only need the extern "C" include; the unique_ptr is instantiated directly by var.py
        lines = []
        lines.append('extern "C" {')
        lines.append(f'#include "{header}"')
        lines.append('}')
        lines.append('#include <memory>')   # needed for std::unique_ptr
        return '\n'.join(lines)
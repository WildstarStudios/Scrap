import os
import shutil
import subprocess
import re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import register_alias, register_owned_creator

# -------------------------------------------------------------------
# Header parsing
# -------------------------------------------------------------------
def _get_compiler():
    for prog in ['g++', 'gcc']:
        path = shutil.which(prog)
        if path:
            return prog
    return None

def _parse_header(header_path):
    compiler = _get_compiler()
    if not compiler:
        return None, None
    if not os.path.isabs(header_path):
        header_path = os.path.abspath(header_path)
    cmd = [compiler, '-E', '-P', '-I.', header_path, '-o', '-']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None, None
    except FileNotFoundError:
        return None, None

    preprocessed = result.stdout
    functions = []
    namespaces = set()

    for line in preprocessed.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        line = re.sub(r'^\s*(IMGUI_API|extern|static|virtual|inline)\s+', '', line)
        m = re.match(r'^(.*?)\s+(\w+(::\w+)+)\s*\(([^)]*)\)\s*;', line)
        if m:
            ret = m.group(1).strip()
            full_name = m.group(2)
            params_str = m.group(4).strip()
            short_name = full_name.split('::')[-1]
            is_ptr = '*' in ret
            functions.append({
                'name': short_name,
                'full_name': full_name,
                'return_type': ret,
                'is_pointer_return': is_ptr,
                'params': [p.strip() for p in params_str.split(',')] if params_str else []
            })
            ns = full_name.split('::')[0]
            namespaces.add(ns)
            continue

        m = re.match(r'^(.*?)\s+(\w+)\s*\(([^)]*)\)\s*;', line)
        if m:
            ret = m.group(1).strip()
            name = m.group(2)
            params_str = m.group(3).strip()
            is_ptr = '*' in ret
            functions.append({
                'name': name,
                'full_name': name,
                'return_type': ret,
                'is_pointer_return': is_ptr,
                'params': [p.strip() for p in params_str.split(',')] if params_str else []
            })

    namespace_hint = namespaces.pop() if len(namespaces) == 1 else None
    return functions, namespace_hint

def _infer_ownership(functions):
    ownership = {}
    func_names = {f['name'] for f in functions}
    for f in functions:
        if f['is_pointer_return'] and f['name'].startswith('Create'):
            suffix = f['name'][6:]
            if f'Destroy{suffix}' in func_names:
                ownership[f['name']] = f'Destroy{suffix}'
    return ownership

# -------------------------------------------------------------------
# Known missing declarations (forward declarations to inject)
# -------------------------------------------------------------------
MISSING_DECLARATIONS = {
    "imgui_impl_win32": [
        'LRESULT ImGui_ImplWin32_WndProcHandler(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam);'
    ]
}

def _get_backend_key(header_path):
    base = os.path.basename(header_path)
    name = os.path.splitext(base)[0]
    return name

# -------------------------------------------------------------------
# Main handler
# -------------------------------------------------------------------
class ImportLibHandler(StatementHandler):
    keywords = ['import lib ']
    _wrapper_cache = {}
    _parsed_ownership = {}

    def can_handle(self, line):
        return line.strip().startswith('import lib ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^import lib\s+"([^"]+)"(?:\s+as\s+([a-zA-Z_]\w*))?$', line)
        if not m:
            raise SyntaxError('Expected: import lib "path" [as Alias]')
        header = m.group(1)
        alias = m.group(2)

        if alias is None:
            functions, ns_hint = _parse_header(header)
            if functions and ns_hint:
                alias = ns_hint

        if alias is not None:
            register_alias(alias, alias)
            if header not in self._parsed_ownership:
                if 'functions' not in locals():
                    functions, _ = _parse_header(header)
                if functions:
                    ownership = _infer_ownership(functions)
                    for create_func, destroy_func in ownership.items():
                        wrapper = f'Unique{alias}{create_func}'
                        register_owned_creator(create_func, wrapper)
                    self._parsed_ownership[header] = (alias, ownership, functions)
                else:
                    self._parsed_ownership[header] = (alias, {}, [])
        else:
            if header not in self._parsed_ownership:
                self._parsed_ownership[header] = (None, {}, [])

        return ('IMPORT', alias, header), start_index + 1

    def generate(self, node, indent=''):
        return ''

    def generate_pre_main(self, node):
        alias, header = node[1:]
        if header in self._wrapper_cache:
            return self._wrapper_cache[header]

        result_parts = []

        if alias is not None and header in self._parsed_ownership:
            alias2, ownership, functions = self._parsed_ownership[header]
            if ownership:
                result_parts.append('#include <memory>')
                result_parts.append(f'// Automatic smart wrappers for {alias}')
                for create_func, destroy_func in ownership.items():
                    creator_info = next((f for f in functions if f['name'] == create_func), None)
                    if creator_info is None:
                        continue
                    base_type = creator_info['return_type'].replace('*', '').strip()
                    wrapper = f'Unique{alias}{create_func}'
                    deleter_call = f'{alias}::{destroy_func}'
                    result_parts.append(
                        f'struct {wrapper}Deleter {{ void operator()({base_type}* p) {{ {deleter_call}(p); }} }};'
                    )
                    result_parts.append(
                        f'using {wrapper} = std::unique_ptr<{base_type}, {wrapper}Deleter>;'
                    )

        # Inject any missing declarations for this backend
        backend_key = _get_backend_key(header)
        if backend_key in MISSING_DECLARATIONS:
            for decl in MISSING_DECLARATIONS[backend_key]:
                result_parts.append(decl)

        result = '\n'.join(result_parts)
        if result:
            result += '\n'
        self._wrapper_cache[header] = result
        return result

    def required_headers(self, node=None):
        if node is None:
            return set()
        _, header = node[1:]
        return {f'"{header}"'}
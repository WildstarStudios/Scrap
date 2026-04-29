import re
import os
from . import StatementHandler, register_alias, register_c_alias, strip_comments

STD_HEADERS = {
    'iostream', 'string', 'vector', 'map', 'set', 'list', 'deque', 'array',
    'algorithm', 'numeric', 'memory', 'fstream', 'sstream', 'cmath', 'cstdlib',
    'cstdio', 'cstring', 'ctime', 'chrono', 'thread', 'mutex', 'atomic'
}

def _is_cpp_header(header_path):
    """Open the file and look for C++ keywords. Return True if C++."""
    try:
        with open(header_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(4096)
            # Strong C++ indicators
            if re.search(r'\b(namespace|template|class\s+\w+\s*[:{]|public\s*:|private\s*:|protected\s*:)\b', content):
                return True
            if re.search(r'extern\s*"C"', content):
                return False
    except FileNotFoundError:
        pass
    return False

class ImportHandler(StatementHandler):
    keywords = ['import lib ']

    def can_handle(self, line):
        return line.startswith('import lib ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^import lib\s+([^\s]+)(?:\s+as\s+([a-zA-Z_]\w*))?$', line)
        if not m:
            raise SyntaxError("Expected: import lib <path> [as <alias>]")
        raw_path = m.group(1)
        custom_alias = m.group(2)

        # Detect inclusion style and resolve path
        if raw_path.startswith('<') and raw_path.endswith('>'):
            header = raw_path[1:-1]
            use_angles = True
        elif raw_path.startswith('"') and raw_path.endswith('"'):
            header = raw_path[1:-1]
            use_angles = False
        else:
            if raw_path in STD_HEADERS:
                header = raw_path
                use_angles = True
            else:
                header = os.path.join('libs', raw_path).replace('\\', '/')
                use_angles = False

        kind = self._determine_header_kind(header, use_angles)

        if kind == 'cpp':
            if custom_alias:
                alias = custom_alias
            else:
                alias = os.path.basename(header)
                alias = re.sub(r'\.(hpp|h|hxx)$', '', alias)
            register_alias(alias, alias)
            return ('IMPORT_CPP', header, alias, use_angles), start_index + 1
        else:
            if custom_alias:
                alias = custom_alias
            else:
                alias = os.path.basename(header)
                alias = re.sub(r'\.(h|hpp)$', '', alias)
            register_c_alias(alias, alias)
            return ('IMPORT_C', header, use_angles), start_index + 1

    def _determine_header_kind(self, header, use_angles):
        if use_angles:
            if '.' not in header:
                return 'cpp'
            elif header.endswith('.h'):
                return 'c'
            else:
                return 'c'
        else:
            if os.path.exists(header):
                return 'cpp' if _is_cpp_header(header) else 'c'
            libs_path = os.path.join('libs', header)
            if os.path.exists(libs_path):
                return 'cpp' if _is_cpp_header(libs_path) else 'c'
            return 'cpp'  # fallback

    def generate(self, node, indent=''):
        return ''

    def generate_pre_main(self, node):
        kind = node[0]
        if kind == 'IMPORT_C':
            header, use_angles = node[1], node[2]
            if use_angles:
                return f'extern "C" {{\n#include <{header}>\n}}\n'
            else:
                return f'extern "C" {{\n#include "{header}"\n}}\n'
        return ''

    def required_headers(self, node=None):
        if node is None:
            return set()
        kind = node[0]
        if kind == 'IMPORT_CPP':
            header, use_angles = node[1], node[3]
            if use_angles:
                return {f'<{header}>'}
            else:
                return {f'"{header}"'}
        return set()
import re
import os
from . import StatementHandler, register_alias, is_c_header

# List of known C++ standard library headers (without .h)
STD_HEADERS = {
    'iostream', 'string', 'vector', 'map', 'set', 'list', 'deque', 'array',
    'algorithm', 'numeric', 'memory', 'fstream', 'sstream', 'cmath', 'cstdlib',
    'cstdio', 'cstring', 'ctime', 'chrono', 'thread', 'mutex', 'atomic'
}

class ImportHandler(StatementHandler):
    keywords = ['import lib ']

    def can_handle(self, line):
        return line.startswith('import lib ')

    def parse(self, lines, start_index):
        line = lines[start_index].strip()
        m = re.match(r'^import lib\s+([^\s]+)(?:\s+as\s+([a-zA-Z_]\w*))?$', line)
        if not m:
            raise SyntaxError("Expected: import lib <path> [as <alias>]")
        raw_path = m.group(1)
        custom_alias = m.group(2)

        # Detect inclusion style and resolve path
        if raw_path.startswith('<') and raw_path.endswith('>'):
            # System header – keep as is
            header = raw_path[1:-1]
            use_angles = True
        elif raw_path.startswith('"') and raw_path.endswith('"'):
            # Explicit quoted path – keep as is
            header = raw_path[1:-1]
            use_angles = False
        else:
            # Check if it's a standard library header (e.g., "iostream")
            if raw_path in STD_HEADERS:
                header = raw_path
                use_angles = True
            else:
                # Local library – assume inside libs/ folder
                header = os.path.join('libs', raw_path).replace('\\', '/')
                use_angles = False

        # Determine if it's a C or C++ header
        if is_c_header(header):
            kind = 'c'
        else:
            kind = 'cpp'

        if kind == 'cpp':
            if custom_alias:
                alias = custom_alias
            else:
                alias = os.path.basename(header)
                alias = re.sub(r'\.(hpp|h|hxx)$', '', alias)
            # Build namespace from path, removing 'libs/' prefix if present
            namespace = header
            if namespace.startswith('libs/'):
                namespace = namespace[5:]  # strip 'libs/'
            namespace = namespace.replace('/', '::')
            namespace = re.sub(r'\.(hpp|h|hxx)$', '', namespace)
            register_alias(alias, namespace)
            return ('IMPORT_CPP', header, alias, use_angles), start_index + 1
        else:
            # C header – no alias
            return ('IMPORT_C', header, use_angles), start_index + 1

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
import re
import os
from . import StatementHandler, register_alias, register_c_alias, is_c_header, strip_comments

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
            # Top‑level namespace: take first component of path
            # e.g., "rapidfuzz/fuzz.hpp" → "rapidfuzz"
            path_parts = header.replace('\\', '/').split('/')
            namespace = path_parts[0] if len(path_parts) > 1 else alias
            register_alias(alias, namespace)
            return ('IMPORT_CPP', header, alias, use_angles), start_index + 1
        else:
            # C library: register alias for dot‑to‑underscore
            if custom_alias:
                alias = custom_alias
            else:
                alias = os.path.basename(header)
                alias = re.sub(r'\.(h|hpp)$', '', alias)
            register_c_alias(alias, alias)
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
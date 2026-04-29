import re
from .. import StatementHandler

class FreeHandler(StatementHandler):
    keywords = ['free var ']

    def can_handle(self, line):
        return bool(re.match(r'^free var [a-zA-Z_]\w*$', line.strip()))

    def parse(self, lines, start_index):
        line = lines[start_index].strip()
        m = re.match(r'^free var ([a-zA-Z_]\w*)$', line)
        if not m:
            raise SyntaxError("Expected: free var variable_name")
        name = m.group(1)
        return ('FREE', name), start_index + 1

    def generate(self, node, indent=''):
        name = node[1]
        return f'{indent}free({name});\n{indent}{name} = nullptr;'

    required_headers = set()
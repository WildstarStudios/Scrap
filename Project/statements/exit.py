import re
from . import StatementHandler

class ExitHandler(StatementHandler):
    keywords = ['exit ']

    def parse(self, lines, start_index):
        line = lines[start_index].strip()
        parts = line.split()
        if len(parts) == 2 and parts[0] == 'exit':
            try:
                code = int(parts[1])
            except ValueError:
                raise SyntaxError("Expected: exit <integer>")
            return ('EXIT', code), start_index + 1
        raise SyntaxError("Expected: exit <integer>")

    def generate(self, node, indent=''):
        code = node[1]
        return f'{indent}return {code};'

    required_headers = set()
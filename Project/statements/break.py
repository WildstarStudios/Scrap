from . import StatementHandler

class BreakHandler(StatementHandler):
    keywords = ['break']

    def parse(self, lines, start_index):
        line = lines[start_index].strip()
        if line != 'break':
            raise SyntaxError("Expected 'break'")
        return ('BREAK', None), start_index + 1

    def generate(self, node, indent=''):
        return f'{indent}break;'

    required_headers = set()
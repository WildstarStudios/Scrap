from . import StatementHandler, strip_comments

class DeleteHandler(StatementHandler):
    keywords = ['delete ']

    def can_handle(self, line):
        return line.strip().startswith('delete ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        expr = line[7:].strip()   # after 'delete '
        if not expr:
            raise SyntaxError("Expected expression after 'delete'")
        return ('DELETE', expr), start_index + 1

    def generate(self, node, indent=''):
        return f'{indent}delete {node[1]};'

    required_headers = set()
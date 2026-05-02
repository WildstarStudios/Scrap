# return.py
from scrap.core.handler_base import StatementHandler, strip_comments

class ReturnHandler(StatementHandler):
    keywords = ['return']

    def can_handle(self, line):
        return line.strip().startswith('return')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        if line == 'return':
            return ('RETURN', None), start_index + 1
        expr = line[7:].strip()
        return ('RETURN', expr), start_index + 1

    def generate(self, node, indent=''):
        if node[1] is None:
            return indent + 'return {};'
        return f'{indent}return {node[1]};'
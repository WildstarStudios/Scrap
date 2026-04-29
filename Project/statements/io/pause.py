from .. import StatementHandler, strip_comments

class PauseHandler(StatementHandler):
    keywords = ['pause']

    def can_handle(self, line):
        return line.strip() == 'pause'

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        if line != 'pause':
            raise SyntaxError("Expected 'pause'")
        return ('PAUSE', None), start_index + 1

    def generate(self, node, indent=''):
        return f'{indent}std::cin.get();'

    required_headers = {'<iostream>'}
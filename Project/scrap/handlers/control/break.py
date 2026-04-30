from scrap.core.handler_base import StatementHandler

class BreakHandler(StatementHandler):
    keywords = ['break']

    def can_handle(self, line):
        return line.strip() == 'break'

    def parse(self, lines, start_index):
        return ('BREAK', None), start_index + 1

    def generate(self, node, indent=''):
        return indent + 'break;'
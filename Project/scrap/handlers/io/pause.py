from scrap.core.handler_base import StatementHandler

class PauseHandler(StatementHandler):
    keywords = ['pause']

    def can_handle(self, line):
        return line.strip() == 'pause'

    def parse(self, lines, start_index):
        return ('PAUSE', None), start_index + 1

    def generate(self, node, indent=''):
        return indent + 'std::cin.get();'

    required_headers = {'<iostream>'}
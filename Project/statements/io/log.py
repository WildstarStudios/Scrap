import re
from .. import StatementHandler

class LogHandler(StatementHandler):
    keywords = ['log ']

    def parse(self, lines, start_index):
        line = lines[start_index].strip()
        rest = line[4:].strip()
        if not rest:
            raise SyntaxError("Expected an expression after 'log'")
        return ('LOG_EXPR', rest), start_index + 1

    def generate(self, node, indent=''):
        expr = node[1]
        return f'{indent}std::cout << {expr} << std::endl;'

    required_headers = {'<iostream>'}
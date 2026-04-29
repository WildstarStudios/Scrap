import re
from .. import StatementHandler

class VarIncrementHandler(StatementHandler):
    def can_handle(self, line):
        return bool(re.match(r'^var [a-zA-Z_]\w* [-+]\d+$', line.strip()))

    def parse(self, lines, start_index):
        line = lines[start_index].strip()
        parts = line.split()
        name = parts[1]
        op = parts[2]
        amount = int(op)
        return ('VAR_INCR', name, amount), start_index + 1

    def generate(self, node, indent=''):
        name = node[1]
        amount = node[2]
        if amount >= 0:
            return f'{indent}{name} += {amount};'
        else:
            return f'{indent}{name} -= {-amount};'

    required_headers = set()
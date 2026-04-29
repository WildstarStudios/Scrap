import re
from .. import StatementHandler, strip_comments

class LogHandler(StatementHandler):
    keywords = ['log ']

    def can_handle(self, line):
        return line.strip().startswith('log ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        rest = line[4:].strip()
        if not rest:
            raise SyntaxError("Expected an expression after 'log'")
        return ('LOG_EXPR', rest), start_index + 1

    def generate(self, node, indent=''):
        expr = node[1]
        # Split the expression on '+' that are not inside quotes
        parts = self._split_expression(expr)
        # Build the output chain: std::cout << part1 << part2 << ... << std::endl;
        output = f'{indent}std::cout'
        for part in parts:
            output += f' << {part}'
        output += ' << std::endl;'
        return output

    def _split_expression(self, expr):
        """Split expression on '+' outside quotes, preserving quoted strings."""
        parts = []
        current = []
        in_quotes = False
        for ch in expr:
            if ch == '"':
                in_quotes = not in_quotes
                current.append(ch)
            elif ch == '+' and not in_quotes:
                parts.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            parts.append(''.join(current).strip())
        # If no '+' was found, the whole expression is a single part
        if not parts:
            parts = [expr.strip()]
        return parts

    required_headers = {'<iostream>'}
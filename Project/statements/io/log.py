import re
from .. import StatementHandler, parse_function_call, strip_comments, wrap_c_args

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
        parts = self._split_expression(expr)
        transformed_parts = []
        for part in parts:
            if '(' in part and ')' in part:
                call_info = parse_function_call(part)
                if call_info:
                    full_func, args, is_c = call_info
                    args = wrap_c_args(args, is_c)
                    args_str = ', '.join(args)
                    transformed_parts.append(f'{full_func}({args_str})')
                else:
                    transformed_parts.append(part)
            else:
                transformed_parts.append(part)
        output = f'{indent}std::cout'
        for part in transformed_parts:
            output += f' << {part}'
        output += ' << std::endl;'
        return output

    def _split_expression(self, expr):
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
        if not parts:
            parts = [expr.strip()]
        return parts

    required_headers = {'<iostream>'}
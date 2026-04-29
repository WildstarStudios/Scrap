import re
from . import StatementHandler, parse_function_call, strip_comments

class FunctionCallHandler(StatementHandler):
    keywords = []

    def can_handle(self, line):
        stripped = line.strip()
        if stripped.endswith(':'):
            return False
        if stripped.startswith(('var ', 'if ', 'while ', 'repeat ', 'for ', 'ask ', 'log ', 'free ', 'import ', 'pause', '--', 'exit ')):
            return False
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_.]*\(.*\)$', stripped))

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        return ('FUNCALL', line), start_index + 1

    def generate(self, node, indent=''):
        call_expr = node[1]
        call_info = parse_function_call(call_expr)
        if call_info:
            full_func, args = call_info
            args_str = ', '.join(args)
            return f'{indent}{full_func}({args_str});'
        return f'{indent}{call_expr};'

    def required_headers(self, node=None):
        return set()
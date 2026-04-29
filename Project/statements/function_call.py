import re
from . import StatementHandler, C_STRING_FUNCTIONS, _var_types

class FunctionCallHandler(StatementHandler):
    """Handles standalone function calls: func(args), obj.method(args)."""
    keywords = []

    def can_handle(self, line):
        stripped = line.strip()
        if stripped.endswith(':'):
            return False
        if stripped.startswith(('var ', 'if ', 'while ', 'repeat ', 'for ', 'ask ', 'log ', 'free ', 'import ', 'pause', '--', 'exit ')):
            return False
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?\(.*\)$', stripped))

    def parse(self, lines, start_index):
        line = lines[start_index].strip()
        return ('FUNCALL', line), start_index + 1

    def generate(self, node, indent=''):
        call_expr = node[1]
        # Parse the call to get function name and arguments
        m = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?)\((.*)\)$', call_expr)
        if m:
            func = m.group(1)
            args_raw = m.group(3).strip()
            # Split arguments (simple split, not handling nested commas)
            if args_raw:
                args = [a.strip() for a in args_raw.split(',')]
            else:
                args = []
            # Transform if function is in C_STRING_FUNCTIONS
            base_func = func.split('.')[-1] if '.' in func else func
            if base_func in C_STRING_FUNCTIONS:
                new_args = []
                for arg in args:
                    # If arg is a variable name and its type is std::string, add .c_str()
                    if arg in _var_types and _var_types[arg] == 'std::string':
                        new_args.append(f'{arg}.c_str()')
                    else:
                        new_args.append(arg)
                call_expr = f'{func}({", ".join(new_args)})'
        return f'{indent}{call_expr};'

    def required_headers(self, node=None):
        return set()
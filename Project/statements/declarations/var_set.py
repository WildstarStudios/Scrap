import re
from .. import StatementHandler, parse_function_call

class SetHandler(StatementHandler):
    keywords = []

    def can_handle(self, line):
        # Must contain '=', not start with a keyword, and not be a block header.
        if '=' not in line:
            return False
        stripped = line.strip()
        # Exclude lines that start with language keywords
        if stripped.startswith(('var ', 'if ', 'while ', 'repeat ', 'for ', 'ask ', 'log ', 'free ', 'import ', 'pause', '--')):
            return False
        # Exclude lines that look like a block header (ending with ':')
        if stripped.endswith(':'):
            return False
        return True

    def parse(self, lines, start_index):
        line = lines[start_index].strip()
        # Split on the first '=' that is not inside quotes
        lhs, rhs = self._split_on_first_eq(line)
        lhs = lhs.strip()
        rhs = rhs.strip()

        # Parse RHS as function call, string, number, or general expression
        call_info = parse_function_call(rhs)
        if call_info:
            full_func, args = call_info
            return ('SET_FUNCCALL', lhs, full_func, args), start_index + 1
        else:
            if rhs.startswith('"') and rhs.endswith('"'):
                literal = rhs[1:-1]
                return ('SET_STRING', lhs, literal), start_index + 1
            elif re.match(r'^-?\d+\.\d+$', rhs):
                return ('SET_FLOAT', lhs, rhs), start_index + 1
            elif re.match(r'^-?\d+$', rhs):
                return ('SET_INT', lhs, rhs), start_index + 1
            else:
                # General expression (e.g., array access, variable, arithmetic)
                return ('SET_EXPR', lhs, rhs), start_index + 1

    def generate(self, node, indent=''):
        kind = node[0]
        lhs = node[1]
        if kind == 'SET_INT':
            rhs = node[2]
            return f'{indent}{lhs} = {rhs};'
        elif kind == 'SET_FLOAT':
            rhs = node[2]
            return f'{indent}{lhs} = {rhs};'
        elif kind == 'SET_STRING':
            literal = node[2]
            escaped = literal.replace('\\', '\\\\').replace('"', '\\"')
            return f'{indent}{lhs} = "{escaped}";'
        elif kind == 'SET_FUNCCALL':
            full_func, args = node[2], node[3]
            args_str = ', '.join(args)
            return f'{indent}{lhs} = {full_func}({args_str});'
        elif kind == 'SET_EXPR':
            rhs = node[2]
            return f'{indent}{lhs} = {rhs};'
        else:
            raise RuntimeError(f"Unknown set node kind: {kind}")

    def required_headers(self, node=None):
        if node and node[0] == 'SET_STRING':
            return {'<string>'}
        return set()

    def _split_on_first_eq(self, line):
        """Split line at first '=' not inside quotes."""
        in_quotes = False
        for i, ch in enumerate(line):
            if ch == '"':
                in_quotes = not in_quotes
            elif ch == '=' and not in_quotes:
                return line[:i], line[i+1:]
        return line, ''   # fallback (should not happen)
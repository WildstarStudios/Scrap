import re
from .. import StatementHandler, parse_function_call, strip_comments, wrap_c_args, _var_types

class SetHandler(StatementHandler):
    keywords = []

    def can_handle(self, line):
        if '=' not in line:
            return False
        stripped = line.strip()
        if stripped.startswith(('var ', 'if ', 'while ', 'repeat ', 'for ', 'ask ', 'log ', 'free ', 'import ', 'pause', '--')):
            return False
        if stripped.endswith(':'):
            return False
        return True

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        lhs, rhs = self._split_on_first_eq(line)
        lhs = lhs.strip()
        rhs = rhs.strip()

        # 1. Plain string literal (no concatenation)
        if rhs.startswith('"') and rhs.endswith('"') and '+' not in rhs:
            literal = rhs[1:-1]
            return ('SET_STRING', lhs, literal), start_index + 1

        # 2. String expression (starts with quote but has +)
        if rhs.startswith('"'):
            # Contains '+' → treat as generic expression
            return ('SET_EXPR', lhs, rhs), start_index + 1

        # 3. Function call
        call_info = parse_function_call(rhs)
        if call_info:
            full_func, args, is_c = call_info
            args = wrap_c_args(args, is_c)
            return ('SET_FUNCCALL', lhs, full_func, args), start_index + 1

        # 4. Numeric, nullptr, or generic expression
        if re.match(r'^-?\d+\.\d+$', rhs):
            return ('SET_FLOAT', lhs, rhs), start_index + 1
        elif re.match(r'^-?\d+$', rhs):
            return ('SET_INT', lhs, rhs), start_index + 1
        elif rhs == 'nullptr':
            return ('SET_NULLPTR', lhs), start_index + 1
        else:
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
        elif kind == 'SET_NULLPTR':
            return f'{indent}{lhs} = nullptr;'
        else:
            raise RuntimeError(f"Unknown set node kind: {kind}")

    def required_headers(self, node=None):
        if node and node[0] == 'SET_STRING':
            return {'<string>'}
        return set()

    def _split_on_first_eq(self, line):
        in_quotes = False
        for i, ch in enumerate(line):
            if ch == '"':
                in_quotes = not in_quotes
            elif ch == '=' and not in_quotes:
                return line[:i], line[i+1:]
        return line, ''

    # ---------- Semantic Check ----------
    def check_semantics(self, node, symbols):
        lhs = node[1]
        var_sym = symbols.lookup(lhs)
        if var_sym is None:
            raise SyntaxError(f"Variable '{lhs}' not declared")
        if var_sym.is_function:
            raise SyntaxError(f"Cannot assign to function '{lhs}'")
        kind = node[0]
        t = var_sym.cpp_type
        if kind == 'SET_STRING' and t != 'std::string':
            raise SyntaxError(f"Cannot assign string to variable '{lhs}' of type '{t}'")
        if kind == 'SET_INT' and t not in ('int', 'long', 'long long', 'auto'):
            raise SyntaxError(f"Cannot assign integer to variable '{lhs}' of type '{t}'")
        if kind == 'SET_FLOAT' and t not in ('float', 'double', 'auto'):
            raise SyntaxError(f"Cannot assign float to variable '{lhs}' of type '{t}'")
        if kind == 'SET_FUNCCALL':
            func_name = node[2]
            func_sym = symbols.lookup(func_name)
            if func_sym:
                if func_sym.is_function and func_sym.cpp_type != t and t != 'auto':
                    print(f"Warning: assigning return of '{func_name}' (type '{func_sym.cpp_type}') to variable '{lhs}' of type '{t}'", file=__import__('sys').stderr)
import re
from .. import StatementHandler, parse_function_call, strip_comments, set_var_type

class VarHandler(StatementHandler):
    def can_handle(self, line):
        stripped = line.strip()
        if re.match(r'^var\s+[a-zA-Z_]\w*\s+as\s+[a-zA-Z_]\w*(?:[*&])*\s*$', stripped):
            return True
        if re.match(r'^var\s+[a-zA-Z_]\w*\s+as\s+[a-zA-Z_]\w*(?:[*&])*\s*=\s*.+$', stripped):
            return True
        return False

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        # Uninitialized
        m = re.match(r'^var\s+([a-zA-Z_]\w*)\s+as\s+([a-zA-Z_]\w*(?:[*&])*)\s*$', line)
        if m:
            name = m.group(1)
            scrap_type = m.group(2)
            cpp_type = self._to_cpp_type(scrap_type)
            set_var_type(name, cpp_type)
            return ('DEFINE_VAR_UNINIT', name, cpp_type), start_index + 1

        # Initialized: capture everything after '='
        m = re.match(r'^var\s+([a-zA-Z_]\w*)\s+as\s+([a-zA-Z_]\w*(?:[*&])*)\s*=\s*(.+)$', line)
        if not m:
            raise SyntaxError("Expected: var name as type [= value]")
        name = m.group(1)
        scrap_type = m.group(2)
        value_expr = m.group(3).strip()
        cpp_type = self._to_cpp_type(scrap_type)

        # 1. If it looks like a quoted string, handle it as a string literal immediately.
        #    Do NOT pass it to parse_function_call – even if it contains parentheses.
        if value_expr.startswith('"'):
            if not value_expr.endswith('"'):
                raise SyntaxError("Unclosed string literal")
            if '+' in value_expr:
                # Concatenation with + – treat as generic expression
                set_var_type(name, cpp_type)
                return ('DEFINE_VAR_EXPR', name, value_expr, cpp_type), start_index + 1

            if cpp_type != 'std::string':
                raise SyntaxError(f"Type mismatch: cannot assign string to '{scrap_type}'")
            literal = value_expr[1:-1]
            set_var_type(name, cpp_type)
            return ('DEFINE_VAR_STRING', name, literal, cpp_type), start_index + 1

        # 2. Function call (only if it doesn't start with a quote)
        call_info = parse_function_call(value_expr)
        if call_info:
            full_func, args = call_info
            set_var_type(name, cpp_type)
            return ('DEFINE_VAR_FUNCCALL', name, full_func, args, cpp_type), start_index + 1

        # 3. Integer literal
        if re.match(r'^-?\d+$', value_expr):
            if cpp_type not in ('int', 'long', 'long long'):
                raise SyntaxError(f"Type mismatch: cannot assign integer to '{scrap_type}'")
            set_var_type(name, cpp_type)
            return ('DEFINE_VAR_INT', name, value_expr, cpp_type), start_index + 1

        # 4. Float literal
        if re.match(r'^-?\d+\.\d+$', value_expr):
            if cpp_type not in ('float', 'double'):
                raise SyntaxError(f"Type mismatch: cannot assign float to '{scrap_type}'")
            set_var_type(name, cpp_type)
            return ('DEFINE_VAR_FLOAT', name, value_expr, cpp_type), start_index + 1

        # 5. Boolean literal
        if value_expr in ('true', 'false'):
            if cpp_type != 'bool':
                raise SyntaxError(f"Type mismatch: cannot assign bool to '{scrap_type}'")
            set_var_type(name, cpp_type)
            return ('DEFINE_VAR_BOOL', name, value_expr, cpp_type), start_index + 1

        # 6. nullptr
        if value_expr == 'nullptr':
            if not cpp_type.endswith('*'):
                raise SyntaxError(f"nullptr requires pointer type, got '{scrap_type}'")
            set_var_type(name, cpp_type)
            return ('DEFINE_VAR_NULLPTR', name, cpp_type), start_index + 1

        # 7. Everything else – generic expression
        set_var_type(name, cpp_type)
        return ('DEFINE_VAR_EXPR', name, value_expr, cpp_type), start_index + 1

    def generate(self, node, indent=''):
        kind = node[0]
        name = node[1]
        if kind == 'DEFINE_VAR_UNINIT':
            type_name = node[2]
            return f'{indent}{type_name} {name};'
        elif kind == 'DEFINE_VAR_INT':
            value = node[2]
            type_name = node[3]
            return f'{indent}{type_name} {name} = {value};'
        elif kind == 'DEFINE_VAR_FLOAT':
            value = node[2]
            type_name = node[3]
            return f'{indent}{type_name} {name} = {value};'
        elif kind == 'DEFINE_VAR_STRING':
            literal = node[2]
            type_name = node[3]
            escaped = literal.replace('\\', '\\\\').replace('"', '\\"')
            return f'{indent}{type_name} {name} = "{escaped}";'
        elif kind == 'DEFINE_VAR_BOOL':
            value = node[2]
            type_name = node[3]
            return f'{indent}{type_name} {name} = {value};'
        elif kind == 'DEFINE_VAR_FUNCCALL':
            full_func, args, type_name = node[2], node[3], node[4]
            args_str = ', '.join(args)
            return f'{indent}{type_name} {name} = {full_func}({args_str});'
        elif kind == 'DEFINE_VAR_NULLPTR':
            type_name = node[2]
            return f'{indent}{type_name} {name} = nullptr;'
        elif kind == 'DEFINE_VAR_EXPR':
            value = node[2]
            type_name = node[3]
            return f'{indent}{type_name} {name} = {value};'
        else:
            raise RuntimeError(f"Unknown var node kind: {kind}")

    def required_headers(self, node=None):
        if node and (node[0] == 'DEFINE_VAR_STRING' or
                     (node[0] == 'DEFINE_VAR_FUNCCALL' and node[4] == 'std::string')):
            return {'<string>'}
        return set()

    def _to_cpp_type(self, scrap_type: str) -> str:
        mapping = {
            'int': 'int',
            'float': 'double',
            'String': 'std::string',
            'str': 'std::string',
            'bool': 'bool',
        }
        base_type = scrap_type.rstrip('*&').rstrip()
        if base_type in mapping:
            suffix = scrap_type[len(base_type):]
            return mapping[base_type] + suffix
        return scrap_type
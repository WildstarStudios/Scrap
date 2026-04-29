import re
from .. import StatementHandler, parse_function_call, strip_comments, set_var_type, wrap_c_args

class VarHandler(StatementHandler):
    def can_handle(self, line):
        stripped = line.strip()
        # allow: var name as Type[ = value], var name = value
        if re.match(r'^var\s+[a-zA-Z_]\w*\s+as\s+[a-zA-Z_]\w*(?:[*&])*(\s*=\s*.+)?$', stripped):
            return True
        if re.match(r'^var\s+[a-zA-Z_]\w*\s*=\s*.+$', stripped):
            return True
        return False

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        # Case 1: var name as Type [= value]
        m = re.match(r'^var\s+([a-zA-Z_]\w*)\s+as\s+([a-zA-Z_]\w*(?:[*&])*)\s*(?:=\s*(.+))?$', line)
        if m:
            name = m.group(1)
            scrap_type = m.group(2)
            cpp_type = self._to_cpp_type(scrap_type)
            value_expr = m.group(3)  # may be None
            if value_expr is None:
                set_var_type(name, cpp_type)
                return ('DEFINE_VAR_UNINIT', name, cpp_type), start_index + 1
            value_expr = value_expr.strip()
            return self._process_init(name, cpp_type, value_expr, start_index)

        # Case 2: var name = expr  (auto)
        m = re.match(r'^var\s+([a-zA-Z_]\w*)\s*=\s*(.+)$', line)
        if m:
            name = m.group(1)
            value_expr = m.group(2).strip()
            cpp_type = 'auto'
            return self._process_init(name, cpp_type, value_expr, start_index)

        raise SyntaxError("Expected: var name as Type [= value] or var name = value")

    def _process_init(self, name, cpp_type, value_expr, start_index):
        # String literal detection
        if value_expr.startswith('"'):
            if not value_expr.endswith('"'):
                raise SyntaxError("Unclosed string literal")
            if '+' in value_expr:
                set_var_type(name, cpp_type)
                return ('DEFINE_VAR_EXPR', name, value_expr, cpp_type), start_index + 1
            if cpp_type != 'std::string' and cpp_type != 'auto':
                raise SyntaxError(f"Type mismatch: cannot assign string to '{cpp_type}'")
            literal = value_expr[1:-1]
            final_type = 'std::string' if cpp_type == 'auto' else cpp_type
            set_var_type(name, final_type)
            return ('DEFINE_VAR_STRING', name, literal, final_type), start_index + 1

        # new expression?
        new_match = re.match(r'^new\s+(.+)$', value_expr)
        if new_match:
            set_var_type(name, cpp_type)
            return ('DEFINE_VAR_NEW', name, new_match.group(1), cpp_type), start_index + 1

        # Function call
        call_info = parse_function_call(value_expr)
        if call_info:
            full_func, args, is_c = call_info
            args = wrap_c_args(args, is_c)
            set_var_type(name, cpp_type)
            return ('DEFINE_VAR_FUNCCALL', name, full_func, args, cpp_type), start_index + 1

        # Numeric, bool, nullptr, expression
        if re.match(r'^-?\d+$', value_expr):
            if cpp_type not in ('int', 'long', 'long long', 'auto'):
                raise SyntaxError(f"Type mismatch: cannot assign integer to '{cpp_type}'")
            final_type = 'int' if cpp_type == 'auto' else cpp_type
            set_var_type(name, final_type)
            return ('DEFINE_VAR_INT', name, value_expr, final_type), start_index + 1
        if re.match(r'^-?\d+\.\d+$', value_expr):
            if cpp_type not in ('float', 'double', 'auto'):
                raise SyntaxError(f"Type mismatch: cannot assign float to '{cpp_type}'")
            final_type = 'double' if cpp_type == 'auto' else cpp_type
            set_var_type(name, final_type)
            return ('DEFINE_VAR_FLOAT', name, value_expr, final_type), start_index + 1
        if value_expr in ('true', 'false'):
            if cpp_type != 'bool' and cpp_type != 'auto':
                raise SyntaxError(f"Type mismatch: cannot assign bool to '{cpp_type}'")
            final_type = 'bool' if cpp_type == 'auto' else cpp_type
            set_var_type(name, final_type)
            return ('DEFINE_VAR_BOOL', name, value_expr, final_type), start_index + 1
        if value_expr == 'nullptr':
            if not cpp_type.endswith('*') and cpp_type != 'auto':
                raise SyntaxError(f"nullptr requires pointer type, got '{cpp_type}'")
            set_var_type(name, cpp_type)
            return ('DEFINE_VAR_NULLPTR', name, cpp_type), start_index + 1

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
        elif kind == 'DEFINE_VAR_NEW':
            new_expr = node[2]
            type_name = node[3]
            return f'{indent}{type_name} {name} = new {new_expr};'
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
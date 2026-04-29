import re
from .. import StatementHandler, parse_function_call, strip_comments, set_var_type

class VarHandler(StatementHandler):
    def can_handle(self, line):
        if '= [' in line:
            return False
        return bool(re.match(r'^var [a-zA-Z_]\w*\s*(as\s+\S+)?\s*=\s*.+$', line.strip()))

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^var ([a-zA-Z_]\w*)\s*(?:as\s+([^\s=]+))?\s*=\s*(.+)$', line)
        if not m:
            raise SyntaxError("Expected: var name [as type] = value")
        name = m.group(1)
        type_name = m.group(2)
        value_expr = m.group(3).strip()

        if type_name == 'string':
            type_name = 'std::string'

        # function call?
        call_info = parse_function_call(value_expr)
        if call_info:
            full_func, args = call_info
            if not type_name:
                type_name = 'double'
            set_var_type(name, type_name)
            return ('DEFINE_VAR_FUNCCALL', name, full_func, args, type_name), start_index + 1

        # string literal
        if value_expr.startswith('"') and value_expr.endswith('"'):
            literal = value_expr[1:-1]
            if not type_name:
                type_name = 'std::string'
            set_var_type(name, type_name)
            return ('DEFINE_VAR_STRING', name, literal, type_name), start_index + 1

        # integer
        if re.match(r'^-?\d+$', value_expr):
            if not type_name:
                type_name = 'int'
            set_var_type(name, type_name)
            return ('DEFINE_VAR_INT', name, value_expr, type_name), start_index + 1

        # float
        if re.match(r'^-?\d+\.\d+$', value_expr):
            if not type_name:
                type_name = 'double'
            set_var_type(name, type_name)
            return ('DEFINE_VAR_FLOAT', name, value_expr, type_name), start_index + 1

        # nullptr (pointer)
        if value_expr == 'nullptr':
            if not type_name:
                raise SyntaxError("Pointer variable requires explicit type (e.g., as SomeType*)")
            set_var_type(name, type_name)
            return ('DEFINE_VAR_NULLPTR', name, type_name), start_index + 1

        raise SyntaxError("Value must be a quoted string, integer, float, nullptr, or function call")

    def generate(self, node, indent=''):
        kind = node[0]
        name = node[1]
        if kind == 'DEFINE_VAR_INT':
            value = node[2]
            type_name = node[3]
            if type_name.endswith('*'):
                return f'{indent}{type_name} {name} = ({type_name}){value};'
            else:
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
        elif kind == 'DEFINE_VAR_FUNCCALL':
            full_func, args, type_name = node[2], node[3], node[4]
            args_str = ', '.join(args)
            if type_name.endswith('*'):
                return f'{indent}{type_name} {name} = ({type_name})({full_func}({args_str}));'
            else:
                return f'{indent}{type_name} {name} = {full_func}({args_str});'
        elif kind == 'DEFINE_VAR_NULLPTR':
            type_name = node[2]
            return f'{indent}{type_name} {name} = nullptr;'
        else:
            raise RuntimeError("Unknown var node kind")

    def required_headers(self, node=None):
        if node and (node[0] == 'DEFINE_VAR_STRING' or (node[0] == 'DEFINE_VAR_FUNCCALL' and node[4] == 'std::string')):
            return {'<string>'}
        return set()
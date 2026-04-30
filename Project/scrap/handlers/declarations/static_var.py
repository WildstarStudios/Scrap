import re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import infer_type_from_value, to_cpp_type

class StaticVarHandler(StatementHandler):
    keywords = ['static var ']

    def can_handle(self, line):
        return line.strip().startswith('static var ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        # Pattern: static var name [as Type] [= value]
        m = re.match(r'^static var\s+([a-zA-Z_]\w*)\s*(?:as\s+([a-zA-Z_]\w*(?:[*&])*))?\s*(?:=\s*(.+))?$', line)
        if not m:
            raise SyntaxError("Expected: static var name [as Type] [= value]")
        name, explicit_type, value = m.groups()
        if value:
            value = value.strip()
        if explicit_type:
            cpp_type = to_cpp_type(explicit_type)
        else:
            if value is None:
                raise SyntaxError("static var without type requires an initialiser")
            cpp_type = infer_type_from_value(value)

        if value is None:
            return ('STATIC_VAR_DECL', name, cpp_type), start_index + 1
        return ('STATIC_VAR_INIT', name, cpp_type, value), start_index + 1

    def generate(self, node, indent=''):
        kind = node[0]
        name = node[1]
        if kind == 'STATIC_VAR_DECL':
            cpp_type = node[2]
            return f'{indent}static {cpp_type} {name};'
        elif kind == 'STATIC_VAR_INIT':
            cpp_type = node[2]
            value = node[3]
            if value.startswith('"') and value.endswith('"'):
                escaped = value[1:-1].replace('\\', '\\\\').replace('"', '\\"')
                return f'{indent}static {cpp_type} {name} = "{escaped}";'
            return f'{indent}static {cpp_type} {name} = {value};'

    def check_semantics(self, node, symbols):
        name = node[1]
        cpp_type = node[2] if len(node) > 2 else None
        if cpp_type:
            symbols.declare(name, cpp_type)
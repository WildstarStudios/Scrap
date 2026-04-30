import re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import (
    infer_type_from_value, to_cpp_type, resolve_dotted_calls,
    get_owned_wrapper
)

class VarHandler(StatementHandler):
    keywords = ['var ']

    def can_handle(self, line):
        return line.strip().startswith('var ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^var\s+([a-zA-Z_]\w*)\s*(?:as\s+([a-zA-Z_]\w*(?:[*&])*))?\s*(?:=\s*(.+))?$', line)
        if not m:
            raise SyntaxError("Expected: var name [as Type] [= value]")
        name, explicit_type, value = m.groups()
        if value:
            value = value.strip()
            value = resolve_dotted_calls(value)
            # safety net – ensure dots before '(' become ::
            value = re.sub(r'([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)\s*\(', r'\1::\2(', value)

        if explicit_type:
            cpp_type = to_cpp_type(explicit_type)
            if value is None:
                return ('VAR_DECL', name, cpp_type, None), start_index + 1
            return ('VAR_INIT', name, cpp_type, value), start_index + 1
        else:
            if value is None:
                raise SyntaxError("var without type requires an initialiser")
            cpp_type = infer_type_from_value(value)
            m_call = re.match(r'^([a-zA-Z_][\w:]*)\((.*)\)$', value)
            if m_call:
                func_name = m_call.group(1)
                short_name = func_name.split('::')[-1]
                wrapper = get_owned_wrapper(short_name)
                if wrapper:
                    cpp_type = wrapper
            return ('VAR_INIT', name, cpp_type, value), start_index + 1

    def generate(self, node, indent=''):
        kind = node[0]
        name = node[1]
        if kind == 'VAR_DECL':
            cpp_type = node[2]
            # built-in types that don't need zero‑initialisation
            simple_types = {'int', 'float', 'double', 'bool', 'void', 'char', 'auto'}
            if cpp_type in simple_types or cpp_type.endswith('*') or cpp_type.endswith('&'):
                return f'{indent}{cpp_type} {name};'
            else:
                # struct / class – zero‑initialise to avoid padding garbage
                return f'{indent}{cpp_type} {name}{{}};'

        elif kind == 'VAR_INIT':
            cpp_type = node[2]
            value = node[3]
            m_call = re.match(r'^([a-zA-Z_][\w:]*)\((.*)\)$', value)
            if m_call:
                func_name = m_call.group(1)
                short_name = func_name.split('::')[-1]
                wrapper = get_owned_wrapper(short_name)
                if wrapper:
                    args = m_call.group(2)
                    return f'{indent}{cpp_type} {name}({func_name}({args}));'
            if value.startswith('"') and value.endswith('"'):
                escaped = value[1:-1].replace('\\', '\\\\').replace('"', '\\"')
                return f'{indent}{cpp_type} {name} = "{escaped}";'
            return f'{indent}{cpp_type} {name} = {value};'

    def check_semantics(self, node, symbols):
        kind = node[0]
        name = node[1]
        cpp_type = node[2]
        if kind == 'VAR_DECL':
            symbols.declare(name, cpp_type)
        elif kind == 'VAR_INIT':
            symbols.declare(name, cpp_type)
import re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import resolve_dotted_calls, get_variable_type, is_static_string, is_dynamic_string, get_variable_size

class SetHandler(StatementHandler):
    keywords = []

    def can_handle(self, line):
        stripped = line.strip()
        if '=' not in stripped:
            return False
        if stripped.startswith(('var ', 'list ', 'array ', 'if ', 'elif ', 'else',
                                'while ', 'for ', 'repeat ', 'func ', 'log ', 'ask ',
                                'pause', 'break', 'return', 'import lib')):
            return False
        if stripped.endswith(':'):
            return False
        m = re.match(r'^([a-zA-Z_][\w.]*)\s*=(.*)$', stripped)
        return m is not None

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^([a-zA-Z_][\w.]*)\s*=\s*(.+)$', line)
        if not m:
            raise SyntaxError("Expected: variable = expression")
        name = m.group(1)
        value = m.group(2).strip()
        if value.startswith('"') and value.endswith('"') and '+' not in value:
            return ('SET_STRING', name, value[1:-1]), start_index + 1
        return ('SET_EXPR', name, value), start_index + 1

    def generate(self, node, indent=''):
        kind = node[0]
        name = node[1]
        if kind == 'SET_STRING':
            literal = node[2]
            escaped = literal.replace('\\', '\\\\').replace('"', '\\"')
            if is_static_string(name):
                # static char array – use strcpy; if literal too long, it's a C error (safe enough)
                return f'{indent}strcpy({name}, "{escaped}");'
            elif is_dynamic_string(name):
                return f'{indent}string_set(&{name}, "{escaped}");'
            else:
                # unknown type, fallback to assignment
                return f'{indent}{name} = "{escaped}";'
        elif kind == 'SET_EXPR':
            expr = resolve_dotted_calls(node[2])
            if is_static_string(name):
                # assume expr returns const char*
                return f'{indent}strcpy({name}, {expr});'
            elif is_dynamic_string(name):
                return f'{indent}string_set(&{name}, {expr});'
            else:
                return f'{indent}{name} = {expr};'
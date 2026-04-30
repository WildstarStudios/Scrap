import re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import resolve_dotted_calls

class SetHandler(StatementHandler):
    keywords = []  # we detect via '='

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
            return f'{indent}{name} = "{escaped}";'
        elif kind == 'SET_EXPR':
            expr = resolve_dotted_calls(node[2])
            return f'{indent}{name} = {expr};'

    def check_semantics(self, node, symbols):
        name = node[1]
        # If it's a dotted name (e.g., wc.lpfnWndProc), only check the base variable
        if '.' in name:
            base = name.split('.')[0]
        else:
            base = name
        if symbols.lookup(base) is None:
            raise SyntaxError(f"Variable '{base}' not declared")
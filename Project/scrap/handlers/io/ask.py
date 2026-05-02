import re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import register_variable_type

class AskHandler(StatementHandler):
    keywords = ['ask ']

    def can_handle(self, line):
        return bool(re.match(r'^ask ".*" into [a-zA-Z_]\w*$', line.strip()))

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^ask "([^"]*)" into ([a-zA-Z_]\w*)$', line)
        if not m:
            raise SyntaxError("Expected: ask \"prompt\" into variable")
        return ('ASK', m.group(2), m.group(1)), start_index + 1

    def generate(self, node, indent=''):
        var, prompt = node[1], node[2]
        escaped = prompt.replace('\\', '\\\\').replace('"', '\\"')
        # Dynamic string – use our custom SSO type
        register_variable_type(var, 'string')
        return (
            f'{indent}string {var};\n'
            f'{indent}printf("{escaped}");\n'
            f'{indent}string_readline(&{var}, stdin);'
        )

    required_headers = {'<cstdio>', '<cstring>', '<cstdlib>'}
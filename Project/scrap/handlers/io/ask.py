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
        # Register the variable as std::string
        register_variable_type(var, 'std::string')
        return (
            f'{indent}std::string {var};\n'
            f'{indent}printf("{escaped}");\n'
            f'{indent}char __buf[1024];\n'
            f'{indent}if (fgets(__buf, sizeof(__buf), stdin)) {{\n'
            f'{indent}    {var} = __buf;\n'
            f'{indent}    if (!{var}.empty() && {var}.back() == \'\\n\') {var}.pop_back();\n'
            f'{indent}}}'
        )

    required_headers = {'<cstdio>', '<string>'}
import re
from .. import StatementHandler, strip_comments

class AskHandler(StatementHandler):
    keywords = ['ask ']

    def can_handle(self, line):
        return bool(re.match(r'^ask ".*" into [a-zA-Z_]\w*$', line.strip()))

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^ask "((?:[^"\\]|\\.)*)" into ([a-zA-Z_]\w*)$', line)
        if not m:
            raise SyntaxError("Expected: ask \"prompt\" into variable_name")
        prompt = m.group(1)
        var_name = m.group(2)
        return ('ASK', var_name, prompt), start_index + 1

    def generate(self, node, indent=''):
        var_name, prompt = node[1], node[2]
        escaped_prompt = prompt.replace('\\', '\\\\').replace('"', '\\"')
        return f'{indent}std::string {var_name};\n{indent}std::cout << "{escaped_prompt}";\n{indent}std::getline(std::cin, {var_name});'

    required_headers = {'<iostream>', '<string>'}
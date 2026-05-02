import re
from scrap.core.handler_base import StatementHandler, strip_comments

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
        # Declare the variable as std::string, then output the prompt and read input
        return (f'{indent}std::string {var};\n'
                f'{indent}std::cout << "{escaped}";\n'
                f'{indent}std::getline(std::cin, {var});')

    required_headers = {'<iostream>', '<string>'}
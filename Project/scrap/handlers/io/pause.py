import re
from scrap.core.handler_base import StatementHandler, strip_comments

class PauseHandler(StatementHandler):
    keywords = ['pause']

    def can_handle(self, line):
        stripped = line.strip()
        return stripped.startswith('pause')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^pause(?:\s+"([^"]*)")?\s*$', line)
        if not m:
            raise SyntaxError("Expected: pause or pause \"message\"")
        message = m.group(1)
        return ('PAUSE', message), start_index + 1

    def generate(self, node, indent=''):
        message = node[1]
        lines = []
        if message is not None:
            escaped = message.replace('\\', '\\\\').replace('"', '\\"')
            lines.append(f'{indent}printf("{escaped}");')
        # Wait for Enter only – discard any other characters until newline
        lines.append(f'{indent}while (getchar() != \'\\n\');')
        return '\n'.join(lines)

    required_headers = {'<cstdio>'}
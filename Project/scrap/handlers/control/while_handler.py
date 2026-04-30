import re
from scrap.core.handler_base import StatementHandler, get_indent, parse_block_body, generate_deferred_lines, strip_comments
from scrap.core.utils import resolve_dotted_calls

class WhileHandler(StatementHandler):
    keywords = ['while ']

    def can_handle(self, line):
        return bool(re.match(r'^while\s+.+\s*:\s*$', line.strip()))

    def parse(self, lines, start_index):
        first = lines[start_index].rstrip('\n')
        base_indent = get_indent(first)
        stripped = strip_comments(first).strip()
        m = re.match(r'^while\s+(.+)\s*:\s*$', stripped)
        if not m:
            raise SyntaxError("Expected: while condition:")
        cond = m.group(1).strip()
        body, deferred, next_i = parse_block_body(lines, start_index + 1, base_indent)
        return ('WHILE', (cond, body, deferred)), next_i

    def generate(self, node, indent=''):
        cond, body, deferred = node[1]
        cond = resolve_dotted_calls(cond)
        lines = [f'{indent}while ({cond}) {{']
        inner = indent + '    '
        for h, n in body:
            lines.append(h.generate(n, inner))
        lines.extend(generate_deferred_lines(deferred, inner))
        lines.append(f'{indent}}}')
        return '\n'.join(lines)
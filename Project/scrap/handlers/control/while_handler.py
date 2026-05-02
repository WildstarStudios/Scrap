import re
from scrap.core.handler_base import StatementHandler, get_indent, strip_comments, parse_block_body, generate_deferred_lines
from scrap.core.utils import resolve_dotted_call_with_handle

class WhileHandler(StatementHandler):
    keywords = ['while ']

    def can_handle(self, line):
        return bool(re.match(r'^while\s+.+\s*:\s*$', line.strip()))

    def parse(self, lines, start_index):
        first = lines[start_index].rstrip('\n')
        base_indent = get_indent(first)
        stripped = strip_comments(first).strip()
        m = re.match(r'^while\s+(.+?)\s*:\s*$', stripped)
        if not m:
            raise SyntaxError("Invalid while loop")
        cond = m.group(1).strip()
        i = start_index + 1
        body, deferred, next_i = parse_block_body(lines, i, base_indent)
        return ('WHILE', (cond, body, deferred)), next_i

    def generate(self, node, indent=''):
        cond, body, deferred = node[1]
        cond = resolve_dotted_call_with_handle(cond)
        lines = [f'{indent}while ({cond}) {{']
        inner = indent + '    '
        for h, n in body:
            lines.append(h.generate(n, inner))
        lines.extend(generate_deferred_lines(deferred, inner))
        lines.append(f'{indent}}}')
        return '\n'.join(lines)
import re
from scrap.core.handler_base import StatementHandler, get_indent, parse_block_body, generate_deferred_lines, strip_comments
from scrap.core.optimized_code import generate_optimized_ratio_block

class RepeatHandler(StatementHandler):
    keywords = ['repeat ']

    def can_handle(self, line):
        return bool(re.match(r'^repeat \d+\s*:\s*$', line.strip()))

    def parse(self, lines, start_index):
        first = lines[start_index].rstrip('\n')
        base_indent = get_indent(first)
        stripped = strip_comments(first).strip()
        m = re.match(r'^repeat (\d+)\s*:\s*$', stripped)
        if not m:
            raise SyntaxError("Expected: repeat <count>:")
        count = int(m.group(1))
        body, deferred, next_i = parse_block_body(lines, start_index + 1, base_indent)
        return ('REPEAT', (count, body, deferred)), next_i

    def generate(self, node, indent=''):
        count, body, deferred = node[1]
        lines = [f'{indent}for (int __i = 0; __i < {count}; ++__i) {{']
        inner = indent + '    '
        for h, n in body:
            if h is None and n[0] == 'OPTIMIZED_RATIO':
                lines.extend(generate_optimized_ratio_block(n[1], inner))
            else:
                lines.append(h.generate(n, inner))
        lines.extend(generate_deferred_lines(deferred, inner))
        lines.append(f'{indent}}}')
        return '\n'.join(lines)
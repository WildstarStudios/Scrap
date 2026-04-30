import re
from scrap.core.handler_base import StatementHandler, get_indent, parse_block_body, generate_deferred_lines, strip_comments

class ForRangeHandler(StatementHandler):
    keywords = []  # custom can_handle

    def can_handle(self, line):
        return bool(re.match(r'^for\s+[a-zA-Z_]\w*\s+in\s+range\(.+\)\s*:\s*$', line.strip()))

    def parse(self, lines, start_index):
        first = lines[start_index].rstrip('\n')
        base_indent = get_indent(first)
        stripped = strip_comments(first).strip()
        m = re.match(r'^for\s+([a-zA-Z_]\w*)\s+in\s+range\(([^)]+)\)\s*:\s*$', stripped)
        if not m:
            raise SyntaxError("Expected: for var in range([start,] stop[, step]):")
        var_name = m.group(1)
        args_str = m.group(2).strip()
        args = [a.strip() for a in args_str.split(',')]
        if len(args) == 1:
            start, stop, step = '0', args[0], '1'
        elif len(args) == 2:
            start, stop, step = args[0], args[1], '1'
        elif len(args) == 3:
            start, stop, step = args
        else:
            raise SyntaxError("range takes 1-3 arguments")
        body, deferred, next_i = parse_block_body(lines, start_index + 1, base_indent)
        return ('FOR_RANGE', (var_name, start, stop, step, body, deferred)), next_i

    def generate(self, node, indent=''):
        var, start, stop, step, body, deferred = node[1]
        lines = [f'{indent}for (int {var} = {start}; {var} < {stop}; {var} += {step}) {{']
        inner = indent + '    '
        for h, n in body:
            lines.append(h.generate(n, inner))
        lines.extend(generate_deferred_lines(deferred, inner))
        lines.append(f'{indent}}}')
        return '\n'.join(lines)
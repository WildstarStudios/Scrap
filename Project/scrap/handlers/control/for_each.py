import re
from scrap.core.handler_base import StatementHandler, get_indent, parse_block_body, generate_deferred_lines, strip_comments

class ForEachHandler(StatementHandler):
    keywords = ['for ']

    def can_handle(self, line):
        stripped = line.strip()
        return bool(re.match(r'^for\s+[a-zA-Z_]\w*\s+in\s+.+\s*:\s*$', stripped)) and 'range(' not in stripped

    def parse(self, lines, start_index):
        first = lines[start_index].rstrip('\n')
        base_indent = get_indent(first)
        stripped = strip_comments(first).strip()
        m = re.match(r'^for\s+([a-zA-Z_]\w*)\s+in\s+(.+)\s*:\s*$', stripped)
        if not m:
            raise SyntaxError("Expected: for var in container:")
        var_name = m.group(1)
        container = m.group(2).strip()
        body, deferred, next_i = parse_block_body(lines, start_index + 1, base_indent)
        return ('FOR_EACH', (var_name, container, body, deferred)), next_i

    def generate(self, node, indent=''):
        var, container, body, deferred = node[1]
        lines = [f'{indent}for (auto& {var} : {container}) {{']
        inner = indent + '    '
        for h, n in body:
            lines.append(h.generate(n, inner))
        lines.extend(generate_deferred_lines(deferred, inner))
        lines.append(f'{indent}}}')
        return '\n'.join(lines)
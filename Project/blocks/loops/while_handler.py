import re
from statements import StatementHandler, parse_block_body, get_handlers, suggest_fix, strip_comments, generate_deferred_lines

class WhileHandler(StatementHandler):
    keywords = ['while ']

    def can_handle(self, line):
        return bool(re.match(r'^while\s+.+\s*:\s*$', line.strip()))

    def parse(self, lines, start_index):
        def get_indent(line):
            return len(line) - len(line.lstrip())

        first_line = lines[start_index].rstrip('\n')
        base_indent = get_indent(first_line)
        stripped = strip_comments(first_line).strip()

        m = re.match(r'^while\s+(.+)\s*:\s*$', stripped)
        if not m:
            raise SyntaxError("Expected: while <condition>:")
        condition = m.group(1)

        body_items, deferred_items, next_i = parse_block_body(lines, start_index + 1, base_indent)
        return ('WHILE', (condition, body_items, deferred_items)), next_i

    def generate(self, node, indent=''):
        condition, body_items, deferred_items = node[1]
        lines_out = [f'{indent}while ({condition}) {{']
        inner_indent = indent + '    '

        for item in body_items:
            if isinstance(item, tuple):
                if len(item) == 2 and isinstance(item[0], int):
                    line_num, stmt = item
                    found = False
                    for h in get_handlers():
                        if h.can_handle(stmt):
                            node_inner, _ = h.parse([stmt], 0)
                            lines_out.append(h.generate(node_inner, inner_indent))
                            found = True
                            break
                    if not found:
                        suggestion = suggest_fix(stmt)
                        raise SyntaxError(f"Line {line_num}: Unknown statement '{stmt}'. {suggestion}")
                else:
                    h, node_inner = item
                    lines_out.append(h.generate(node_inner, inner_indent))
            else:
                for h in get_handlers():
                    if h.can_handle(item):
                        node_inner, _ = h.parse([item], 0)
                        lines_out.append(h.generate(node_inner, inner_indent))
                        break
                else:
                    suggestion = suggest_fix(item)
                    raise SyntaxError(f"Unknown statement inside while: {item}. {suggestion}")

        lines_out.extend(generate_deferred_lines(deferred_items, inner_indent))
        lines_out.append(f'{indent}}}')
        return '\n'.join(lines_out)

    required_headers = set()
import re
from statements import StatementHandler, parse_block_body, get_handlers, suggest_fix, strip_comments

class IfHandler(StatementHandler):
    keywords = ['if ']

    def can_handle(self, line):
        return bool(re.match(r'^if\s+.+\s+then\s*:\s*$', line.strip())) or \
               bool(re.match(r'^if\s+.+\s*:\s*$', line.strip()))

    def parse(self, lines, start_index):
        def get_indent(line):
            return len(line) - len(line.lstrip())

        first_line = lines[start_index].rstrip('\n')
        base_indent = get_indent(first_line)
        stripped = strip_comments(first_line).strip()

        m = re.match(r'^if\s+(.+?)(?:\s+then)?\s*:\s*$', stripped)
        if not m:
            raise SyntaxError("Expected: if <condition> [then] :")
        condition = m.group(1).strip()

        branches = []
        current_cond = condition
        current_body = []
        i = start_index + 1
        while i < len(lines):
            raw_line = lines[i]
            stripped_line = strip_comments(raw_line).strip()
            if not stripped_line:
                i += 1
                continue
            indent = get_indent(raw_line)

            if indent == base_indent:
                # elif
                if stripped_line.startswith('elif ') and stripped_line.endswith(':'):
                    branches.append((current_cond, current_body))
                    m2 = re.match(r'^elif\s+(.+?)(?:\s+then)?\s*:\s*$', stripped_line)
                    if not m2:
                        raise SyntaxError("Expected: elif <condition> [then] :")
                    current_cond = m2.group(1).strip()
                    current_body = []
                    i += 1
                    continue
                # else
                elif stripped_line.startswith('else') and stripped_line.endswith(':'):
                    branches.append((current_cond, current_body))
                    current_cond = None
                    current_body = []
                    i += 1
                    continue
                else:
                    break
            elif indent > base_indent:
                body_items, i = parse_block_body(lines, i, base_indent)
                current_body.extend(body_items)
                continue
            else:
                break

        branches.append((current_cond, current_body))
        if not branches:
            raise SyntaxError("Empty if block")
        return ('IF', branches), i

    def generate(self, node, indent=''):
        branches = node[1]
        lines_out = []
        for idx, (cond, body_items) in enumerate(branches):
            if idx == 0:
                keyword = 'if'
            elif cond is None:
                keyword = 'else'
            else:
                keyword = 'else if'

            if cond is not None:
                lines_out.append(f'{indent}{keyword} ({cond}) {{')
            else:
                lines_out.append(f'{indent}{keyword} {{')

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
                        raise SyntaxError(f"Unknown statement inside if: {item}. {suggestion}")
            lines_out.append(f'{indent}}}')
        return '\n'.join(lines_out)

    required_headers = set()
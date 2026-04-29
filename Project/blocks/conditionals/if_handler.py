import re
from statements import StatementHandler, parse_block_body, get_handlers, suggest_fix, strip_comments, generate_deferred_lines, resolve_expression

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
        current_body = []   # will hold (body_items, deferred_items)
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
                body_items, deferred_items, i = parse_block_body(lines, i, base_indent)
                current_body.append((body_items, deferred_items))
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
        for idx, (cond, body_data) in enumerate(branches):
            all_body_items = []
            all_deferred = []
            for item in body_data:
                body_part, def_part = item
                all_body_items.append(body_part)
                all_deferred.extend(def_part)

            if idx == 0:
                keyword = 'if'
            elif cond is None:
                keyword = 'else'
            else:
                keyword = 'else if'

            if cond is not None:
                lines_out.append(f'{indent}{keyword} ({resolve_expression(cond)}) {{')
            else:
                lines_out.append(f'{indent}{keyword} {{')

            inner_indent = indent + '    '
            for body_part in all_body_items:
                for item in body_part:
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

            # Emit deferred statements
            lines_out.extend(generate_deferred_lines(all_deferred, inner_indent))

            lines_out.append(f'{indent}}}')
        return '\n'.join(lines_out)

    required_headers = set()
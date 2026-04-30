import re
from scrap.core.handler_base import StatementHandler, get_indent, parse_block_body, generate_deferred_lines, strip_comments
from scrap.core.utils import resolve_dotted_calls

class IfHandler(StatementHandler):
    keywords = ['if ', 'elif ', 'else']

    def can_handle(self, line):
        stripped = line.strip()
        return stripped.startswith(('if ', 'elif ')) or stripped == 'else:'

    def parse(self, lines, start_index):
        first_line = lines[start_index].rstrip('\n')
        base_indent = get_indent(first_line)
        stripped = strip_comments(first_line).strip()

        branches = []
        if stripped.startswith('if '):
            m = re.match(r'^if\s+(.+?)\s*:\s*$', stripped)
            if not m:
                raise SyntaxError("Expected: if condition:")
            cond = m.group(1).strip()
            current_cond = cond
            current_body = []
            i = start_index + 1
        else:
            raise SyntaxError("Expected if")

        while i < len(lines):
            raw = lines[i]
            stripped_line = strip_comments(raw).strip()
            if not stripped_line:
                i += 1
                continue
            indent = get_indent(raw)
            if indent == base_indent:
                if stripped_line.startswith('elif '):
                    branches.append((current_cond, current_body))
                    m = re.match(r'^elif\s+(.+?)\s*:\s*$', stripped_line)
                    if not m:
                        raise SyntaxError("Expected: elif condition:")
                    current_cond = m.group(1).strip()
                    current_body = []
                    i += 1
                    continue
                elif stripped_line == 'else:':
                    branches.append((current_cond, current_body))
                    current_cond = None
                    current_body = []
                    i += 1
                    continue
                else:
                    break
            elif indent > base_indent:
                body, deferred, i = parse_block_body(lines, i, base_indent)
                current_body.append((body, deferred))
                continue
            else:
                break

        branches.append((current_cond, current_body))
        return ('IF', branches), i

    def generate(self, node, indent=''):
        branches = node[1]
        lines = []
        for idx, (cond, body_data) in enumerate(branches):
            if idx == 0:
                kw = 'if'
            elif cond is None:
                kw = 'else'
            else:
                kw = 'else if'
            # Convert `not`/`and`/`or` and resolve dotted calls
            if cond:
                cond = resolve_dotted_calls(cond)
                cond = cond.replace('not ', '!')
                cond = cond.replace(' and ', ' && ')
                cond = cond.replace(' or ', ' || ')
                lines.append(f'{indent}{kw} ({cond}) {{')
            else:
                lines.append(f'{indent}{kw} {{')
            inner = indent + '    '
            for body, deferred in body_data:
                for h, n in body:
                    lines.append(h.generate(n, inner))
                lines.extend(generate_deferred_lines(deferred, inner))
            lines.append(f'{indent}}}')
        return '\n'.join(lines)
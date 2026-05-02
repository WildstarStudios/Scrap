import re
from scrap.core.handler_base import StatementHandler, get_indent, strip_comments, parse_block_body, generate_deferred_lines
from scrap.core.utils import resolve_dotted_call_with_handle, auto_fill_resolved_call, resolve_string_comparison
from scrap.core.optimized_code import generate_optimized_ratio_block

class IfHandler(StatementHandler):
    keywords = ['if ']

    def can_handle(self, line):
        stripped = line.strip()
        return stripped.startswith('if ') or stripped.startswith('elif ') or stripped == 'else:'

    def parse(self, lines, start_index):
        base_indent = get_indent(lines[start_index])
        i = start_index
        branches = []

        raw = lines[i].rstrip('\n')
        stripped = strip_comments(raw).strip()
        if not stripped.startswith('if '):
            raise SyntaxError("Expected 'if'")
        m = re.match(r'^if\s+(.+?)\s*:\s*$', stripped)
        if not m:
            raise SyntaxError("Invalid if")
        cond = m.group(1).strip()
        i += 1
        body, deferred, i = parse_block_body(lines, i, base_indent)
        branches.append((cond, [(body, deferred)]))

        while i < len(lines):
            raw = lines[i].rstrip('\n')
            stripped = strip_comments(raw).strip()
            if not stripped:
                i += 1
                continue
            indent = get_indent(raw)
            if indent != base_indent:
                break

            if stripped.startswith('elif '):
                m = re.match(r'^elif\s+(.+?)\s*:\s*$', stripped)
                if not m:
                    raise SyntaxError("Invalid elif")
                cond = m.group(1).strip()
                i += 1
                body, deferred, i = parse_block_body(lines, i, base_indent)
                branches.append((cond, [(body, deferred)]))
            elif stripped == 'else:':
                i += 1
                body, deferred, i = parse_block_body(lines, i, base_indent)
                branches.append((None, [(body, deferred)]))
                break
            else:
                break

        return ('IF', branches), i

    def generate(self, node, indent=''):
        branches = node[1]
        code = []
        for idx, (cond, body_data) in enumerate(branches):
            if idx == 0:
                kw = 'if'
            elif cond is None:
                kw = 'else'
            else:
                kw = 'else if'
            if cond:
                cond = resolve_dotted_call_with_handle(cond)
                cond = auto_fill_resolved_call(cond)
                cond = resolve_string_comparison(cond)
                cond = cond.replace('not ', '!').replace(' and ', ' && ').replace(' or ', ' || ')
                code.append(f'{indent}{kw} ({cond}) {{')
            else:
                code.append(f'{indent}{kw} {{')
            inner = indent + '    '
            for body, deferred in body_data:
                for h, n in body:
                    if h is None and n[0] == 'OPTIMIZED_RATIO':
                        code.extend(generate_optimized_ratio_block(n[1], inner))
                    else:
                        code.append(h.generate(n, inner))
                code.extend(generate_deferred_lines(deferred, inner))
            code.append(f'{indent}}}')
        return '\n'.join(code)
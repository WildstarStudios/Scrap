import re
from scrap.core.handler_base import StatementHandler, get_indent, strip_comments, parse_block_body, generate_deferred_lines, get_handlers
from scrap.core.utils import to_cpp_type
from scrap.core.optimized_code import generate_optimized_ratio_block

class FuncHandler(StatementHandler):
    keywords = ['func ']

    def can_handle(self, line):
        return line.strip().startswith('func ')

    def parse(self, lines, start_index):
        first = lines[start_index].rstrip('\n')
        base_indent = get_indent(first)
        stripped = strip_comments(first).strip()
        m = re.match(r'^func\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*(?:as\s+([a-zA-Z_]\w*(?:[*&])*))?\s*:\s*$', stripped)
        if not m:
            raise SyntaxError("Invalid function definition")
        name = m.group(1)
        params_str = m.group(2).strip()
        ret_type = m.group(3) if m.group(3) else 'void'
        params = []
        if params_str:
            for p in params_str.split(','):
                p = p.strip()
                if not p:
                    continue
                pm = re.match(r'^([a-zA-Z_]\w*)\s*(?:as\s+([a-zA-Z_]\w*(?:[*&])*))?$', p)
                if pm:
                    params.append((pm.group(1), pm.group(2) if pm.group(2) else 'auto'))
                else:
                    raise SyntaxError(f"Bad parameter: {p}")
        body, deferred, next_i = parse_block_body(lines, start_index + 1, base_indent)
        return ('FUNC', (name, params, ret_type, body, deferred)), next_i

    def generate_function(self, node):
        name, params, ret_type, body, deferred = node[1]
        if name == 'main':
            cpp_name = 'user_main'
        else:
            cpp_name = name
        cpp_params = ', '.join(f'{to_cpp_type(pt)} {pn}' for pn, pt in params)
        lines = [f'{to_cpp_type(ret_type)} {cpp_name}({cpp_params}) {{']
        inner = '    '
        for h, n in body:
            if h is None and n[0] == 'OPTIMIZED_RATIO':
                lines.extend(generate_optimized_ratio_block(n[1], inner))
            else:
                lines.append(h.generate(n, inner))
        lines.extend(generate_deferred_lines(deferred, inner))
        lines.append('}')
        return '\n'.join(lines)

    def generate(self, node, indent=''):
        return ''   # function definitions are emitted separately
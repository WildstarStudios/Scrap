import re
from scrap.core.handler_base import StatementHandler, parse_block_body, generate_deferred_lines, strip_comments
from scrap.core.utils import to_cpp_type

class FuncHandler(StatementHandler):
    keywords = ['func ']

    def can_handle(self, line):
        return line.strip().startswith('func ')

    def parse(self, lines, start_index):
        first = lines[start_index].rstrip('\n')
        base_indent = len(first) - len(first.lstrip())
        stripped = strip_comments(first).strip()
        # Return type is now introduced by 'as' (optional, defaults to void)
        m = re.match(r'^func\s+([a-zA-Z_]\w*)\s*\(([^)]*)\)\s*(?:as\s+([a-zA-Z_]\w*(?:[*&])*))?\s*:\s*$', stripped)
        if not m:
            raise SyntaxError("Expected: func name(params) [as return_type]:")
        name = m.group(1)
        params_str = m.group(2).strip()
        return_type = m.group(3) if m.group(3) else 'void'
        params = []
        if params_str:
            for p in params_str.split(','):
                p = p.strip()
                if not p:
                    continue
                pm = re.match(r'^([a-zA-Z_]\w*)\s*(?:as\s+([a-zA-Z_]\w*(?:[*&])*))?$', p)
                if pm:
                    pname = pm.group(1)
                    ptype = pm.group(2) if pm.group(2) else 'auto'
                    params.append((pname, ptype))
                else:
                    raise SyntaxError(f"Invalid parameter: {p}")
        body, deferred, next_i = parse_block_body(lines, start_index + 1, base_indent)
        return ('FUNC', (name, params, return_type, body, deferred)), next_i

    def forward_declaration(self, node):
        name, params, ret_type, _, _ = node[1]
        if name == 'main':
            name = 'user_main'
        cpp_params = ', '.join(f'{to_cpp_type(pt)} {pn}' for pn, pt in params)
        return f'{to_cpp_type(ret_type)} {name}({cpp_params});'

    def generate_function(self, node):
        name, params, ret_type, body, deferred = node[1]
        if name == 'main':
            name = 'user_main'
        cpp_params = ', '.join(f'{to_cpp_type(pt)} {pn}' for pn, pt in params)
        lines = [f'{to_cpp_type(ret_type)} {name}({cpp_params}) {{']
        inner = '    '
        for h, n in body:
            lines.append(h.generate(n, inner))
        lines.extend(generate_deferred_lines(deferred, inner))
        lines.append('}')
        return '\n'.join(lines)

    def generate(self, node, indent=''):
        return ''
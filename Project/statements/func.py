import re
from . import StatementHandler, parse_block_body, get_handlers, strip_comments, generate_deferred_lines, set_var_type, clear_var_types

class FuncHandler(StatementHandler):
    keywords = ['func ']

    def can_handle(self, line):
        return line.strip().startswith('func ')

    def parse(self, lines, start_index):
        def get_indent(line):
            return len(line) - len(line.lstrip())

        first_line = lines[start_index].rstrip('\n')
        base_indent = get_indent(first_line)
        stripped = strip_comments(first_line).strip()

        m = re.match(r'^func\s+([a-zA-Z_]\w*)\s*\((.*?)\)\s*(?:as\s+([a-zA-Z_]\w*(?:[*&])*))?\s*:\s*$', stripped)
        if not m:
            raise SyntaxError("Expected: func name(param as type, ...) [as return_type]:")

        name = m.group(1)
        params_str = m.group(2).strip()
        return_type = m.group(3) if m.group(3) else 'void'

        params = []
        if params_str:
            for param in params_str.split(','):
                param = param.strip()
                if not param:
                    continue
                p = re.match(r'^([a-zA-Z_]\w*)\s+as\s+([a-zA-Z_]\w*(?:[*&])*)$', param)
                if not p:
                    raise SyntaxError(f"Invalid parameter: {param}. Expected 'name as type'")
                params.append((p.group(1), p.group(2)))

        body_items, deferred_items, next_i = parse_block_body(lines, start_index + 1, base_indent)

        return ('FUNC', (name, params, return_type, body_items, deferred_items)), next_i

    def generate(self, node, indent=''):
        return ''

    def forward_declaration(self, node):
        name, params, return_type, _, _ = node[1]
        if name == 'main':
            name = 'user_main'
        param_decls = []
        for pname, ptype in params:
            param_decls.append(f"{self._to_cpp_type(ptype)} {pname}")
        cpp_return = self._to_cpp_type(return_type)
        return f"{cpp_return} {name}({', '.join(param_decls)});"

    def generate_function(self, node, indent=''):
        name, params, return_type, body_items, deferred_items = node[1]
        if name == 'main':
            name = 'user_main'

        clear_var_types()
        for pname, ptype in params:
            cpp_type = self._to_cpp_type(ptype)
            set_var_type(pname, cpp_type)

        cpp_params = []
        for pname, ptype in params:
            cpp_params.append(f"{self._to_cpp_type(ptype)} {pname}")

        lines = [f"{self._to_cpp_type(return_type)} {name}({', '.join(cpp_params)}) {{"]
        inner_indent = '    '

        body_code = []
        deferred_nodes = []
        for item in body_items:
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], int):
                line_num, stmt = item
                found = False
                for h in get_handlers():
                    if h.can_handle(stmt):
                        node_inner, _ = h.parse([stmt], 0)
                        if node_inner[0] == 'DEFER':
                            deferred_nodes.append(node_inner)
                        else:
                            body_code.append(h.generate(node_inner, inner_indent))
                        found = True
                        break
                if not found:
                    from . import suggest_fix
                    suggestion = suggest_fix(stmt)
                    raise SyntaxError(f"Line {line_num}: Unknown statement '{stmt}'. {suggestion}")
            else:
                h, node_inner = item
                if node_inner[0] == 'DEFER':
                    deferred_nodes.append(node_inner)
                else:
                    body_code.append(h.generate(node_inner, inner_indent))

        lines.extend(body_code)
        lines.extend(generate_deferred_lines(deferred_nodes, inner_indent))
        lines.append("}")
        return '\n'.join(lines)

    def _to_cpp_type(self, scrap_type):
        mapping = {
            'int': 'int',
            'float': 'double',
            'String': 'std::string',
            'bool': 'bool',
            'void': 'void',
        }
        base_type = scrap_type.rstrip('*&').rstrip()
        if base_type in mapping:
            suffix = scrap_type[len(base_type):]
            return mapping[base_type] + suffix
        return scrap_type

    required_headers = set()
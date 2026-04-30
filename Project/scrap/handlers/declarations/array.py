import re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import to_cpp_type

class ArrayHandler(StatementHandler):
    keywords = ['array ']

    def can_handle(self, line):
        return line.strip().startswith('array ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^array\s+([a-zA-Z_]\w*)\s*(?:as\s+([a-zA-Z_]\w*))?\s*=\s*\[([^\]]*)\]$', line)
        if not m:
            raise SyntaxError("Expected: array name [as Type] = [elem1, elem2, ...]")
        name = m.group(1)
        type_part = m.group(2)
        elements_raw = m.group(3).strip()
        elements = [e.strip() for e in elements_raw.split(',')] if elements_raw else []
        count = len(elements)
        if type_part:
            cpp_elem_type = to_cpp_type(type_part)
        else:
            if elements:
                elem = elements[0]
                if elem.startswith('"'):
                    cpp_elem_type = 'std::string'
                elif re.match(r'^-?\d+$', elem):
                    cpp_elem_type = 'int'
                else:
                    cpp_elem_type = 'double'
            else:
                cpp_elem_type = 'int'
        cpp_arr_type = f'std::array<{cpp_elem_type}, {count}>'
        return ('ARRAY', name, cpp_arr_type, elements), start_index + 1

    def generate(self, node, indent=''):
        name = node[1]
        arr_type = node[2]
        elements = node[3]
        init_list = '{' + ', '.join(elements) + '}'
        return f'{indent}{arr_type} {name} = {init_list};'

    def required_headers(self, node=None):
        return {'<array>', '<string>'}
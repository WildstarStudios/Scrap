import re
from .. import StatementHandler, strip_comments, set_var_type

class ListVarHandler(StatementHandler):
    keywords = []   # dynamic detection

    def can_handle(self, line):
        stripped = line.strip()
        # Matches: list name as ElementType = [...]  OR  array name as ElementType = [...]
        return bool(re.match(r'^(list|array)\s+[a-zA-Z_]\w*\s+as\s+[a-zA-Z_]\w*\s*=\s*\[.*\]$', stripped))

    def parse(self, lines, start_index):
        # Collect multi-line declaration until brackets balance
        full_decl = lines[start_index].rstrip('\n')
        i = start_index + 1
        bracket_count = full_decl.count('[') - full_decl.count(']')
        while bracket_count > 0 and i < len(lines):
            raw = lines[i].rstrip('\n')
            full_decl += ' ' + raw
            bracket_count += raw.count('[') - raw.count(']')
            i += 1

        full_decl = strip_comments(full_decl).strip()
        m = re.match(r'^(list|array)\s+([a-zA-Z_]\w*)\s+as\s+([a-zA-Z_]\w*)\s*=\s*\[(.*?)\]\s*$', full_decl, re.DOTALL)
        if not m:
            raise SyntaxError("Expected: list name as ElementType = [elem1, elem2, ...]")
        kind = m.group(1)          # 'list' or 'array'
        name = m.group(2)
        element_type_scrap = m.group(3).strip()
        elements_raw = m.group(4).strip()

        # Convert element type to C++
        element_type_cpp = self._to_cpp_type(element_type_scrap)
        vector_type = f"std::vector<{element_type_cpp}>"

        elements = self._parse_elements(elements_raw)

        # Type-check each element
        for elem in elements:
            self._check_element_type(elem, element_type_scrap, element_type_cpp)

        set_var_type(name, vector_type)
        return ('DEFINE_LIST', name, vector_type, elements, kind), i

    def generate(self, node, indent=''):
        _, name, vector_type, elements, _ = node
        cpp_elements = []
        for e in elements:
            if e.startswith('"') and e.endswith('"'):
                escaped = e[1:-1].replace('\\', '\\\\').replace('"', '\\"')
                cpp_elements.append(f'"{escaped}"')
            elif e in ('true', 'false'):
                cpp_elements.append(e)
            else:
                cpp_elements.append(e)
        init_list = '{' + ', '.join(cpp_elements) + '}'
        return f'{indent}{vector_type} {name} = {init_list};'

    def required_headers(self, node=None):
        return {'<vector>', '<string>'}

    def _parse_elements(self, raw: str):
        if not raw.strip():
            return []
        elements = []
        current = []
        in_quotes = False
        for ch in raw:
            if ch == '"':
                in_quotes = not in_quotes
                current.append(ch)
            elif ch == ',' and not in_quotes:
                elements.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            elements.append(''.join(current).strip())
        return elements

    def _to_cpp_type(self, scrap_type: str) -> str:
        mapping = {
            'int': 'int',
            'float': 'double',
            'String': 'std::string',
            'bool': 'bool',
        }
        return mapping.get(scrap_type, scrap_type)

    def _check_element_type(self, elem: str, scrap_type: str, cpp_type: str):
        if scrap_type == 'String':
            if not (elem.startswith('"') and elem.endswith('"')):
                raise SyntaxError(f"Element '{elem}' must be a quoted string")
        elif scrap_type == 'int':
            if not re.match(r'^-?\d+$', elem):
                raise SyntaxError(f"Element '{elem}' is not an integer")
        elif scrap_type == 'float':
            if not re.match(r'^-?\d+\.?\d*$', elem):
                raise SyntaxError(f"Element '{elem}' is not a float")
        elif scrap_type == 'bool':
            if elem not in ('true', 'false'):
                raise SyntaxError(f"Element '{elem}' is not a boolean")
        # For other types (e.g., pointers) we trust the user
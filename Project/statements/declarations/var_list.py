import re
from .. import StatementHandler

class ListVarHandler(StatementHandler):
    keywords = []

    def can_handle(self, line):
        stripped = line.strip()
        return stripped.startswith('var ') and '= [' in stripped

    def parse(self, lines, start_index):
        # Collect lines until matching closing bracket
        full_decl = lines[start_index].rstrip('\n')
        i = start_index + 1
        bracket_count = full_decl.count('[') - full_decl.count(']')
        while bracket_count > 0 and i < len(lines):
            line = lines[i].rstrip('\n')
            full_decl += ' ' + line
            bracket_count += line.count('[') - line.count(']')
            i += 1

        # Now parse the full declaration (may span lines)
        m = re.match(r'^var\s+([a-zA-Z_]\w*)\s*(?:as\s+([^\s=]+))?\s*=\s*\[(.*?)\]\s*(?:\s+as\s+([^\s]+))?\s*$', full_decl, re.DOTALL)
        if not m:
            raise SyntaxError("Expected: var name [as Type] = [elem1, ...]  or  var name = [elem1, ...] as Type")
        name = m.group(1)
        type_before = m.group(2)
        elements_raw = m.group(3).strip()
        type_after = m.group(4)

        type_hint = type_after if type_after else type_before
        elements = self._parse_elements(elements_raw)

        if elements:
            element_type = self._infer_element_type(elements)
        else:
            if not type_hint:
                raise SyntaxError("Empty list requires explicit type: use 'as List<type>' before or after []")
            inner_match = re.match(r'^List<(.+)>$', type_hint.strip())
            if not inner_match:
                raise SyntaxError("Type hint for list must be List<element_type>")
            element_type = self._normalize_type(inner_match.group(1))

        vector_type = f"std::vector<{element_type}>"

        if type_hint:
            hint_match = re.match(r'^List<(.+)>$', type_hint.strip())
            if hint_match:
                provided = self._normalize_type(hint_match.group(1))
                if provided != element_type:
                    raise SyntaxError(f"Type mismatch: List<{provided}> but elements are {element_type}")
            else:
                raise SyntaxError("Type hint must be List<element_type>")

        return ('DEFINE_LIST', name, vector_type, elements), i

    def generate(self, node, indent=''):
        _, name, vector_type, elements = node
        cpp_elements = []
        for e in elements:
            if e.startswith('"') and e.endswith('"'):
                escaped = e[1:-1].replace('\\', '\\\\').replace('"', '\\"')
                cpp_elements.append(f'"{escaped}"')
            elif e.isdigit() or (e[0]=='-' and e[1:].isdigit()):
                cpp_elements.append(e)
            elif re.match(r'^-?\d+\.\d+$', e):
                cpp_elements.append(e)
            else:
                cpp_elements.append(e)
        init_list = '{' + ', '.join(cpp_elements) + '}'
        return f'{indent}{vector_type} {name} = {init_list};'

    def required_headers(self, node=None):
        return {'<vector>'}

    def _parse_elements(self, raw):
        if not raw.strip():
            return []
        elements = []
        current = ''
        in_quotes = False
        for ch in raw:
            if ch == '"':
                in_quotes = not in_quotes
                current += ch
            elif ch == ',' and not in_quotes:
                elements.append(current.strip())
                current = ''
            else:
                current += ch
        if current.strip():
            elements.append(current.strip())
        return elements

    def _infer_element_type(self, elements):
        first = elements[0]
        if first.startswith('"') and first.endswith('"'):
            return 'std::string'
        elif re.match(r'^-?\d+\.\d+$', first):
            return 'double'
        elif first.isdigit() or (first[0]=='-' and first[1:].isdigit()):
            return 'int'
        else:
            return 'int'

    def _normalize_type(self, t):
        t = t.strip()
        if t == 'string':
            return 'std::string'
        return t
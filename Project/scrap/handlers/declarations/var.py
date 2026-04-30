import re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import (
    infer_type_from_value, to_cpp_type, resolve_dotted_calls,
    get_owned_wrapper
)

class VarHandler(StatementHandler):
    keywords = ['var ']

    def can_handle(self, line):
        return line.strip().startswith('var ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^var\s+([a-zA-Z_]\w*)\s*(?:as\s+([a-zA-Z_]\w*(?:[*&])*))?\s*(?:=\s*(.+))?$', line)
        if not m:
            raise SyntaxError("Expected: var name [as Type] [= value]")
        name, explicit_type, value = m.groups()
        if value:
            value = value.strip()
            # Resolve dotted calls using the standard function
            value = resolve_dotted_calls(value)

            # SAFETY NET: if a dot still exists before '(' (e.g. ImGui.CreateContext)
            # force it to :: because some patterns may slip through.
            value = re.sub(r'([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)\s*\(', r'\1::\2(', value)

        if explicit_type:
            cpp_type = to_cpp_type(explicit_type)
            if value is None:
                return ('VAR_DECL', name, cpp_type, None), start_index + 1
            return ('VAR_INIT', name, cpp_type, value), start_index + 1
        else:
            if value is None:
                raise SyntaxError("var without type requires an initialiser")
            # Basic inference (will be overridden if it's an owned‑creator call)
            cpp_type = infer_type_from_value(value)

            # Now check if the resolved value is a function call (e.g. ImGui::CreateContext())
            m_call = re.match(r'^([a-zA-Z_][\w:]*)\((.*)\)$', value)
            if m_call:
                func_name = m_call.group(1)          # already qualified, e.g. ImGui::CreateContext
                short_name = func_name.split('::')[-1]
                wrapper = get_owned_wrapper(short_name)
                if wrapper:
                    cpp_type = wrapper
            return ('VAR_INIT', name, cpp_type, value), start_index + 1

    def generate(self, node, indent=''):
        kind = node[0]
        name = node[1]
        if kind == 'VAR_DECL':
            return f'{indent}{node[2]} {name};'
        elif kind == 'VAR_INIT':
            cpp_type = node[2]
            value = node[3]                 # already resolved

            # If the value is a function call that should be a smart pointer
            m_call = re.match(r'^([a-zA-Z_][\w:]*)\((.*)\)$', value)
            if m_call:
                func_name = m_call.group(1)
                short_name = func_name.split('::')[-1]
                wrapper = get_owned_wrapper(short_name)
                if wrapper:
                    args = m_call.group(2)
                    # Smart pointer initialisation: Wrapper var( function_call )
                    return f'{indent}{cpp_type} {name}({func_name}({args}));'

            # Strings and ordinary expressions
            if value.startswith('"') and value.endswith('"'):
                escaped = value[1:-1].replace('\\', '\\\\').replace('"', '\\"')
                return f'{indent}{cpp_type} {name} = "{escaped}";'
            return f'{indent}{cpp_type} {name} = {value};'

    def check_semantics(self, node, symbols):
        kind = node[0]
        name = node[1]
        cpp_type = node[2]
        if kind == 'VAR_DECL':
            symbols.declare(name, cpp_type)
        elif kind == 'VAR_INIT':
            symbols.declare(name, cpp_type)
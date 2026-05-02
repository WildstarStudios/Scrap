import re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import (
    infer_type_from_value, to_cpp_type, resolve_dotted_calls,
    get_owned_wrapper, get_outparam_creator_info, register_variable_library,
    register_variable_type, is_dynamic_string
)

class VarHandler(StatementHandler):
    keywords = ['var ']
    _raw_counter = 0

    def can_handle(self, line):
        return line.strip().startswith('var ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(
            r'^var\s+([a-zA-Z_]\w*)\s*(?:as\s+([a-zA-Z_]\w*(?:[*&])*))?\s*(?:=\s*(.+))?$',
            line
        )
        if not m:
            raise SyntaxError(f"Invalid var declaration: {line}")
        name, explicit_type, value = m.groups()
        if value is not None:
            value = value.strip()
            value = resolve_dotted_calls(value)
        return ('VAR', name, explicit_type, value), start_index + 1

    def generate(self, node, indent=''):
        _, name, explicit_type, value = node
        if value is None:
            if explicit_type is None:
                raise SyntaxError("var without type requires an initialiser")
            cpp_type = to_cpp_type(explicit_type)
            register_variable_type(name, cpp_type)
            if cpp_type == 'string':
                return f'{indent}string {name}; string_init(&{name});'
            if cpp_type in ('int', 'double', 'bool', 'auto', 'char') or cpp_type.endswith('*') or cpp_type.endswith('&'):
                return f'{indent}{cpp_type} {name};'
            return f'{indent}{cpp_type} {name}{{}};'

        value = resolve_dotted_calls(value)

        # Determine type
        if explicit_type:
            cpp_type = to_cpp_type(explicit_type)
        else:
            m_call = re.match(r'^([a-zA-Z_][\w:]*)\((.*)\)$', value)
            if m_call:
                func_name = m_call.group(1)
                outparam_info = get_outparam_creator_info(func_name)
                if outparam_info:
                    base_type, deleter, alias = outparam_info
                    cpp_type = f'Unique{alias}{func_name}'
                else:
                    cpp_type = infer_type_from_value(value)
                    short_name = func_name.split('::')[-1]
                    wrapper = get_owned_wrapper(short_name)
                    if wrapper:
                        cpp_type = wrapper
            else:
                cpp_type = infer_type_from_value(value)

        # If initializer is a string literal
        if value.startswith('"') and value.endswith('"'):
            literal = value[1:-1]
            escaped = literal.replace('\\', '\\\\').replace('"', '\\"')
            if cpp_type == 'string':   # dynamic
                register_variable_type(name, 'string')
                return f'{indent}string {name}; string_init(&{name}); string_set(&{name}, "{escaped}");'
            else:   # static
                size = len(literal) + 1
                cpp_type = f'char[{size}]'
                register_variable_type(name, cpp_type, size)
                return f'{indent}{cpp_type} {name} = "{escaped}";'

        # Not a string literal
        register_variable_type(name, cpp_type)

        m_call = re.match(r'^([a-zA-Z_][\w:]*)\((.*)\)$', value)
        if m_call:
            func_name = m_call.group(1)
            args_str = m_call.group(2).strip()

            outparam_info = get_outparam_creator_info(func_name)
            if outparam_info:
                base_type, deleter, alias = outparam_info
                raw_var = f'__raw{VarHandler._raw_counter}'
                VarHandler._raw_counter += 1
                lines = []
                lines.append(f'{indent}{base_type}* {raw_var} = nullptr;')
                lines.append(f'{indent}{func_name}({args_str}, &{raw_var});')
                lines.append(f'{indent}auto {name} = std::unique_ptr<{base_type}, decltype(&{deleter})>({raw_var}, {deleter});')
                register_variable_library(name, alias)
                return '\n'.join(lines)

            short_name = func_name.split('::')[-1]
            wrapper = get_owned_wrapper(short_name)
            if wrapper:
                return f'{indent}{cpp_type} {name}({func_name}({args_str}));'

            return f'{indent}{cpp_type} {name} = {func_name}({args_str});'

        # Plain non‑string value
        return f'{indent}{cpp_type} {name} = {value};'
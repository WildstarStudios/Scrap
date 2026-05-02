from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import (
    resolve_dotted_call_with_handle, auto_fill_resolved_call,
    get_variable_type, is_dynamic_string, is_static_string
)
import re

class LogHandler(StatementHandler):
    keywords = ['log ']

    def can_handle(self, line):
        return line.strip().startswith('log ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        args_str = line[4:].strip()
        args = [a.strip() for a in args_str.split(',')]
        return ('LOG', args), start_index + 1

    def generate(self, node, indent=''):
        args = node[1]
        if not args:
            return f'{indent}puts("");'

        format_parts = []
        arg_vals = []
        for arg in args:
            resolved = resolve_dotted_call_with_handle(arg)
            if '(' in resolved:
                resolved = auto_fill_resolved_call(resolved)

            # Simple variable name?
            if re.match(r'^[a-zA-Z_]\w*$', resolved):
                if is_dynamic_string(resolved):
                    format_parts.append('%s')
                    arg_vals.append(f'string_c_str(&{resolved})')
                elif is_static_string(resolved):
                    format_parts.append('%s')
                    arg_vals.append(resolved)   # char array decays to pointer
                else:
                    vtype = get_variable_type(resolved)
                    if vtype == 'int':
                        format_parts.append('%d')
                        arg_vals.append(resolved)
                    elif vtype == 'double' or vtype == 'float':
                        format_parts.append('%f')
                        arg_vals.append(resolved)
                    else:
                        format_parts.append('%s')
                        arg_vals.append(resolved)
            elif resolved.startswith('"') and resolved.endswith('"'):
                format_parts.append('%s')
                arg_vals.append(resolved)
            else:
                # expression – assume const char*
                format_parts.append('%s')
                arg_vals.append(resolved)

        fmt_str = '"' + ' '.join(format_parts) + '\\n"'
        return f'{indent}printf({fmt_str}, {", ".join(arg_vals)});'

    required_headers = {'<cstdio>', '<cstring>', '<cstdlib>'}
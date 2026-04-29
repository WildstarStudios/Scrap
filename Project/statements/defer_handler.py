from . import StatementHandler, strip_comments, parse_function_call, wrap_c_args

class DeferHandler(StatementHandler):
    keywords = ['defer ']

    def can_handle(self, line):
        return line.strip().startswith('defer ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        deferred_stmt = line[6:].strip()   # everything after 'defer '
        if not deferred_stmt:
            raise SyntaxError("Expected statement after 'defer'")

        # Transform library aliases (dots → underscore) and auto .c_str()
        call_info = parse_function_call(deferred_stmt)
        if call_info:
            func, args, is_c = call_info
            args = wrap_c_args(args, is_c)
            transformed = f"{func}({', '.join(args)})"
            return ('DEFER', transformed), start_index + 1
        else:
            # Not a function call? Keep it as is.
            return ('DEFER', deferred_stmt), start_index + 1

    def generate(self, node, indent=''):
        # Defer lines are emitted later via generate_deferred_lines
        return ''
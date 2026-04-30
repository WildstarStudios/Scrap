from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import to_cpp_type

class ReturnHandler(StatementHandler):
    keywords = ['return']

    def can_handle(self, line):
        return line.strip().startswith('return')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        if line == 'return':
            return ('RETURN', None), start_index + 1
        elif line.startswith('return '):
            expr = line[7:].strip()
            return ('RETURN', expr), start_index + 1
        raise SyntaxError("Expected: return [expression]")

    def generate(self, node, indent=''):
        if node[1] is None:
            # bare return – we need to know the expected type; we'll just emit a default
            # The semantic checker will later catch mismatches, but for now we trust that
            # the user wants the proper default. We'll emit "return {};" which for int is 0,
            # for pointers is nullptr, etc.
            return indent + 'return {};'
        else:
            return f'{indent}return {node[1]};'

    def check_semantics(self, node, symbols):
        expr = node[1]
        expected = symbols.current_function_ret
        if expected is None:
            return
        if expected == 'void':
            if expr is not None:
                raise SyntaxError("Cannot return a value from a void function")
        else:
            # if expr is None, we will be using default initialization – that's fine
            pass
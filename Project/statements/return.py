from . import StatementHandler, strip_comments, resolve_expression

class ReturnHandler(StatementHandler):
    keywords = ['return ']

    def can_handle(self, line):
        return line.strip().startswith('return')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        if line == 'return':
            return ('RETURN', None), start_index + 1
        elif line.startswith('return '):
            expr = line[7:].strip()
            # Resolve any dot calls inside the return expression
            expr = resolve_expression(expr)
            return ('RETURN', expr), start_index + 1
        raise SyntaxError("Expected: return [expression]")

    def generate(self, node, indent=''):
        expr = node[1]
        if expr is None:
            return f'{indent}return;'
        else:
            return f'{indent}return {expr};'

    required_headers = set()
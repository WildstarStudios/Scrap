from . import StatementHandler, strip_comments

class BreakHandler(StatementHandler):
    keywords = ['break']

    def can_handle(self, line):
        return line.strip() == 'break'

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        if line != 'break':
            raise SyntaxError("Expected 'break'")
        return ('BREAK', None), start_index + 1

    def generate(self, node, indent=''):
        return f'{indent}break;'

    required_headers = set()

    # ---------- Semantic Check ----------
    def check_semantics(self, node, symbols):
        if symbols.loop_depth == 0:
            raise SyntaxError("'break' outside of loop")
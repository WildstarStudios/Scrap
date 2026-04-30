from scrap.core.handler_base import StatementHandler, strip_comments

class DeferHandler(StatementHandler):
    keywords = ['defer ']

    def can_handle(self, line):
        return line.strip().startswith('defer ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        stmt = line[6:].strip()
        if not stmt:
            raise SyntaxError("Expected statement after defer")
        return ('DEFER', stmt), start_index + 1

    def generate(self, node, indent=''):
        return ''
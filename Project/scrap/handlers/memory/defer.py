from scrap.core.handler_base import StatementHandler, strip_comments

class DeferHandler(StatementHandler):
    keywords = ['defer ']

    def can_handle(self, line):
        return line.strip().startswith('defer ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        stmt = line[6:].strip()
        return ('DEFER', stmt), start_index + 1

    def generate(self, node, indent=''):
        return ''   # emitted later via generate_deferred_lines
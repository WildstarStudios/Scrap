from . import StatementHandler

class CommentHandler(StatementHandler):
    keywords = ['--']

    def parse(self, lines, start_index):
        line = lines[start_index].strip()
        comment_text = line[2:].strip()
        return ('COMMENT', comment_text), start_index + 1

    def generate(self, node, indent=''):
        text = node[1]
        if text:
            return f'{indent}// {text}'
        else:
            return f'{indent}//'

    required_headers = set()
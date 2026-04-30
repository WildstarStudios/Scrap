from scrap.core.handler_base import StatementHandler, strip_comments

class LogHandler(StatementHandler):
    keywords = ['log ']

    def can_handle(self, line):
        return line.strip().startswith('log ')

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        args_str = line[4:].strip()
        args = self._split_args(args_str)
        return ('LOG', args), start_index + 1

    def generate(self, node, indent=''):
        args = node[1]
        parts = []
        for i, arg in enumerate(args):
            if i > 0:
                parts.append(' << " "')
            parts.append(f' << {arg}')
        chain = ''.join(parts)
        return f'{indent}std::cout{chain} << std::endl;'

    required_headers = {'<iostream>'}

    @staticmethod
    def _split_args(s):
        """Split arguments by comma, respecting quotes."""
        args = []
        current = []
        in_quotes = False
        for ch in s:
            if ch == '"':
                in_quotes = not in_quotes
                current.append(ch)
            elif ch == ',' and not in_quotes:
                args.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            args.append(''.join(current).strip())
        return args
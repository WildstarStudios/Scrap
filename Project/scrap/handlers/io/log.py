from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import resolve_dotted_call_with_handle, auto_fill_resolved_call

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
        parts = []
        for i, arg in enumerate(args):
            # Resolve dotted calls
            resolved = resolve_dotted_call_with_handle(arg)
            # Auto‑fill if it's a function call
            if '(' in resolved:
                resolved = auto_fill_resolved_call(resolved)
            if i > 0:
                parts.append(' << " "')
            parts.append(f' << {resolved}')
        chain = ''.join(parts)
        return f'{indent}std::cout{chain} << std::endl;'

    required_headers = {'<iostream>'}
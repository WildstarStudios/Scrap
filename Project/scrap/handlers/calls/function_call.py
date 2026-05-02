import re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import resolve_dotted_call_with_handle, auto_fill_arguments

class FunctionCallHandler(StatementHandler):
    keywords = []

    def can_handle(self, line):
        stripped = line.strip()
        if not re.match(r'^[a-zA-Z_][\w.]*\(', stripped):
            return False
        if stripped.startswith(('var ', 'list ', 'array ', 'if ', 'elif ', 'else',
                                'while ', 'for ', 'repeat ', 'func ', 'log ', 'ask ',
                                'pause', 'break', 'return', 'defer ', 'import lib')):
            return False
        if '=' in stripped or stripped.endswith(':'):
            return False
        return True

    def parse(self, lines, start_index):
        line = strip_comments(lines[start_index]).strip()
        m = re.match(r'^([a-zA-Z_][\w.]*)\((.*)\)$', line)
        if not m:
            raise SyntaxError("Invalid function call")
        func_name = m.group(1)
        args_str = m.group(2).strip()
        args = self._split_args(args_str)
        return ('CALL', func_name, args), start_index + 1

    def generate(self, node, indent=''):
        func_name, args = node[1], node[2]
        call_str = f'{func_name}({", ".join(args)})'
        resolved = resolve_dotted_call_with_handle(call_str)

        # Extract function name and argument list from resolved string,
        # using the same safe splitter that ignores commas inside strings/parens.
        m = re.match(r'^([a-zA-Z_]\w*)\(', resolved)
        if m:
            fn = m.group(1)
            # locate the matching closing parenthesis
            start = resolved.index('(')
            i = start + 1
            depth = 1
            in_str = False
            str_char = None
            while i < len(resolved) and depth > 0:
                c = resolved[i]
                if in_str:
                    if c == '\\' and i+1 < len(resolved):
                        i += 1
                    elif c == str_char:
                        in_str = False
                else:
                    if c == '"' or c == "'":
                        in_str = True
                        str_char = c
                    elif c == '(':
                        depth += 1
                    elif c == ')':
                        depth -= 1
                i += 1
            inner = resolved[start+1 : i-1].strip()
            # safe split
            arg_list = self._split_args(inner)
            # auto‑fill missing pointer arguments
            filled_args = auto_fill_arguments(fn, arg_list)
            resolved = f'{fn}({", ".join(filled_args)})'

        return f'{indent}{resolved};'

    @staticmethod
    def _split_args(s):
        args = []
        current = []
        parens = 0
        in_quotes = False
        for ch in s:
            if ch == '"':
                in_quotes = not in_quotes
                current.append(ch)
            elif ch == '(' and not in_quotes:
                parens += 1
                current.append(ch)
            elif ch == ')' and not in_quotes:
                parens -= 1
                current.append(ch)
            elif ch == ',' and not in_quotes and parens == 0:
                args.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            args.append(''.join(current).strip())
        return args
import re
from scrap.core.handler_base import StatementHandler, strip_comments
from scrap.core.utils import is_cpp_alias, resolve_alias, resolve_dotted_calls

class FunctionCallHandler(StatementHandler):
    keywords = []   # custom detection

    def can_handle(self, line):
        stripped = line.strip()
        # Must start with identifier (dotted allowed) followed by '('
        if not re.match(r'^[a-zA-Z_][\w.]*\(', stripped):
            return False
        # Exclude known statement starters
        if stripped.startswith((
            'var ', 'list ', 'array ', 'if ', 'elif ', 'else',
            'while ', 'for ', 'repeat ', 'func ', 'log ', 'ask ',
            'pause', 'break', 'return', 'defer ', 'import lib'
        )):
            return False
        # Exclude assignments and block starters
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
        resolved = self._resolve_dotted(func_name)
        # Resolve any dotted calls inside arguments as well
        args = [resolve_dotted_calls(a) for a in args]
        return f'{indent}{resolved}({", ".join(args)});'

    def _resolve_dotted(self, name):
        """ImGui.Begin -> ImGui::Begin (C++ namespace)"""
        if '.' in name:
            parts = name.split('.')
            alias = parts[0]
            if is_cpp_alias(alias):
                namespace = resolve_alias(alias)
                return namespace + '::' + '::'.join(parts[1:])
        return name

    @staticmethod
    def _split_args(s):
        """Split arguments, respecting quotes and parentheses."""
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
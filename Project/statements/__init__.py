import re
import os

_handlers = []
_alias_map = {}

def register_handler(handler):
    _handlers.append(handler)

def get_handlers():
    return _handlers

def register_alias(alias, namespace):
    _alias_map[alias] = namespace

def resolve_alias(alias):
    return _alias_map.get(alias, alias)

def _split_args(raw_args):
    args = []
    current = ''
    in_quotes = False
    for ch in raw_args:
        if ch == '"':
            in_quotes = not in_quotes
            current += ch
        elif ch == ',' and not in_quotes:
            args.append(current.strip())
            current = ''
        else:
            current += ch
    args.append(current.strip())
    return args

def parse_function_call(expr):
    m = re.match(r'^([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)\((.+)\)$', expr)
    if m:
        alias = m.group(1)
        func = m.group(2)
        raw_args = m.group(3)
        args = _split_args(raw_args)
        full_namespace = resolve_alias(alias)
        full_func = f'{full_namespace}::{func}'
        return full_func, args

    m = re.match(r'^([a-zA-Z_]\w*)\((.+)\)$', expr)
    if m:
        func = m.group(1)
        raw_args = m.group(2)
        args = _split_args(raw_args)
        return func, args

    return None

def is_c_header(header_path):
    ext = os.path.splitext(header_path)[1].lower()
    return ext in ('.h', '.c')

def suggest_fix(line):
    line = line.strip()
    if line.startswith('set '):
        return "Use 'variable = expression' without 'set'. Example: " + line[4:]
    if '=' in line and not line.startswith(('var ', 'if ', 'while ', 'repeat ', 'for ', 'ask ', 'log ', 'free ', 'import ', 'pause', '--')):
        return "Assignment should use 'variable = expression'. Example: " + line
    return "Check the statement syntax."

def parse_block_body(lines, start_index, base_indent):
    def get_indent(line):
        return len(line) - len(line.lstrip())

    body = []
    i = start_index
    handlers = get_handlers()
    while i < len(lines):
        raw_line = lines[i]
        stripped = raw_line.strip()
        if not stripped:
            i += 1
            continue
        indent = get_indent(raw_line)
        if indent <= base_indent:
            break

        handled = False
        for h in handlers:
            if h.can_handle(stripped):
                node, i = h.parse(lines, i)
                body.append((h, node))
                handled = True
                break
        if not handled:
            body.append((i+1, stripped))
            i += 1
    return body, i

class StatementHandler:
    keywords = []
    required_headers = set()

    def can_handle(self, line: str) -> bool:
        return any(line.startswith(kw) for kw in self.keywords)

    def parse(self, lines, start_index):
        raise NotImplementedError

    def generate(self, node, indent='') -> str:
        raise NotImplementedError
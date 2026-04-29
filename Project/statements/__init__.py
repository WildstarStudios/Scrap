import re
import os

_handlers = []
_alias_map = {}
_var_types = {}  # name -> type string (e.g., 'std::string', 'int', 'double', 'sqlite3*', etc.)

# C functions that require const char* for string arguments
C_STRING_FUNCTIONS = {
    'sqlite3_open', 'sqlite3_exec', 'sqlite3_prepare_v2',
    'sqlite3_bind_text', 'sqlite3_column_text', 'sqlite3_errmsg'
}

def register_handler(handler):
    _handlers.append(handler)

def get_handlers():
    return _handlers

def register_alias(alias, namespace):
    _alias_map[alias] = namespace

def resolve_alias(alias):
    return _alias_map.get(alias, alias)

def set_var_type(name: str, typ: str):
    _var_types[name] = typ

def get_var_type(name: str) -> str:
    return _var_types.get(name, '')

def clear_var_types():
    _var_types.clear()

def strip_comments(line: str) -> str:
    """Remove -- comment from line, respecting quotes."""
    in_quotes = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == '-' and i+1 < len(line) and line[i+1] == '-' and not in_quotes:
            return line[:i].rstrip()
    return line

def _split_args(raw_args):
    """Split comma-separated arguments, respecting quotes. Returns list."""
    if not raw_args.strip():
        return []
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
    # Match alias.func(args)  (allow empty args)
    m = re.match(r'^([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)\((.*)\)$', expr)
    if m:
        alias = m.group(1)
        func = m.group(2)
        raw_args = m.group(3)
        args = _split_args(raw_args)
        full_namespace = resolve_alias(alias)
        full_func = f'{full_namespace}::{func}'
        return full_func, args

    # Match func(args)  (allow empty args)
    m = re.match(r'^([a-zA-Z_]\w*)\((.*)\)$', expr)
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
        # Strip comments before checking emptiness
        no_comment = strip_comments(raw_line)
        stripped = no_comment.strip()
        if not stripped:
            i += 1
            continue
        indent = get_indent(raw_line)
        if indent <= base_indent:
            break

        handled = False
        for h in handlers:
            if h.can_handle(stripped):
                # Parse using the original raw lines (the handler will strip comments inside)
                node, i = h.parse(lines, i)
                body.append((h, node))
                handled = True
                break
        if not handled:
            # Keep line number, but store stripped version for error reporting
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
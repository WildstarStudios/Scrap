import re
import os

# ---------- Global state for type tracking ----------
_var_types = {}

def set_var_type(name, cpp_type):
    _var_types[name] = cpp_type

def get_var_type(name):
    return _var_types.get(name)

def clear_var_types():
    _var_types.clear()

def is_pointer_type(name):
    t = _var_types.get(name)
    return t is not None and t.endswith('*')

# ---------- Handler registry ----------
_handlers = []

def register_handler(handler):
    _handlers.append(handler)

def get_handlers():
    return _handlers

# ---------- Alias handling for C++ namespaces ----------
_alias_map = {}

def register_alias(alias, namespace):
    _alias_map[alias] = namespace

def resolve_alias(alias):
    return _alias_map.get(alias, alias)

def is_cpp_alias(alias):
    return alias in _alias_map

# ---------- Alias handling for C libraries ----------
_c_alias_map = {}

def register_c_alias(alias, prefix):
    _c_alias_map[alias] = prefix

def resolve_c_alias(alias):
    return _c_alias_map.get(alias)

# ---------- C / C++ header detection ----------
def is_c_header(header_path):
    ext = os.path.splitext(header_path)[1].lower()
    return ext in ('.h', '.c') and not header_path.endswith('.hpp')

# ---------- Comment stripping ----------
def strip_comments(line):
    in_quotes = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == '-' and i+1 < len(line) and line[i+1] == '-' and not in_quotes:
            return line[:i].rstrip()
    return line

# ---------- Helper: split arguments respecting parentheses and quotes ----------
def _split_args(args_str):
    args = []
    current = []
    paren_depth = 0
    in_quotes = False
    for ch in args_str:
        if ch == '"' and not in_quotes:
            in_quotes = True
            current.append(ch)
        elif ch == '"' and in_quotes:
            in_quotes = False
            current.append(ch)
        elif ch == '(' and not in_quotes:
            paren_depth += 1
            current.append(ch)
        elif ch == ')' and not in_quotes:
            paren_depth -= 1
            current.append(ch)
        elif ch == ',' and not in_quotes and paren_depth == 0:
            args.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        args.append(''.join(current).strip())
    return args

# ---------- Function call parsing (handles nested parentheses) ----------
def parse_function_call(expr):
    """
    Returns (transformed_func_name, arg_list, is_c_call)
    or None if it's not a function call.
    """
    idx = expr.find('(')
    if idx == -1:
        return None
    func_name = expr[:idx].strip()
    # Find matching closing parenthesis
    paren_count = 0
    end = idx
    for i, ch in enumerate(expr):
        if i < idx:
            continue
        if ch == '(':
            paren_count += 1
        elif ch == ')':
            paren_count -= 1
            if paren_count == 0:
                end = i
                break
    if end == idx:
        return None
    args_str = expr[idx+1:end].strip()
    args = _split_args(args_str)

    is_c_call = False
    new_func = func_name
    if '.' in func_name:
        parts = func_name.split('.')
        alias = parts[0]
        c_prefix = resolve_c_alias(alias)
        if c_prefix:
            is_c_call = True
            # Build the C function name dynamically:
            new_func = parts[0]
            for part in parts[1:]:
                if part and part[0].isupper():
                    new_func += part
                else:
                    new_func += '_' + part
            return new_func, args, is_c_call
        if is_cpp_alias(alias):
            namespace = _alias_map[alias]
            if len(parts) == 1:
                new_func = namespace
            else:
                new_func = namespace + '::' + '::'.join(parts[1:])
            return new_func, args, is_c_call   # is_c_call remains False
    return func_name, args, is_c_call

def wrap_c_args(args, is_c_call):
    """If this is a C call, convert any std::string variable to .c_str()"""
    if not is_c_call:
        return args
    wrapped = []
    for arg in args:
        if arg in _var_types and _var_types[arg] == 'std::string':
            wrapped.append(f'{arg}.c_str()')
        else:
            wrapped.append(arg)
    return wrapped

# ---------- Expression resolver for conditions / loop expressions ----------
def resolve_expression(expr):
    """
    Replace any dot‑calls inside `expr` with their resolved C/C++ names.
    Example: "glfw.WindowShouldClose(window)" -> "glfwWindowShouldClose(window)"
    """
    def replace_func(match):
        full_call = match.group(0)  # e.g., "glfw.WindowShouldClose(window)"
        idx = full_call.find('(')
        before_paren = full_call[:idx]
        if '.' in before_paren:
            parts = before_paren.split('.')
            alias = parts[0]
            c_prefix = resolve_c_alias(alias)
            if c_prefix:
                # C library: apply case rule
                new_name = parts[0]
                for part in parts[1:]:
                    if part and part[0].isupper():
                        new_name += part
                    else:
                        new_name += '_' + part
                return new_name + '(' + full_call[idx+1:]
            elif is_cpp_alias(alias):
                # C++ namespace
                namespace = _alias_map[alias]
                new_name = namespace + '::' + '::'.join(parts[1:])
                return new_name + '(' + full_call[idx+1:]
        return full_call

    # Find patterns like identifier.identifier(...) with optional arguments
    return re.sub(r'[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\)', replace_func, expr)

# ---------- Error suggestion ----------
def suggest_fix(line):
    line = line.strip()
    if line.startswith('set '):
        return "Use 'variable = expression' without 'set'. Example: " + line[4:]
    if '=' in line and not line.startswith(('var ', 'if ', 'while ', 'repeat ', 'for ', 'ask ', 'log ', 'free ', 'import ', 'pause', '--', 'delete ')):
        return "Assignment should use 'variable = expression'. Example: " + line
    return "Check the statement syntax."

# ---------- Block body parsing (updated to return defer list) ----------
def parse_block_body(lines, start_index, base_indent):
    def get_indent(line):
        return len(line) - len(line.lstrip())

    body = []
    deferred = []   # list of ('DEFER', stmt) nodes
    i = start_index
    from . import get_handlers
    handlers = get_handlers()

    while i < len(lines):
        raw_line = lines[i]
        stripped = strip_comments(raw_line).strip()
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
                if node[0] == 'DEFER':
                    deferred.append(node)
                else:
                    body.append((h, node))
                handled = True
                break
        if not handled:
            body.append((i+1, stripped))
            i += 1
    return body, deferred, i

def generate_deferred_lines(deferred_nodes, indent):
    """Turn deferred nodes into C++ statements with the given indent."""
    lines = []
    for node in deferred_nodes:
        stmt = node[1]   # raw statement string
        lines.append(f'{indent}{stmt};')
    return lines

# ---------- Base handler class ----------
class StatementHandler:
    keywords = []
    required_headers = set()

    def can_handle(self, line: str) -> bool:
        return any(line.startswith(kw) for kw in self.keywords)

    def parse(self, lines, start_index):
        raise NotImplementedError

    def generate(self, node, indent='') -> str:
        raise NotImplementedError

    # New optional method for semantic checks
    def check_semantics(self, node, symbols):
        pass
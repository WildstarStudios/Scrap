"""Scrap utilities – type mapping, alias registry, dotted call resolution."""
import re
from scrap.core.debug import DEBUG

_type_map = {
    'int': 'int', 'float': 'double', 'string': 'std::string',
    'bool': 'bool', 'void': 'void', 'auto': 'auto',
}

def to_cpp_type(t: str) -> str:
    base = t.rstrip('*&').rstrip()
    suffix = t[len(base):]
    return _type_map.get(base, base) + suffix

def infer_type_from_value(value: str) -> str:
    if value.startswith('"') and value.endswith('"'):
        return 'std::string'
    if re.match(r'^-?\d+$', value):
        return 'int'
    if re.match(r'^-?\d+\.\d+$', value):
        return 'double'
    if value.lower() in ('true', 'false'):
        return 'bool'
    return 'auto'

# ----------------------------------------------------------------------
#  Library alias system
# ----------------------------------------------------------------------
_LIBRARY_ALIASES = {}

def register_library_alias(alias, prefix, func_map):
    _LIBRARY_ALIASES[alias] = {'prefix': prefix, 'functions': func_map}

def is_library_alias(alias):
    return alias in _LIBRARY_ALIASES

def get_library_function(alias, suffix):
    lib = _LIBRARY_ALIASES.get(alias)
    if lib:
        return lib['functions'].get(suffix)
    return None

# ----------------------------------------------------------------------
#  Owned / out‑param creators
# ----------------------------------------------------------------------
_OWNED_CREATORS = {}
_OUTPARAM_CREATORS = {}

def register_owned_creator(func_name, wrapper_type):
    _OWNED_CREATORS[func_name] = wrapper_type

def get_owned_wrapper(func_name):
    return _OWNED_CREATORS.get(func_name)

def register_outparam_creator(creator, base_type, deleter, alias):
    _OUTPARAM_CREATORS[creator] = (base_type, deleter, alias)

def get_outparam_creator_info(func_name):
    return _OUTPARAM_CREATORS.get(func_name)

# ----------------------------------------------------------------------
#  Variable → library alias mapping
# ----------------------------------------------------------------------
_VARIABLE_LIB_MAP = {}

def register_variable_library(var_name, alias):
    if DEBUG:
        print(f"[DEBUG utils.py] register_variable_library: {var_name} -> {alias}")
    _VARIABLE_LIB_MAP[var_name] = alias

def get_variable_library(var_name):
    return _VARIABLE_LIB_MAP.get(var_name)

# ----------------------------------------------------------------------
#  Imported function signatures (for auto‑fill)
# ----------------------------------------------------------------------
_IMPORTED_FUNCTIONS = {}

def register_imported_function(full_name, param_types):
    _IMPORTED_FUNCTIONS[full_name] = param_types

def get_imported_function_signature(full_name):
    return _IMPORTED_FUNCTIONS.get(full_name)

def auto_fill_arguments(func_name, given_args):
    """If func_name is a known imported function, append `nullptr` for any
    missing pointer parameters."""
    sig = get_imported_function_signature(func_name)
    if not sig:
        return given_args
    filled = list(given_args)
    for i in range(len(filled), len(sig)):
        ptype = sig[i]
        if '*' in ptype:
            filled.append('nullptr')
    return filled

def auto_fill_resolved_call(resolved: str) -> str:
    """Given a resolved function call string (e.g., 'sqlite3_exec(db.get(), ...)'),
    auto-fill missing pointer arguments and return the corrected string."""
    m = re.match(r'^([a-zA-Z_]\w*)\(', resolved)
    if not m:
        return resolved
    fn = m.group(1)
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
    args = []
    current = []
    depth = 0
    in_str = False
    for ch in inner:
        if ch == '"' and not in_str:
            in_str = True
            current.append(ch)
        elif ch == '"' and in_str:
            in_str = False
            current.append(ch)
        elif ch == ',' and depth == 0 and not in_str:
            args.append(''.join(current).strip())
            current = []
        else:
            if ch == '(' and not in_str:
                depth += 1
            elif ch == ')' and not in_str:
                depth -= 1
            current.append(ch)
    if current:
        args.append(''.join(current).strip())
    filled = auto_fill_arguments(fn, args)
    return f'{fn}({", ".join(filled)})'

# ----------------------------------------------------------------------
#  Variable type registry (for smart printf formatting)
# ----------------------------------------------------------------------
_VAR_TYPES = {}

def register_variable_type(name, cpp_type):
    _VAR_TYPES[name] = cpp_type

def get_variable_type(name):
    return _VAR_TYPES.get(name)

# ----------------------------------------------------------------------
#  Basic dotted call resolution – handles multi‑dot chains
# ----------------------------------------------------------------------
def resolve_dotted_calls(text: str) -> str:
    if DEBUG:
        print(f"[DEBUG utils.py] resolve_dotted_calls IN: {text!r}")

    def replacer(match):
        full = match.group(0)                # e.g., 'rapidfuzz.fuzz.ratio('
        dotted_chain = match.group(1)        # 'rapidfuzz.fuzz.ratio'
        paren_idx = full.find('(')
        if paren_idx == -1:
            return full
        args_start = full[paren_idx:]        # '(' + rest
        parts = dotted_chain.split('.')
        alias = parts[0]

        if DEBUG:
            print(f"[DEBUG utils.py]   Checking alias='{alias}', chain='{dotted_chain}'")

        if is_library_alias(alias):
            lib = _LIBRARY_ALIASES[alias]
            # C++ namespace alias? (empty prefix, empty func_map)
            if lib['prefix'] == '' and not lib['functions']:
                cpp_name = '::'.join(parts)
                if DEBUG:
                    print(f"[DEBUG utils.py]   -> C++ qualified: {cpp_name}")
                return cpp_name + args_start

            # C library alias: method is everything after the first dot
            method = '.'.join(parts[1:])
            info = get_library_function(alias, method)
            if info:
                full_name, takes_handle = info
                if DEBUG:
                    print(f"[DEBUG utils.py]   -> resolved to {full_name}")
                return full_name + args_start
            else:
                if DEBUG:
                    print(f"[DEBUG utils.py]   alias '{alias}' known but method '{method}' not found")
        else:
            if DEBUG:
                print(f"[DEBUG utils.py]   alias '{alias}' not in _LIBRARY_ALIASES (keys: {list(_LIBRARY_ALIASES.keys())})")

        # Variable method call?
        if alias in _VARIABLE_LIB_MAP:
            lib_alias = _VARIABLE_LIB_MAP[alias]
            method = '.'.join(parts[1:])
            info = get_library_function(lib_alias, method)
            if info:
                full_name, takes_handle = info
                if DEBUG:
                    print(f"[DEBUG utils.py]   -> resolved via variable to {full_name}")
                return full_name + args_start

        return full

    # Match one or more dot‑separated identifiers before '('
    result = re.sub(r'\b([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+)\s*\(', replacer, text)
    if DEBUG:
        print(f"[DEBUG utils.py] resolve_dotted_calls OUT: {result!r}")
    return result

# ----------------------------------------------------------------------
#  Full dotted‑call resolution WITH handle insertion
# ----------------------------------------------------------------------
def resolve_dotted_call_with_handle(text: str) -> str:
    """
    Resolves dotted calls entirely, inserting `var.get()` as the first
    argument when a variable method call requires a handle.
    Replaces the **whole** dotted call (including its argument list).
    """
    result = []
    i = 0
    n = len(text)

    while i < n:
        # Match a chain of identifiers separated by dots, ending with '('
        m = re.compile(r'\b([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)+)\s*\(').search(text, i)
        if not m:
            result.append(text[i:])
            break

        result.append(text[i:m.start()])

        dotted_chain = m.group(1)          # e.g., 'rapidfuzz.fuzz.ratio' or 'db.exec'
        paren_pos = m.end() - 1            # position of '('
        parts = dotted_chain.split('.')
        var_name = parts[0]
        method = '.'.join(parts[1:])

        j = paren_pos + 1
        depth = 1
        in_str = False
        str_char = None
        while j < n and depth > 0:
            c = text[j]
            if in_str:
                if c == '\\' and j+1 < n:
                    j += 1
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
            j += 1
        if depth != 0:
            result.append(text[m.start():j])
            i = j
            continue

        closing_paren = j - 1
        inner = text[paren_pos+1 : closing_paren].strip()

        resolved = None

        # Variable method call?
        if var_name in _VARIABLE_LIB_MAP:
            lib_alias = _VARIABLE_LIB_MAP[var_name]
            info = get_library_function(lib_alias, method)
            if info:
                full_name, takes_handle = info
                if takes_handle:
                    new_inner = f'{var_name}.get(), {inner}' if inner else f'{var_name}.get()'
                else:
                    new_inner = inner
                resolved = f'{full_name}({new_inner})'

        # Static alias call? (C or C++ namespace)
        if resolved is None and is_library_alias(var_name):
            lib = _LIBRARY_ALIASES.get(var_name)
            if lib and lib['prefix'] == '' and not lib['functions']:
                # C++ namespace: replace all dots with ::
                cpp_name = '::'.join(parts)
                resolved = f'{cpp_name}({inner})'
            else:
                info = get_library_function(var_name, method)
                if info:
                    full_name, _ = info
                    resolved = f'{full_name}({inner})'

        if resolved is not None:
            result.append(resolved)
        else:
            result.append(text[m.start():j])

        i = j

    return ''.join(result)
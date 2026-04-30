import re

# ---------- type mapping ----------
_type_map = {
    'int': 'int', 'float': 'double', 'String': 'std::string',
    'bool': 'bool', 'void': 'void',
}

def infer_type_from_value(value_expr):
    if value_expr.startswith('"') and value_expr.endswith('"'):
        return 'std::string'
    if re.match(r'^-?\d+$', value_expr):
        return 'int'
    if re.match(r'^-?\d+\.\d+$', value_expr):
        return 'double'
    if value_expr.lower() in ('true', 'false'):
        return 'bool'
    if value_expr.startswith('['):
        return '__LIST__'
    return 'auto'

def to_cpp_type(scrap_type):
    base = scrap_type.rstrip('*&').rstrip()
    suffix = scrap_type[len(base):]
    if base in _type_map:
        return _type_map[base] + suffix
    return scrap_type

def resolve_expression(expr):
    return expr

# ---------- alias maps ----------
_alias_map = {}        # C++ namespace aliases (import lib ...)
_c_alias_map = {}      # C library prefixes (currently unused)

def register_alias(alias, namespace):
    _alias_map[alias] = namespace

def register_c_alias(alias, prefix):
    _c_alias_map[alias] = prefix

def resolve_alias(alias):
    return _alias_map.get(alias, alias)

def is_cpp_alias(alias):
    return alias in _alias_map

def resolve_c_alias(alias):
    return _c_alias_map.get(alias)

# ---------- dotted call resolver ----------
def resolve_dotted_calls(text):
    """Replace Alias.method(...) with Namespace::method(...) for known aliases."""
    def replace(match):
        dotted = match.group(0)
        parts = dotted.split('(')
        name_parts = parts[0].rstrip('.').split('.')
        if len(name_parts) >= 2:
            alias = name_parts[0]
            if is_cpp_alias(alias):
                ns = resolve_alias(alias)
                name_parts[0] = ns
                new_prefix = '::'.join(name_parts)
                return new_prefix + '(' + '('.join(parts[1:])
        return dotted
    return re.sub(r'[a-zA-Z_]\w*\.[a-zA-Z_]\w*\(', replace, text)

# ---------- owned creators map (used by import_lib + var/set) ----------
_owned_creators = {}

def register_owned_creator(func_name, wrapper_type):
    """Remember that a function returns an owned pointer wrapped by wrapper_type."""
    _owned_creators[func_name] = wrapper_type

def get_owned_wrapper(func_name):
    """Return the unique_ptr wrapper name for a function, or None."""
    return _owned_creators.get(func_name)
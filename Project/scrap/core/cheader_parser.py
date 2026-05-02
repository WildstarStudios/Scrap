#!/usr/bin/env python3
"""
Pure-Python C header parser – extracts functions and ownership.
No compiler required.
"""
import re
from scrap.core.debug import DEBUG

C_KEYWORDS = {
    'int', 'char', 'void', 'float', 'double', 'short', 'long',
    'unsigned', 'signed', 'struct', 'union', 'enum', 'const', 'volatile',
    'typedef', 'extern', 'static', 'auto', 'register', 'sizeof'
}

def read_and_clean(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
    raw = re.sub(r'//.*$', '', raw, flags=re.MULTILINE)
    lines = raw.split('\n')
    clean = []
    for line in lines:
        s = line.strip()
        if s.startswith('#') or not s:
            continue
        clean.append(s)
    return clean

def join_multiline(lines):
    joined = []
    buffer = ""
    paren_count = 0
    for line in lines:
        if not buffer:
            buffer = line
        else:
            buffer += ' ' + line
        paren_count += line.count('(') - line.count(')')
        if paren_count == 0:
            joined.append(buffer)
            buffer = ""
    if buffer:
        joined.append(buffer)
    return joined

def strip_macros(line):
    macros = ['SQLITE_API', 'SQLITE_CDECL', 'SQLITE_STDCALL', 'SQLITE_EXTERN',
              'GLFWAPI', 'CURL_EXTERN', 'extern', 'static', 'virtual', 'inline',
              'typedef']
    for m in macros:
        line = re.sub(r'\b' + m + r'\b', '', line)
    line = line.rstrip(';')
    return line.strip()

def parse_declaration(line):
    start = line.find('(')
    if start == -1:
        return None
    before = line[:start].strip()
    tokens = before.split()
    if not tokens:
        return None
    last = tokens[-1]
    name = last.lstrip('*')
    if not name:
        return None
    ptr_prefix = '*' * (len(last) - len(name))
    ret_parts = tokens[:-1]
    if ret_parts:
        return_type = ' '.join(ret_parts) + (' ' + ptr_prefix).strip()
    else:
        return_type = ptr_prefix if ptr_prefix else ''
    open_count = 1
    i = start + 1
    while i < len(line) and open_count > 0:
        if line[i] == '(':
            open_count += 1
        elif line[i] == ')':
            open_count -= 1
        i += 1
    if open_count != 0:
        return None
    params_str = line[start+1 : i-1].strip()
    return return_type.strip(), name, params_str

def split_param_types(params_str):
    if not params_str or params_str.lower().strip() == 'void':
        return []
    params = []
    current = []
    depth = 0
    for ch in params_str:
        if ch == ',' and depth == 0:
            params.append(''.join(current).strip())
            current = []
        else:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            current.append(ch)
    if current:
        params.append(''.join(current).strip())
    return params

def extract_functions(clean_lines):
    joined = join_multiline(clean_lines)
    functions = []
    for line in joined:
        line = strip_macros(line)
        if '(' not in line or ')' not in line:
            continue
        decl = parse_declaration(line)
        if decl:
            ret_type, name, params_str = decl
            if name in C_KEYWORDS or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
                continue
            param_list = split_param_types(params_str)
            functions.append({
                'name': name,
                'full_name': name,
                'return_type': ret_type,
                'is_pointer_return': '*' in ret_type and '**' not in ret_type,
                'param_types': param_list,
            })
    if DEBUG:
        print(f"[DEBUG cheader_parser] extracted {len(functions)} functions, first 5: {[f['name'] for f in functions[:5]]}")
    return functions

def get_base_type(type_str):
    t = re.sub(r'\bconst\b', '', type_str).strip()
    t = t.replace('*', '').strip()
    return t.split()[0] if t else ''

def detect_ownership(functions):
    by_name = {f['name']: f for f in functions}
    ownership = {}
    # Keywords in decreasing order of preference (more specific/reliable)
    destroy_keywords = ['finalize', 'close', 'free', 'destroy', 'reset', 'unlock', 'disable']

    for f in functions:
        if f['name'] in ownership:
            continue
        base_type = None
        is_outparam = False

        # Check return type (pointer return) -> creator
        if f['is_pointer_return']:
            base_type = get_base_type(f['return_type'])

        # Check for output parameter (`**`), but exclude function pointers
        if not base_type:
            for p in f['param_types']:
                # Skip parameters that are function pointers (contain '(')
                if '(' in p:
                    continue
                if '**' in p:
                    base_type = get_base_type(p)
                    is_outparam = True
                    break

        if not base_type or base_type == 'void' or base_type in ('int', 'char', 'double', 'float'):
            continue

        # Find the best matching destroyer
        # Preference: earlier keywords in the list are better
        best_destroyer = None
        best_keyword_idx = len(destroy_keywords) + 1  # lower is better

        for cand in functions:
            if cand['name'] == f['name']:
                continue
            if len(cand['param_types']) != 1:
                continue
            p0 = cand['param_types'][0].replace('const', '').strip()
            if re.match(r'^' + re.escape(base_type) + r'\s*\*$', p0):
                dname_lower = cand['name'].lower()
                # Find the best keyword in this destroyer
                for idx, kw in enumerate(destroy_keywords):
                    if kw in dname_lower:
                        if idx < best_keyword_idx:
                            best_keyword_idx = idx
                            best_destroyer = cand['name']
                        break   # first matching keyword wins for this function

        if best_destroyer:
            if is_outparam:
                ownership[f['name']] = (best_destroyer, base_type, True)
            else:
                ownership[f['name']] = best_destroyer

    if DEBUG:
        print(f"[DEBUG cheader_parser] ownership keys: {list(ownership.keys())}")
    return ownership

def parse_cheader(header_path):
    lines = read_and_clean(header_path)
    functions = extract_functions(lines)
    ownership = detect_ownership(functions)
    return functions, ownership
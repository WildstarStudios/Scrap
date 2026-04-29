#!/usr/bin/env python3
"""
Scrap Transpiler v0.3 – with functions, return, and proper entry point.
"""

import sys
import os
import importlib
import inspect
from statements import StatementHandler, register_handler, get_handlers, clear_var_types, generate_deferred_lines

def strip_comments(line):
    """Remove -- comment from line, respecting quotes."""
    in_quotes = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == '-' and i+1 < len(line) and line[i+1] == '-' and not in_quotes:
            return line[:i].rstrip()
    return line

def discover_handlers():
    base_dir = os.path.dirname(__file__)
    for folder in ['statements', 'blocks']:
        folder_path = os.path.join(base_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                if filename.endswith('.py') and filename != '__init__.py':
                    rel_path = os.path.relpath(root, base_dir)
                    module_parts = rel_path.split(os.sep) + [filename[:-3]]
                    module_name = '.'.join(module_parts)
                    try:
                        module = importlib.import_module(module_name)
                    except ImportError as e:
                        print(f"Warning: could not import {module_name}: {e}", file=sys.stderr)
                        continue
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, StatementHandler) and obj is not StatementHandler:
                            register_handler(obj())

def collect_all_headers(nodes):
    headers = set()
    for handler, node in nodes:
        if node[0] == 'DEFER':
            continue
        rh = handler.required_headers
        if callable(rh):
            headers.update(rh(node))
        else:
            headers.update(rh)

        # Recursively handle nested blocks (including function bodies)
        if node[0] == 'IF':
            branches = node[1]
            for _, body_data in branches:
                for body_items, deferred_items in body_data:
                    for item in body_items:
                        if isinstance(item, tuple):
                            if len(item) == 2 and isinstance(item[0], int):
                                _, stmt = item
                                for h in get_handlers():
                                    if not isinstance(h, StatementHandler):
                                        continue
                                    if h.can_handle(stmt):
                                        rh2 = h.required_headers
                                        if callable(rh2):
                                            headers.update(rh2(None))
                                        else:
                                            headers.update(rh2)
                                        break
                            else:
                                h, n = item
                                if not isinstance(h, StatementHandler):
                                    continue
                                rh2 = h.required_headers
                                if callable(rh2):
                                    headers.update(rh2(n))
                                else:
                                    headers.update(rh2)
        elif node[0] in ('WHILE', 'REPEAT', 'FOR', 'FUNC'):
            if node[0] == 'FOR':
                body_items = node[1][2]
            elif node[0] == 'FUNC':
                body_items = node[1][4]
            else:
                body_items = node[1][1]
            for item in body_items:
                if isinstance(item, tuple):
                    if len(item) == 2 and isinstance(item[0], int):
                        _, stmt = item
                        for h in get_handlers():
                            if not isinstance(h, StatementHandler):
                                continue
                            if h.can_handle(stmt):
                                rh2 = h.required_headers
                                if callable(rh2):
                                    headers.update(rh2(None))
                                else:
                                    headers.update(rh2)
                                break
                    else:
                        h, n = item
                        if not isinstance(h, StatementHandler):
                            continue
                        rh2 = h.required_headers
                        if callable(rh2):
                            headers.update(rh2(n))
                        else:
                            headers.update(rh2)
    return headers

def main():
    clear_var_types()

    if len(sys.argv) != 3:
        print("Usage: python scrap.py input.scrap output.cpp")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    with open(input_file, 'r') as f:
        source_lines = f.readlines()

    discover_handlers()
    handlers = get_handlers()

    # Parse all top-level nodes
    top_level_nodes = []
    functions = []
    i = 0
    while i < len(source_lines):
        raw_line = source_lines[i].rstrip('\n')
        line = strip_comments(raw_line).strip()
        if not line:
            i += 1
            continue

        handled = False
        for handler in handlers:
            if not isinstance(handler, StatementHandler):
                continue
            if handler.can_handle(line):
                try:
                    node, i = handler.parse(source_lines, i)
                    if node[0] == 'FUNC':
                        functions.append((handler, node))
                    else:
                        top_level_nodes.append((handler, node))
                    handled = True
                    break
                except SyntaxError as e:
                    print(f"Error on line {i+1} of {input_file}: {e}", file=sys.stderr)
                    sys.exit(1)
        if not handled:
            print(f"Error on line {i+1} of {input_file}: Unknown statement: {line}", file=sys.stderr)
            sys.exit(1)

    # Collect headers from both functions and top-level nodes
    headers = collect_all_headers(top_level_nodes + functions)

    # Force inclusion of <iostream> because log/ask/pause use it
    headers.add('<iostream>')

    pre_main_lines = []
    for handler, node in top_level_nodes + functions:
        if not isinstance(handler, StatementHandler):
            continue
        if hasattr(handler, 'generate_pre_main'):
            pm = handler.generate_pre_main(node)
            if pm:
                pre_main_lines.append(pm)

    cpp_lines = []
    if headers:
        cpp_lines.extend([f'#include {h}' for h in sorted(headers)])
    cpp_lines.extend(pre_main_lines)
    cpp_lines.append('')

    # Generate forward declarations for all user functions
    for handler, node in functions:
        if not isinstance(handler, StatementHandler):
            continue
        if hasattr(handler, 'forward_declaration'):
            fwd = handler.forward_declaration(node)
            if fwd:
                cpp_lines.append(fwd)
    if functions:
        cpp_lines.append('')

    # Generate function definitions
    for handler, node in functions:
        if not isinstance(handler, StatementHandler):
            continue
        if hasattr(handler, 'generate_function'):
            cpp_lines.append(handler.generate_function(node))

    # Determine if user defined a 'main' function
    user_main_node = None
    for handler, node in functions:
        if node[0] == 'FUNC' and node[1][0] == 'main':
            user_main_node = node
            break

    # Generate real C++ int main()
    cpp_lines.append('')
    cpp_lines.append('int main() {')
    body_indent = '    '

    deferred_main = []
    for handler, node in top_level_nodes:
        if node[0] == 'DEFER':
            deferred_main.append(node)
        else:
            cpp_lines.append(handler.generate(node, body_indent))

    if user_main_node:
        return_type = user_main_node[1][3]
        if return_type == 'int':
            cpp_lines.append(f'{body_indent}return user_main();')
        else:
            cpp_lines.append(f'{body_indent}user_main();')
            cpp_lines.append(f'{body_indent}return 0;')

    cpp_lines.extend(generate_deferred_lines(deferred_main, body_indent))
    cpp_lines.append('}')
    final_code = '\n'.join(cpp_lines) + '\n'

    with open(output_file, 'w') as f:
        f.write(final_code)

    print(f"✓ Transpiled '{input_file}' → '{output_file}'")

if __name__ == '__main__':
    main()
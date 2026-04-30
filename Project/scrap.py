#!/usr/bin/env python3
"""Scrap transpiler – high‑level Pythonic language to C++."""
import sys
from scrap.core.handler_base import discover_handlers, strip_comments, get_indent, generate_deferred_lines
from scrap.core.symbol_table import SemanticAnalyzer

def join_multiline_statements(lines):
    """Join lines that end with a comma, open paren or bracket with the next line."""
    joined = []
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip('\n')
        if not raw.strip():
            i += 1
            continue
        # If line ends with , ( [ and next line is indented more, join them.
        while (raw.strip().endswith(',') or raw.strip().endswith('(') or raw.strip().endswith('[')) \
              and i + 1 < len(lines):
            next_raw = lines[i + 1].rstrip('\n')
            if not next_raw.strip():
                # skip empty lines between parts
                i += 1
                continue
            if get_indent(next_raw) <= get_indent(raw):
                break
            raw = raw + ' ' + next_raw.lstrip()
            i += 1
        joined.append(raw)
        i += 1
    return joined

def main():
    if len(sys.argv) != 3:
        print("Usage: python scrap.py input.scrap output.cpp")
        sys.exit(1)

    with open(sys.argv[1], 'r') as f:
        source = [line.rstrip('\n') for line in f.readlines()]

    # Allow multi‑line function calls (comma / paren continuation)
    source = join_multiline_statements(source)

    discover_handlers()

    top_nodes = []
    functions = []
    i = 0
    while i < len(source):
        raw = source[i]
        stripped = strip_comments(raw).strip()
        if not stripped:
            i += 1
            continue
        if get_indent(raw) != 0:
            raise SyntaxError(f"Unexpected indentation at line {i+1}")

        handled = False
        for h in discover_handlers():
            if h.can_handle(stripped):
                node, i = h.parse(source, i)
                if node[0] == 'FUNC':
                    functions.append((h, node))
                else:
                    top_nodes.append((h, node))
                handled = True
                break
        if not handled:
            raise SyntaxError(f"Unknown statement at line {i+1}: {stripped}")

    SemanticAnalyzer.analyze(top_nodes, functions)

    # Recursive header collection from all statements (handlers, block bodies)
    def collect_headers_from_nodes(nodes):
        hdrs = set()
        for h, n in nodes:
            rh = getattr(h, 'required_headers', set())
            if callable(rh):
                rh = rh(n)
            hdrs.update(rh)

            kind = n[0]
            if kind == 'FUNC':
                _, _, _, body, deferred = n[1]
                hdrs.update(collect_headers_from_nodes(body))
            elif kind == 'IF':
                for _, body_data in n[1]:
                    for body, deferred in body_data:
                        hdrs.update(collect_headers_from_nodes(body))
            elif kind in ('WHILE', 'REPEAT'):
                _, body, deferred = n[1]
                hdrs.update(collect_headers_from_nodes(body))
            elif kind == 'FOR_RANGE':
                _, _, _, _, _, body, deferred = n[1]
                hdrs.update(collect_headers_from_nodes(body))
            elif kind == 'FOR_EACH':
                _, _, _, body, deferred = n[1]
                hdrs.update(collect_headers_from_nodes(body))
        return hdrs

    headers = collect_headers_from_nodes(top_nodes + functions)

    # Pre‑main content (smart wrappers, extern "C" blocks)
    pre_main = []
    for h, n in top_nodes + functions:
        if hasattr(h, 'generate_pre_main'):
            pre_main.append(h.generate_pre_main(n))

    output = []
    for hdr in sorted(headers):
        output.append(f'#include {hdr}')
    output.extend(pre_main)

    # Function definitions before main()
    for h, n in functions:
        if hasattr(h, 'generate_function'):
            output.append(h.generate_function(n))

    # main() wrapper
    if top_nodes or any(n[0] == 'FUNC' and n[1][0] == 'main' for _, n in functions):
        if any(n[0] == 'FUNC' and n[1][0] == 'main' for _, n in functions):
            output.append('')
            output.append('int main() { return user_main(); }')
        else:
            output.append('')
            output.append('int main() {')
            indent = '    '
            deferred_main = []
            for h, n in top_nodes:
                if n[0] == 'DEFER':
                    deferred_main.append(n)
                else:
                    output.append(h.generate(n, indent))
            output.extend(generate_deferred_lines(deferred_main, indent))
            output.append('    return 0;')
            output.append('}')

    with open(sys.argv[2], 'w') as f:
        f.write('\n'.join(output) + '\n')
    print(f"✓ Transpiled '{sys.argv[1]}' → '{sys.argv[2]}'")

if __name__ == '__main__':
    main()
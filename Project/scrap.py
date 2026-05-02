#!/usr/bin/env python3
import sys, re
from scrap.core.handler_base import (
    strip_comments, get_indent, parse_block_body, generate_deferred_lines,
    set_handlers, get_handlers
)
from scrap.handlers.interop.import_lib import ImportLibHandler
from scrap.handlers.declarations.var import VarHandler
from scrap.handlers.declarations.set import SetHandler
from scrap.handlers.functions.func import FuncHandler
from scrap.handlers.control.if_handler import IfHandler
from scrap.handlers.control.while_handler import WhileHandler
from scrap.handlers.control.break_handler import BreakHandler
from scrap.handlers.control.return_handler import ReturnHandler
from scrap.handlers.io.log import LogHandler
from scrap.handlers.io.ask import AskHandler
from scrap.handlers.memory.defer import DeferHandler
from scrap.handlers.calls.function_call import FunctionCallHandler
from scrap.core.debug import DEBUG
from scrap.core.utils import SSO_RUNTIME, mark_uses_dynamic_string

HANDLERS = [
    ImportLibHandler(),
    FuncHandler(),
    VarHandler(),
    SetHandler(),
    IfHandler(),
    WhileHandler(),
    BreakHandler(),
    ReturnHandler(),
    LogHandler(),
    AskHandler(),
    DeferHandler(),
    FunctionCallHandler(),
]

set_handlers(HANDLERS)

def join_multiline_statements(lines):
    joined = []
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip('\n')
        if not raw.strip():
            i += 1
            continue
        while (raw.strip().endswith(',') or raw.strip().endswith('(') or raw.strip().endswith('[')) \
              and i+1 < len(lines):
            next_raw = lines[i+1].rstrip('\n')
            if not next_raw.strip():
                i += 1
                continue
            if get_indent(next_raw) <= get_indent(raw):
                break
            raw = raw + ' ' + next_raw.lstrip()
            i += 1
        joined.append(raw)
        i += 1
    return joined

def collect_headers_from_nodes(nodes):
    """Recursively collect required headers from a list of (handler, node) tuples."""
    headers = set()
    for h, node in nodes:
        if hasattr(h, 'required_headers'):
            rh = h.required_headers
            if callable(rh):
                rh = rh(node)
            headers.update(rh)

        kind = node[0]
        if kind == 'FUNC':
            _, _, _, body, deferred = node[1]
            headers.update(collect_headers_from_nodes(body))
        elif kind == 'IF':
            for _, body_data in node[1]:
                for body, deferred in body_data:
                    headers.update(collect_headers_from_nodes(body))
        elif kind in ('WHILE', 'REPEAT'):
            _, body, deferred = node[1]
            headers.update(collect_headers_from_nodes(body))
        elif kind == 'FOR_RANGE':
            _, _, _, _, _, body, deferred = node[1]
            headers.update(collect_headers_from_nodes(body))
        elif kind == 'FOR_EACH':
            _, _, _, body, deferred = node[1]
            headers.update(collect_headers_from_nodes(body))
    return headers

def _scan_for_dynamic_strings(nodes):
    """Recursively walk through parsed nodes and mark if any 'ASK' or explicit 'string'
       variable is present. This must be called BEFORE generation so that the runtime
       is emitted early enough."""
    for h, node in nodes:
        kind = node[0]
        if kind == 'ASK':
            mark_uses_dynamic_string()
        elif kind == 'VAR':
            _, _, explicit_type, _ = node
            if explicit_type == 'string':
                mark_uses_dynamic_string()
        elif kind == 'FUNC':
            _, _, _, body, deferred = node[1]
            _scan_for_dynamic_strings(body)
        elif kind == 'IF':
            for _, body_data in node[1]:
                for body, deferred in body_data:
                    _scan_for_dynamic_strings(body)
        elif kind in ('WHILE', 'REPEAT'):
            _, body, deferred = node[1]
            _scan_for_dynamic_strings(body)
        elif kind == 'FOR_RANGE':
            _, _, _, _, _, body, deferred = node[1]
            _scan_for_dynamic_strings(body)
        elif kind == 'FOR_EACH':
            _, _, _, body, deferred = node[1]
            _scan_for_dynamic_strings(body)

def main():
    if len(sys.argv) != 3:
        print("Usage: python scrap.py input.scrap output.cpp")
        sys.exit(1)

    with open(sys.argv[1], 'r') as f:
        source = [line.rstrip('\n') for line in f.readlines()]

    source = join_multiline_statements(source)

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
        for h in HANDLERS:
            if h.can_handle(stripped):
                if DEBUG:
                    print(f"[DEBUG scrap.py] Line {i+1} '{stripped}' -> handler {type(h).__name__}")
                node, i = h.parse(source, i)
                if node[0] == 'FUNC':
                    functions.append((h, node))
                else:
                    top_nodes.append((h, node))
                handled = True
                break
        if not handled:
            raise SyntaxError(f"Unknown statement at line {i+1}: {stripped}")

    # ---- Early scan for dynamic strings ----
    _scan_for_dynamic_strings(top_nodes)
    _scan_for_dynamic_strings(functions)

    # Collect required headers (recursively)
    all_headers = set()
    all_headers.update(collect_headers_from_nodes(top_nodes))
    all_headers.update(collect_headers_from_nodes(functions))
    for h, n in top_nodes + functions:
        if hasattr(h, 'required_headers'):
            rh = h.required_headers
            if callable(rh):
                rh = rh(n)
            all_headers.update(rh)

    output = []
    for hdr in sorted(all_headers):
        output.append(f'#include {hdr}')

    # Insert SSO string runtime if any dynamic string is used
    # (we check the global flag set during the early scan)
    from scrap.core.utils import uses_dynamic_string
    if uses_dynamic_string():
        output.append(SSO_RUNTIME.strip())

    # Pre‑main content from import libs
    for h, n in top_nodes + functions:
        if hasattr(h, 'generate_pre_main'):
            pre = h.generate_pre_main(n)
            if pre:
                output.append(pre)

    # Function definitions
    for h, n in functions:
        if hasattr(h, 'generate_function'):
            output.append(h.generate_function(n))

    # main() wrapper
    has_main_func = any(n[0] == 'FUNC' and n[1][0] == 'main' for _, n in functions)
    if has_main_func:
        output.append('int main() { return user_main(); }')
    else:
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

    final_code = '\n'.join(output) + '\n'
    final_code = re.sub(r'\bnull\b', 'nullptr', final_code)

    with open(sys.argv[2], 'w') as f:
        f.write(final_code)
    print(f"✓ Transpiled → {sys.argv[2]}")

if __name__ == '__main__':
    main()
import importlib
import inspect
import os
import sys
import re

_HANDLERS = None

def discover_handlers():
    global _HANDLERS
    if _HANDLERS is not None:
        return _HANDLERS
    _HANDLERS = []
    base_dir = os.path.dirname(os.path.dirname(__file__))   # scrap/
    handlers_dir = os.path.join(base_dir, 'handlers')
    for root, _, files in os.walk(handlers_dir):
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                rel_path = os.path.relpath(root, handlers_dir)
                parts = rel_path.split(os.sep) + [file[:-3]]
                module_name = 'scrap.handlers.' + '.'.join(parts)
                try:
                    mod = importlib.import_module(module_name)
                    for name, obj in inspect.getmembers(mod, inspect.isclass):
                        if issubclass(obj, StatementHandler) and obj is not StatementHandler:
                            _HANDLERS.append(obj())
                except Exception as e:
                    print(f"Warning: could not import {module_name}: {e}", file=sys.stderr)
    return _HANDLERS

class StatementHandler:
    keywords = []
    required_headers = set()

    def can_handle(self, line: str) -> bool:
        return any(line.startswith(kw) for kw in self.keywords)

    def parse(self, lines, start_index):
        raise NotImplementedError

    def generate(self, node, indent='') -> str:
        raise NotImplementedError

    def check_semantics(self, node, symbols):
        pass

def strip_comments(line):
    in_quotes = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == '-' and i+1 < len(line) and line[i+1] == '-' and not in_quotes:
            return line[:i].rstrip()
    return line

def get_indent(line):
    return len(line) - len(line.lstrip())

def parse_block_body(lines, start_index, base_indent):
    body = []
    deferred = []
    i = start_index
    handlers = discover_handlers()
    while i < len(lines):
        raw = lines[i]
        stripped = strip_comments(raw).strip()
        if not stripped:
            i += 1
            continue
        indent = get_indent(raw)
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
            raise SyntaxError(f"Line {i+1}: Unknown statement: {stripped}")
    return body, deferred, i

def generate_deferred_lines(deferred_nodes, indent):
    return [f'{indent}{stmt[1]};' for stmt in deferred_nodes]
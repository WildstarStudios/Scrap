import re

# Global handler list for block parsing
_handlers = []

def set_handlers(hlist):
    global _handlers
    _handlers = hlist

def get_handlers():
    return _handlers

class StatementHandler:
    keywords = []

    def can_handle(self, line: str) -> bool:
        return any(line.startswith(kw) for kw in self.keywords)

    def parse(self, lines, start_index):
        raise NotImplementedError

    def generate(self, node, indent='') -> str:
        raise NotImplementedError


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
    handlers = get_handlers()
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
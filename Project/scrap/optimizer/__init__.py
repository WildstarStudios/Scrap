"""AST optimization passes."""
from .loopify import optimize_ratio_chain

def optimize_ast(nodes, functions):
    """Apply all optimizations to AST nodes."""
    nodes = optimize_ratio_chain(nodes)
    new_functions = []
    for h, n in functions:
        if n[0] == 'FUNC':
            name, params, ret_type, body, deferred = n[1]
            body = optimize_ratio_chain(body)
            new_functions.append((h, ('FUNC', (name, params, ret_type, body, deferred))))
        else:
            new_functions.append((h, n))
    return nodes, new_functions
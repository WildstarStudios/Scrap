import sys
from scrap.core.utils import to_cpp_type

class Symbol:
    def __init__(self, name, cpp_type, is_function=False, param_types=None):
        self.name = name
        self.cpp_type = cpp_type
        self.is_function = is_function
        self.param_types = param_types or []

class SymbolTable:
    def __init__(self):
        self.scopes = [{}]
        self.current_function_ret = None
        self.loop_depth = 0

    def push_scope(self):
        self.scopes.append({})

    def pop_scope(self):
        self.scopes.pop()

    def declare(self, name, cpp_type, is_function=False, param_types=None):
        if name in self.scopes[-1]:
            raise SyntaxError(f"Redeclaration of '{name}'")
        self.scopes[-1][name] = Symbol(name, cpp_type, is_function, param_types)

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def enter_loop(self):
        self.loop_depth += 1

    def exit_loop(self):
        self.loop_depth -= 1

class SemanticAnalyzer:
    @staticmethod
    def analyze(top_level_nodes, functions):
        global_syms = SymbolTable()
        for handler, node in functions:
            if node[0] == 'FUNC':
                name, params, ret_type, _, _ = node[1]
                param_types = [to_cpp_type(pt) for pname, pt in params]
                global_syms.declare(name, to_cpp_type(ret_type), is_function=True, param_types=param_types)

        for handler, node in functions:
            if node[0] == 'FUNC':
                _check_function(node, global_syms)

        top_syms = SymbolTable()
        top_syms.push_scope()
        for name, sym in global_syms.scopes[0].items():
            if sym.is_function:
                top_syms.declare(name, sym.cpp_type, is_function=True, param_types=sym.param_types)
        _check_body(top_level_nodes, top_syms)

def _check_function(func_node, global_syms):
    name, params, ret_type, body_items, deferred_items = func_node[1]
    local = SymbolTable()
    local.push_scope()
    for pname, ptype in params:
        local.declare(pname, to_cpp_type(ptype))
    local.current_function_ret = to_cpp_type(ret_type)
    _check_body(body_items, local)
    for d in deferred_items:
        if d[0] == 'DEFER':
            _check_raw_statement(d[1], local)

def _check_body(nodes, symbols):
    for handler, node in nodes:
        if hasattr(handler, 'check_semantics'):
            handler.check_semantics(node, symbols)
        else:
            kind = node[0]
            if kind in ('IF', 'WHILE', 'REPEAT', 'FOR_RANGE', 'FOR_EACH'):
                _check_block(node, symbols)
            elif kind == 'BREAK':
                if symbols.loop_depth == 0:
                    raise SyntaxError("'break' outside loop")
            elif kind == 'RETURN':
                expected = symbols.current_function_ret
                expr = node[1]
                if expected == 'void':
                    if expr is not None:
                        raise SyntaxError("Cannot return a value from void function")
                else:
                    if expr is None:
                        raise SyntaxError(f"Expected return expression of type '{expected}'")

def _check_block(block_node, symbols):
    kind = block_node[0]
    if kind == 'IF':
        for _, body_data in block_node[1]:
            for body, deferred in body_data:
                _check_body(body, symbols)
                for d in deferred:
                    if d[0] == 'DEFER':
                        _check_raw_statement(d[1], symbols)
    elif kind in ('WHILE', 'REPEAT'):
        _, body, deferred = block_node[1]
        symbols.enter_loop()
        _check_body(body, symbols)
        symbols.exit_loop()
        for d in deferred:
            if d[0] == 'DEFER':
                _check_raw_statement(d[1], symbols)
    elif kind == 'FOR_RANGE':
        _, _, _, _, _, body, deferred = block_node[1]
        symbols.enter_loop()
        _check_body(body, symbols)
        symbols.exit_loop()
        for d in deferred:
            if d[0] == 'DEFER':
                _check_raw_statement(d[1], symbols)
    elif kind == 'FOR_EACH':
        _, _, _, body, deferred = block_node[1]
        symbols.enter_loop()
        _check_body(body, symbols)
        symbols.exit_loop()
        for d in deferred:
            if d[0] == 'DEFER':
                _check_raw_statement(d[1], symbols)

def _check_raw_statement(stmt, symbols):
    pass
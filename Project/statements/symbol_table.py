# statements/symbol_table.py
"""
Symbol table and semantic analysis for Scrap transpiler.
"""
import sys
from statements import get_handlers, parse_function_call

class Symbol:
    def __init__(self, name, cpp_type, is_function=False, param_types=None):
        self.name = name
        self.cpp_type = cpp_type
        self.is_function = is_function
        self.param_types = param_types or []

class SymbolTable:
    def __init__(self):
        self.scopes = [{}]          # list of dict name->Symbol
        self.current_function_ret = None  # expected return type for current function
        self.loop_depth = 0              # number of enclosing loops

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
        # 1. Build global symbol table from function signatures
        global_syms = SymbolTable()
        for handler, node in functions:
            if node[0] == 'FUNC':
                name, params, ret_type, _, _ = node[1]
                param_types = [SemanticAnalyzer._to_cpp_type(pt) for pname, pt in params]
                cpp_ret = SemanticAnalyzer._to_cpp_type(ret_type)
                global_syms.declare(name, cpp_ret, is_function=True, param_types=param_types)

        # 2. Check function bodies
        for handler, node in functions:
            if node[0] == 'FUNC':
                SemanticAnalyzer._check_function(node, global_syms)

        # 3. Check top-level statements (implicit main scope)
        top_syms = SymbolTable()
        top_syms.push_scope()
        # Make global function symbols visible in top-level scope
        for name, sym in global_syms.scopes[0].items():
            if sym.is_function:
                top_syms.declare(name, sym.cpp_type, is_function=True, param_types=sym.param_types)
        SemanticAnalyzer._check_body(top_level_nodes, top_syms)

    @staticmethod
    def _to_cpp_type(scrap_type):
        mapping = {
            'int': 'int',
            'float': 'double',
            'String': 'std::string',
            'bool': 'bool',
            'void': 'void',
        }
        base = scrap_type.rstrip('*&').rstrip()
        if base in mapping:
            return mapping[base] + scrap_type[len(base):]
        return scrap_type

    @staticmethod
    def _check_function(func_node, global_syms):
        name, params, ret_type, body_items, deferred_items = func_node[1]
        local_syms = SymbolTable()
        local_syms.push_scope()
        for pname, ptype in params:
            cpp_type = SemanticAnalyzer._to_cpp_type(ptype)
            local_syms.declare(pname, cpp_type)
        local_syms.current_function_ret = SemanticAnalyzer._to_cpp_type(ret_type)

        # Check body items and deferred items
        # Deferred items are separate nodes (DEFER, stmt)
        for handler, node in body_items:
            if hasattr(handler, 'check_semantics'):
                handler.check_semantics(node, local_syms)
            else:
                SemanticAnalyzer._default_check(node, local_syms)

        for def_node in deferred_items:
            if def_node[0] == 'DEFER':
                stmt = def_node[1]
                if stmt:
                    SemanticAnalyzer._check_raw_statement(stmt, local_syms)

        # Warn if non-void function may miss return
        if local_syms.current_function_ret != 'void':
            if not SemanticAnalyzer._contains_return(body_items):
                print(f"Warning: function '{name}' may not return a value", file=sys.stderr)

    @staticmethod
    def _check_body(nodes_with_handlers, symbols):
        """nodes_with_handlers is list of (handler, node) pairs (top-level or block body)."""
        for handler, node in nodes_with_handlers:
            if hasattr(handler, 'check_semantics'):
                handler.check_semantics(node, symbols)
            else:
                SemanticAnalyzer._default_check(node, symbols)

    @staticmethod
    def _default_check(node, symbols):
        """Fallback checker for nodes without a custom check_semantics."""
        kind = node[0]
        if kind in ('IF', 'WHILE', 'FOR', 'REPEAT'):
            SemanticAnalyzer._check_block(node, symbols)
        elif kind == 'BREAK':
            # should be handled by handler-specific check if used
            pass
        elif kind == 'RETURN':
            SemanticAnalyzer._check_return(node, symbols)

    @staticmethod
    def _check_block(block_node, symbols):
        kind = block_node[0]
        if kind == 'IF':
            branches = block_node[1]
            for cond, body_data in branches:
                for body_items, deferred_items in body_data:
                    SemanticAnalyzer._check_body(body_items, symbols)
                    for def_node in deferred_items:
                        if def_node[0] == 'DEFER':
                            stmt = def_node[1]
                            if stmt:
                                SemanticAnalyzer._check_raw_statement(stmt, symbols)
        elif kind in ('WHILE', 'REPEAT'):
            body_items = block_node[1][1]      # (count, body_items, deferred_items) or (cond, body_items, deferred_items)
            deferred_items = block_node[1][2]
            symbols.enter_loop()
            SemanticAnalyzer._check_body(body_items, symbols)
            symbols.exit_loop()
            for def_node in deferred_items:
                if def_node[0] == 'DEFER':
                    stmt = def_node[1]
                    if stmt:
                        SemanticAnalyzer._check_raw_statement(stmt, symbols)
        elif kind == 'FOR':
            _, _, body_items, deferred_items = block_node[1]
            symbols.enter_loop()
            SemanticAnalyzer._check_body(body_items, symbols)
            symbols.exit_loop()
            for def_node in deferred_items:
                if def_node[0] == 'DEFER':
                    stmt = def_node[1]
                    if stmt:
                        SemanticAnalyzer._check_raw_statement(stmt, symbols)

    @staticmethod
    def _check_return(return_node, symbols):
        expr = return_node[1]
        expected = symbols.current_function_ret
        if expected is None:
            return  # not inside a function (should not happen)
        if expected == 'void':
            if expr is not None:
                raise SyntaxError("Cannot return a value from a void function")
        else:
            if expr is None:
                raise SyntaxError(f"Expected return expression of type '{expected}'")
            # Optionally: check variable type
            if isinstance(expr, str) and expr in symbols.scopes[-1]:
                var_sym = symbols.lookup(expr)
                if var_sym and var_sym.cpp_type != expected:
                    print(f"Warning: returning '{var_sym.name}' of type '{var_sym.cpp_type}' but function expects '{expected}'", file=sys.stderr)

    @staticmethod
    def _check_raw_statement(stmt_str, symbols):
        call_info = parse_function_call(stmt_str)
        if call_info:
            func_name, args, is_c = call_info
            func_sym = symbols.lookup(func_name)
            if func_sym:
                if not func_sym.is_function:
                    raise SyntaxError(f"'{func_name}' is not a function")
                if len(args) != len(func_sym.param_types):
                    raise SyntaxError(f"Function '{func_name}' expects {len(func_sym.param_types)} arguments, got {len(args)}")

    @staticmethod
    def _contains_return(body_items):
        """Check if any of the (handler, node) pairs contain a return statement (direct or nested blocks)."""
        for handler, node in body_items:
            if node[0] == 'RETURN':
                return True
            elif node[0] in ('IF', 'WHILE', 'FOR', 'REPEAT'):
                # Recurse into block
                if node[0] == 'IF':
                    for _, body_data in node[1]:
                        for b, _ in body_data:
                            if SemanticAnalyzer._contains_return(b):
                                return True
                else:
                    inner_body = node[1][1] if node[0] in ('WHILE', 'REPEAT') else node[1][2]
                    if SemanticAnalyzer._contains_return(inner_body):
                        return True
        return False
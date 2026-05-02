"""AST optimization: replace repeated ratio-like calls with a loop."""
import re
from scrap.core.debug import DEBUG

def optimize_ratio_chain(nodes):
    """Recursively optimize ratio chains in a list of nodes."""
    new_nodes = []
    i = 0
    while i < len(nodes):
        handler, node = nodes[i]
        # Recursively optimize inside block nodes
        if node[0] == 'WHILE':
            cond, body, deferred = node[1]
            body = optimize_ratio_chain(body)
            new_nodes.append((handler, ('WHILE', (cond, body, deferred))))
            i += 1
        elif node[0] == 'IF':
            branches = []
            for cond, body_data in node[1]:
                new_body_data = []
                for body, deferred in body_data:
                    body = optimize_ratio_chain(body)
                    new_body_data.append((body, deferred))
                branches.append((cond, new_body_data))
            new_nodes.append((handler, ('IF', branches)))
            i += 1
        elif node[0] in ('FOR_RANGE', 'FOR_EACH', 'REPEAT', 'FUNC'):
            if node[0] == 'FOR_RANGE':
                var, start, stop, step, body, deferred = node[1]
                body = optimize_ratio_chain(body)
                new_nodes.append((handler, ('FOR_RANGE', (var, start, stop, step, body, deferred))))
            elif node[0] == 'FOR_EACH':
                var, container, body, deferred = node[1]
                body = optimize_ratio_chain(body)
                new_nodes.append((handler, ('FOR_EACH', (var, container, body, deferred))))
            elif node[0] == 'REPEAT':
                count, body, deferred = node[1]
                body = optimize_ratio_chain(body)
                new_nodes.append((handler, ('REPEAT', (count, body, deferred))))
            elif node[0] == 'FUNC':
                name, params, ret_type, body, deferred = node[1]
                body = optimize_ratio_chain(body)
                new_nodes.append((handler, ('FUNC', (name, params, ret_type, body, deferred))))
            i += 1
        else:
            info = _is_candidate_ratio(node)
            if info:
                chain = _extract_chain(nodes, i)
                if chain:
                    if DEBUG:
                        print(f"[optimizer] ✓ Replaced ratio chain starting at index {i}")
                    new_nodes.append((None, ('OPTIMIZED_RATIO', chain)))
                    i = chain['end_index'] + 1
                    continue
            new_nodes.append((handler, node))
            i += 1
    return new_nodes

def _is_candidate_ratio(node):
    if node[0] != 'VAR':
        return None
    name, explicit_type, value = node[1], node[2], node[3]
    if explicit_type is not None or value is None:
        return None
    if DEBUG:
        print(f"[optimizer]   Checking VAR {name} = {value}")
    m = re.match(r'^([a-zA-Z_][\w:.]*)\s*\(\s*"([^"]+)"\s*,\s*([a-zA-Z_]\w*)\s*\)$', value)
    if not m:
        return None
    func_name, pattern, var_name = m.groups()
    func_name = func_name.replace('.', '::')
    return {'func': func_name, 'pattern': pattern, 'var': var_name, 'name': name}

def _extract_chain(nodes, start_idx):
    if DEBUG:
        print(f"[optimizer] _extract_chain starting at index {start_idx}")
    calls = []
    idx = start_idx
    var_name = None
    func_name = None

    while idx < len(nodes):
        h, n = nodes[idx]
        info = _is_candidate_ratio(n)
        if not info:
            if DEBUG:
                print(f"[optimizer]   Stopping at index {idx}, not a candidate ratio")
            break
        if var_name is None:
            var_name = info['var']
            func_name = info['func']
        elif info['var'] != var_name or info['func'] != func_name:
            if DEBUG:
                print(f"[optimizer]   Stopping: var {info['var']} vs {var_name}, func {info['func']} vs {func_name}")
            break
        calls.append(info)
        if DEBUG:
            print(f"[optimizer]   Collected call {len(calls)}: {info['name']} = {info['func']}(\"{info['pattern']}\", {info['var']})")
        idx += 1
    if len(calls) < 2:
        if DEBUG:
            print(f"[optimizer] Not enough ratio calls, found {len(calls)}")
        return None

    # var best = first call name
    if idx >= len(nodes):
        if DEBUG:
            print("[optimizer] Reached end before 'var best = ...'")
        return None
    h_best, n_best = nodes[idx]
    if DEBUG:
        print(f"[optimizer]   Expecting 'var best = {calls[0]['name']}', got {n_best}")
    if not (n_best[0] == 'VAR' and n_best[2] is None and n_best[3] == calls[0]['name']):
        if DEBUG:
            print("[optimizer] Failed: 'var best = rX' not found")
        return None
    best_var = n_best[1]
    idx += 1

    # var response = "..."
    if idx >= len(nodes):
        return None
    h_resp, n_resp = nodes[idx]
    if DEBUG:
        print(f"[optimizer]   Expecting 'var response = \"...\"', got {n_resp}")
    if not (n_resp[0] == 'VAR' and n_resp[2] is None and n_resp[3] and n_resp[3].startswith('"')):
        if DEBUG:
            print("[optimizer] Failed: 'var response = \"...\"' not found")
        return None
    default_response = n_resp[3][1:-1]
    response_var = n_resp[1]
    idx += 1

    responses = [default_response]
    for i, info in enumerate(calls[1:], start=2):
        if idx >= len(nodes):
            if DEBUG:
                print(f"[optimizer] Ran out of nodes before if for {info['name']}")
            return None
        h_if, n_if = nodes[idx]
        if DEBUG:
            print(f"[optimizer]   Expecting IF for {info['name']}, got {n_if[0] if n_if else 'None'}")
        if n_if[0] != 'IF':
            return None
        branches = n_if[1]
        if len(branches) != 1:
            if DEBUG:
                print(f"[optimizer] If has {len(branches)} branches, expected 1")
            return None
        cond = branches[0][0]
        expected_cond = f"{info['name']} > {best_var}"
        if cond != expected_cond:
            if DEBUG:
                print(f"[optimizer] Condition mismatch: '{cond}' vs '{expected_cond}'")
            return None
        body_nodes, _ = branches[0][1][0]
        if DEBUG:
            print(f"[optimizer]     Body has {len(body_nodes)} statements")
        found_best = False
        found_resp = False
        resp_literal = None
        for h_body, n_body in body_nodes:
            if DEBUG:
                print(f"[optimizer]       Body node: {n_body[0]}")
            if n_body[0] == 'SET_EXPR' and n_body[1] == best_var and n_body[2] == info['name']:
                found_best = True
                if DEBUG:
                    print(f"[optimizer]         Found SET_EXPR for {best_var}")
            elif n_body[0] == 'SET_STRING' and n_body[1] == response_var:
                found_resp = True
                resp_literal = n_body[2]
                if DEBUG:
                    print(f"[optimizer]         Found SET_STRING for {response_var} -> \"{resp_literal}\"")
        if not (found_best and found_resp):
            if DEBUG:
                print(f"[optimizer] Missing SET_EXPR or SET_STRING in if for {info['name']}")
            return None
        responses.append(resp_literal)
        idx += 1

    fallback = None
    threshold = None
    if idx < len(nodes):
        h_final, n_final = nodes[idx]
        if DEBUG:
            print(f"[optimizer]   Checking final if at index {idx}: {n_final[0] if n_final else 'None'}")
        if n_final[0] == 'IF':
            branches = n_final[1]
            if len(branches) == 1:
                cond = branches[0][0]
                m = re.match(rf'^{best_var}\s*<\s*(\d+)$', cond)
                if m:
                    threshold = int(m.group(1))
                    body_nodes, _ = branches[0][1][0]
                    if len(body_nodes) == 1 and body_nodes[0][1][0] == 'SET_STRING' and body_nodes[0][1][1] == response_var:
                        fallback = body_nodes[0][1][2]
                        if DEBUG:
                            print(f"[optimizer]     Found fallback: if {best_var} < {threshold} -> \"{fallback}\"")
                        idx += 1
    if fallback is None:
        threshold = 0
        fallback = ""

    if DEBUG:
        print(f"[optimizer] ✓ Successfully optimized: {len(calls)} patterns, threshold={threshold}, fallback='{fallback}'")
    return {
        'func': func_name,
        'var': var_name,
        'best_var': best_var,
        'response_var': response_var,
        'patterns': [c['pattern'] for c in calls],
        'responses': responses,
        'fallback': fallback,
        'threshold': threshold,
        'end_index': idx - 1
    }
"""Helper to generate C++ code for OPTIMIZED_RATIO nodes."""

def generate_optimized_ratio_block(data, indent):
    """Generate C++ code for a loop-based pattern matcher."""
    lines = []
    func = data['func']
    var = data['var']
    best_var = data['best_var']
    response_var = data['response_var']
    patterns = data['patterns']
    responses = data['responses']
    fallback = data['fallback']
    threshold = data['threshold']

    lines.append(f'{indent}// Optimized ratio block')
    lines.append(f'{indent}const char* patterns[] = {{')
    for p in patterns:
        lines.append(f'{indent}    "{p}",')
    lines.append(f'{indent}}};')
    lines.append(f'{indent}const char* responses[] = {{')
    for r in responses:
        lines.append(f'{indent}    "{r}",')
    lines.append(f'{indent}}};')
    lines.append(f'{indent}int {best_var} = 0;')
    lines.append(f'{indent}int best_idx = 0;')
    lines.append(f'{indent}for (int i = 0; i < {len(patterns)}; i++) {{')
    lines.append(f'{indent}    int score = {func}(patterns[i], {var});')
    lines.append(f'{indent}    if (score > {best_var}) {{ {best_var} = score; best_idx = i; }}')
    lines.append(f'{indent}}}')
    if threshold > 0:
        lines.append(f'{indent}const char* {response_var} = ({best_var} < {threshold}) ? "{fallback}" : responses[best_idx];')
    else:
        lines.append(f'{indent}const char* {response_var} = responses[best_idx];')
    return lines
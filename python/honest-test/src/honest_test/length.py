"""Length-bounded predicate generation (section 3.4).

For predicates that constrain string length, read the bounds from the comparison operators
and generate a string at every valid length, plus the boundary lengths just outside the
range. Boundary testing is symmetric: one under the minimum and one over the maximum.

The bounds come from the AST, via honest-parse. `len(s) == 5` is min == max == 5; `len(s)
<= 8` is (1, 8); a pure lower bound with no maximum is unbounded above and falls to
supplied-values (section 3.6). Pure functions; no I/O.
"""

from honest_parse import node_text, parse_python, walk

_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"

_OPERATORS = frozenset({"<", "<=", "==", ">=", ">"})

# For `len(s) OP N` (len on the left): which bound the operator sets, and the offset applied
# to N. "both" means an exact length (==), setting min and max together.
_BOUND = {
    "<": ("max", -1),
    "<=": ("max", 0),
    ">": ("min", 1),
    ">=": ("min", 0),
    "==": ("both", 0),
}

# `N OP len(s)` (len on the right) is the same as `len(s) FLIP(OP) N`.
_FLIP = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "=="}


def _is_len_call(node, source):
    if node.type != "call":
        return False
    fn = node.child_by_field_name("function")
    return fn is not None and fn.type == "identifier" and node_text(fn, source) == "len"


def _int_value(node, source):
    if node.type != "integer":
        return None
    return int(node_text(node, source))


def _apply(which, value, bounds):
    """Accumulate a bound: the tightest min/max wins across all comparisons."""
    if which in ("min", "both"):
        bounds["min"] = max(bounds["min"], value)
    if which in ("max", "both"):
        bounds["max"] = value if bounds["max"] is None else min(bounds["max"], value)


def _bound_from_pair(left, op, right, source, bounds):
    """Derive a bound from one comparison `left op right`, when one side is len(...) and the
    other an integer literal. Other comparisons contribute nothing."""
    if op not in _BOUND:
        return
    right_int = _int_value(right, source)
    if _is_len_call(left, source) and right_int is not None:
        which, delta = _BOUND[op]
        _apply(which, right_int + delta, bounds)
        return
    left_int = _int_value(left, source)
    if _is_len_call(right, source) and left_int is not None:
        which, delta = _BOUND[_FLIP[op]]
        _apply(which, left_int + delta, bounds)


def _scan_comparison(comparison, source, bounds):
    """Flatten a (possibly chained) comparison into operand/operator items, then derive a
    bound from each adjacent operand-operator-operand triple."""
    items = []
    for child in comparison.children:
        if child.type in _OPERATORS:
            items.append(("op", child.type))
            continue
        if child.is_named:
            items.append(("operand", child))
    for i in range(0, len(items) - 2, 2):
        (kind_left, left), (kind_op, op), (kind_right, right) = items[i], items[i + 1], items[i + 2]
        if kind_left == "operand" and kind_op == "op" and kind_right == "operand":
            _bound_from_pair(left, op, right, source, bounds)


def extract_length_bounds(source):
    """The (min, max) length a predicate allows (section 3.4). min defaults to 1; max is None
    when there is no upper bound (unbounded above)."""
    bounds = {"min": 1, "max": None}
    source_bytes = source.encode("utf-8")
    root = parse_python(source_bytes).root_node
    for node in walk(root):
        if node.type == "comparison_operator":
            _scan_comparison(node, source_bytes, bounds)
    return bounds["min"], bounds["max"]


def _string_of_length(n, chars):
    """A string of exactly length n, repeating chars as needed (so lengths beyond len(chars)
    are still generated)."""
    if n <= 0:
        return ""
    repeats = (n // len(chars)) + 1
    return (chars * repeats)[:n]


def enumerate_lengths(source, chars=_CHARS):
    """Valid and boundary-invalid strings for a length-bounded predicate (section 3.4). When
    the predicate is unbounded above, valid/invalid are empty (it falls to supplied-values)."""
    min_len, max_len = extract_length_bounds(source)
    if max_len is None:
        return {"min": min_len, "max": None, "valid": [], "invalid": []}
    valid = [_string_of_length(n, chars) for n in range(min_len, max_len + 1)]
    invalid = [_string_of_length(max_len + 1, chars)]
    if min_len > 1:
        invalid.append(_string_of_length(min_len - 1, chars))
    return {"min": min_len, "max": max_len, "valid": valid, "invalid": invalid}

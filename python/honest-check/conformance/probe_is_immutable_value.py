# scenario: is_immutable_value
# inherits: hd=python/honest-check/honest-check.hd::is_immutable_value -> feature=specs/features/honest-check.feature::is_immutable_value
"""Honest probe for honest-check's is_immutable_value (feature Scenario: is_immutable_value).

Scenario: is_immutable_value returns true when a module-level binding's right
side is provably immutable — a number, a string, a bool, None, a tuple literal, a
negated immutable, or a frozenset(...) call — and false for everything else (a
list, dict or set literal, a comprehension, and so on). Each case gives an
assignment snippet, parsed under the real Python grammar; the probe hands the
right-hand value node to the real function and pins the exact boolean. Every row
below is one of the categories the scenario names.

honest-parse is built; the value node is the real tree-sitter `right` child of a
real assignment, never fabricated.
"""

from honest_parse import parse, walk

# Each case: an assignment whose right side is the value under test, and whether
# that value is provably immutable per the scenario's enumeration.
_CASES = [
    {"src": "_ = 3.5", "expect": True},
    {"src": "_ = False", "expect": True},
    {"src": "_ = list()", "expect": False},
    {"src": "_ = 42", "expect": True},                 # a number
    {"src": '_ = "s"', "expect": True},                # a string
    {"src": "_ = True", "expect": True},               # a bool
    {"src": "_ = None", "expect": True},               # None
    {"src": "_ = (1, 2)", "expect": True},             # a tuple literal
    {"src": '_ = - \\\n    1\n', "expect": True},
    {"src": "_ = -1", "expect": True},                 # a negated immutable
    {"src": "_ = frozenset([1, 2])", "expect": True},  # a frozenset(...) call
    {"src": "_ = [1, 2]", "expect": False},            # a list literal
    {"src": '_ = {"a": 1}', "expect": False},          # a dict literal
    {"src": "_ = {1, 2}", "expect": False},            # a set literal
    {"src": "_ = [x for x in y]", "expect": False},    # a comprehension
]


def _rhs_node(src):
    """The `right` child of the first assignment in a parsed snippet."""
    root = parse(src.encode(), "python").root_node
    for node in walk(root):
        if node.type == "assignment":
            return node.child_by_field_name("right")
    return None


def probe_is_immutable_value():
    """is_immutable_value is true exactly for the provably-immutable value kinds."""
    try:
        from honest_check import is_immutable_value
    except ImportError as exc:
        return [f"cannot import is_immutable_value: {exc}"]

    bad = []
    for case in _CASES:
        node = _rhs_node(case["src"])
        if node is None:
            bad.append(f"no assignment right side parsed from {case['src']!r}")
            continue
        got = is_immutable_value(node)
        if got != case["expect"]:
            bad.append(
                f"is_immutable_value({case['src']!r}) -> {got!r}, expected {case['expect']!r}"
            )
    return bad

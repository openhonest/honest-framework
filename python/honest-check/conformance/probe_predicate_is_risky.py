# scenario: predicate_is_risky
# inherits: hd=python/honest-check/honest-check.hd::predicate_is_risky -> feature=specs/features/honest-check.feature::predicate_is_risky
"""Conformance probe for honest-check's predicate_is_risky.

Scenario (specs/features/honest-check.feature, Scenario: predicate_is_risky):
    Given value: Node
    When predicate_is_risky is called
    Then it returns true when a predicate's expression holds a node that throws on a
    non-matching input - a call to bare `int` or `float`, a subscript access, or a
    `/` or `//` division - because a predicate that throws is a recognizer that rejects
    by exception (HC009).

The probe parses each recognizer snippet with the real honest-parse grammar, hands the
lambda node (the recognizer's value node per base_types_of) to the real function, and
checks the boolean against the literal the scenario fixes.
"""

import honest_parse

# Each case: a recognizer value expression, and whether it throws on a non-match (risky).
_CASES = [
    {"src": "r = lambda x: int(x)", "expect": True},    # bare int() call throws on non-numeric
    {"src": "r = lambda x: float(x)", "expect": True},  # bare float() call throws
    {"src": "r = lambda x: x[0]", "expect": True},      # subscript throws on short/empty
    {"src": "r = lambda x: a / x", "expect": True},     # division throws on zero
    {"src": "r = lambda x: a // x", "expect": True},    # floor division throws on zero
    {"src": "r = lambda x: x + 1", "expect": False},
    {"src": "r = lambda x: x == 5", "expect": False},   # comparison never throws (absence/safe)
    {"src": "r = lambda x: x in items", "expect": False},  # membership never throws (safe)
]


def _lambda_node(src):
    tree = honest_parse.parse(src.encode("utf-8"), "python")
    for node in honest_parse.walk(tree.root_node):
        if node.type == "lambda":
            return node
    return None


def probe_predicate_is_risky():
    """A throwing recognizer (int/float call, subscript, or division) is risky; a comparison or membership test is not (HC009)."""
    try:
        from honest_check import predicate_is_risky
    except ImportError as exc:
        return [f"cannot import predicate_is_risky: {exc}"]

    bad = []
    for case in _CASES:
        value = _lambda_node(case["src"])
        if value is None:
            bad.append(f"probe setup: no lambda node parsed from {case['src']!r}")
            continue
        try:
            got = predicate_is_risky(value)
        except Exception as exc:  # a probe reports faults as data, never raises
            bad.append(f"predicate_is_risky({case['src']!r}) raised {exc!r}")
            continue
        if got != case["expect"]:
            bad.append(f"predicate_is_risky({case['src']!r}) -> {got!r}, expected {case['expect']!r}")
    return bad

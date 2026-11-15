"""Honest probe for honest-check's canonical_body (feature Scenario: canonical_body).

canonical_body reduces a function body to a structural signature with every
literal value blanked: each body node becomes its grammar type, except an
identifier, which keeps its name — so two bodies match when they differ only in
the constants they name (HC-P014).

The scenario fixes the MATCH RELATION, not the signature's exact format, so this
probe tests the relation the scenario states: two signatures are equal when the
bodies differ only in a constant, and unequal when they differ in an identifier
name or in structure. The inequality cases are what make this non-vacuous — a
stub that returns one constant value for every body makes all bodies compare
equal and so fails the two 'equal: False' cases. Nodes are real tree-sitter
nodes parsed by honest-parse; none is fabricated.
"""

from honest_parse import parse, walk


def _fdef(src):
    root = parse(src.encode(), "python").root_node
    return [n for n in walk(root) if n.type == "function_definition"][0]


# Each case: two function sources and whether their canonical_body signatures
# must be equal, per the scenario's match relation.
_CASES = [
    # Differ only in a blanked constant -> same signature.
    {"a": "def f():\n    return 1", "b": "def f():\n    return 2", "equal": True},
    # Differ in an identifier, which keeps its name -> different signature.
    {"a": "def f():\n    return x", "b": "def f():\n    return y", "equal": False},
    # Differ in structure (a return vs an assignment) -> different signature.
    {"a": "def f():\n    return 1", "b": "def f():\n    x = 1", "equal": False},
]


def probe_canonical_body():
    """canonical_body makes two bodies match iff they differ only in the constants they name."""
    try:
        from honest_check import canonical_body
    except ImportError as exc:
        return [f"cannot import canonical_body: {exc}"]

    bad = []
    for case in _CASES:
        sig_a = canonical_body(_fdef(case["a"]))
        sig_b = canonical_body(_fdef(case["b"]))
        got_equal = sig_a == sig_b
        if got_equal != case["equal"]:
            bad.append(
                f"canonical_body signatures of {case['a']!r} and {case['b']!r} "
                f"compare equal={got_equal}, expected equal={case['equal']} "
                f"(got {sig_a!r} vs {sig_b!r})"
            )
    return bad

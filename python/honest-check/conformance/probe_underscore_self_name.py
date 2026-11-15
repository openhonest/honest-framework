"""Honest probe for honest-check's underscore_self_name (Scenario: underscore_self_name).

underscore_self_name returns the attribute name of a `self._name` assignment
target whose name starts with an underscore, or NOTHING (None) when the target is
not that shape (HC-P007). The cases parse real Python with honest-parse, hand the
real assignment-target node to the function, and pin the name it must return — the
`self._secret` target returns "_secret", while a public `self.public` target and a
plain `value` target each return None.
"""

from honest_parse import parse, walk


def _assignment_left(source):
    root = parse(source.encode("utf-8"), "python").root_node
    for node in walk(root):
        if node.type == "assignment":
            return node.child_by_field_name("left")
    return None


# Each case: real source, and the attribute name underscore_self_name must return.
_CASES = [
    {"source": "self._secret = 1\n", "expect": "_secret"},   # underscore instance attr
    {"source": "self.public = 1\n", "expect": None},         # no leading underscore
    {"source": "value = 1\n", "expect": None},               # plain identifier, not self.attr
]


def probe_underscore_self_name():
    """underscore_self_name returns the `self._name` attribute name, else None."""
    try:
        from honest_check import underscore_self_name
    except ImportError as exc:
        return [f"cannot import underscore_self_name: {exc}"]

    bad = []
    for case in _CASES:
        target = _assignment_left(case["source"])
        if target is None:
            bad.append(f"test setup: no assignment target in {case['source']!r}")
            continue
        got = underscore_self_name(target)
        if got != case["expect"]:
            bad.append(
                f"underscore_self_name({case['source']!r}) -> {got!r}, expected {case['expect']!r}"
            )
    return bad

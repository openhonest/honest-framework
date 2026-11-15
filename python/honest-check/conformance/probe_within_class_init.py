"""Honest probe for honest-check's within_class_init (Scenario: within_class_init).

within_class_init returns true when a node's nearest enclosing function is an
`__init__` that is a method of a class — the scope HC-P007 reads for hidden
instance state.

Cases parse real Python, build a real CheckContext, and hand the real node to the
function: a `self.x = 1` inside a class's `__init__` (true), an `x = 1` inside a
class's ordinary method `foo` (false, the enclosing function is not `__init__`),
and an `x = 1` inside a module-level function literally named `__init__` but
belonging to no class (false, because it is not a method of a class). The last
case pins the "method of a class" clause: a stub that only checks the name
`__init__` would wrongly return true. A stub that returns False fails the true
case.
"""

from honest_parse import parse, walk


def _ctx(root):
    return {
        "root": root,
        "nodes": walk(root),
        "aliases": {},
        "roles": {},
        "source": root.text,
        "path": "case.py",
        "rule_config": {},
    }


def _find_assignment(root):
    for n in walk(root):
        if n.type == "assignment":
            return n
    return None


# Each case: a real source, and whether the assignment node in it sits in a class
# __init__ method.
_CASES = [
    {
        "source": "class C:\n    def __init__(self):\n        self.x = 1\n",
        "expect": True,
    },
    {
        "source": "class C:\n    def foo(self):\n        x = 1\n",
        "expect": False,
    },
    {
        # A module-level function named __init__ is not a method of a class.
        "source": "def __init__(self):\n    x = 1\n",
        "expect": False,
    },
]


def probe_within_class_init():
    """within_class_init is true only inside the __init__ method of a class."""
    try:
        from honest_check import within_class_init
    except ImportError as exc:
        return [f"cannot import within_class_init: {exc}"]

    bad = []
    for case in _CASES:
        root = parse(case["source"].encode("utf-8"), "python").root_node
        ctx = _ctx(root)
        node = _find_assignment(root)
        if node is None:
            bad.append(f"test setup: no assignment node in {case['source']!r}")
            continue
        got = within_class_init(ctx, node)
        if bool(got) != case["expect"]:
            bad.append(
                f"within_class_init(<assignment> in {case['source']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad

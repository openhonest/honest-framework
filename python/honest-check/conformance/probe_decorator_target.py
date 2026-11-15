"""Honest probe for honest-check's decorator_target (Scenario: decorator_target).

decorator_target returns the final name a decorator names — `boundary` from
@boundary, `lru_cache` from @functools.lru_cache(maxsize=1) — or None when the
decorator is neither a plain nor a dotted name, called or bare. The cases parse
real Python with honest-parse and hand the real decorator node to the function,
pinning the returned name for a bare name, a dotted-and-called decorator and a
dotted-and-called decorator, plus the explicit None for a subscript decorator
(`@registry[0]`), which is neither a plain nor a dotted name.
"""

# Each case: a real one-decorator source and the final name decorator_target must
# return (None for a decorator that is not a plain or dotted name).
_CASES = [
    {"source": "@boundary\ndef f():\n    pass\n", "expect": "boundary"},
    {"source": "@functools.lru_cache(maxsize=1)\ndef f():\n    pass\n", "expect": "lru_cache"},
    {"source": "@app.route('/x')\ndef f():\n    pass\n", "expect": "route"},
    # Absence: a subscript decorator names no plain-or-dotted target -> None.
    {"source": "@registry[0]\ndef f():\n    pass\n", "expect": None},
]


def probe_decorator_target():
    """decorator_target returns a decorator's final name, or None when it names no plain/dotted name."""
    try:
        from honest_check import decorator_target
        from honest_parse import parse, walk
    except ImportError as exc:
        return [f"cannot import decorator_target: {exc}"]

    bad = []
    for case in _CASES:
        tree = parse(case["source"].encode("utf-8"), "python")
        root = tree.root_node
        decorator = None
        for node in walk(root):
            if node.type == "decorator":
                decorator = node
                break
        if decorator is None:
            bad.append(f"test setup: no decorator node in {case['source']!r}")
            continue
        got = decorator_target(decorator)
        if got != case["expect"]:
            bad.append(
                f"decorator_target({case['source']!r}) -> {got!r}, expected {case['expect']!r}"
            )
    return bad

"""Honest probe for honest-check's body_has_call (Scenario: body_has_call).

body_has_call returns true when a function's own body contains a call — the mark
of behaviour worth sharing — and false when the body carries no call, because a
body with no call carries no logic two functions could collapse into one (HC-P014).

Cases parse real Python: a `def f` that calls `g()` (true), a `def f` that only
assigns `x = 1` (false), and a `def f` whose only call `h()` sits inside a nested
`def g` (false, because the call is the nested scope's own, not f's own body).
The false cases make it non-vacuous against a stub that returns True; the true
case fails a stub that returns False.
"""

from honest_parse import parse, walk


def _fdef(src):
    root = parse(src.encode("utf-8"), "python").root_node
    for n in walk(root):
        if n.type == "function_definition":
            return n
    return None


# Each case: a real source for the outer function and whether its OWN body
# contains a call.
_CASES = [
    {"source": "def f():\n    g()\n", "expect": True},
    {"source": "def f():\n    x = 1\n", "expect": False},
    {
        # The only call sits inside a nested def, not in f's own body.
        "source": "def f():\n    def g():\n        h()\n    x = 1\n",
        "expect": False,
    },
]


def probe_body_has_call():
    """body_has_call is true iff the function's own body (not a nested scope) holds a call."""
    try:
        from honest_check import body_has_call
    except ImportError as exc:
        return [f"cannot import body_has_call: {exc}"]

    bad = []
    for case in _CASES:
        fdef = _fdef(case["source"])
        if fdef is None:
            bad.append(f"test setup: no function_definition in {case['source']!r}")
            continue
        got = body_has_call(fdef)
        if got != case["expect"]:
            bad.append(
                f"body_has_call({case['source']!r}) -> {got!r}, expected {case['expect']!r}"
            )
    return bad

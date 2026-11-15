"""Honest probe for honest-check's body_statement_count (Scenario: body_statement_count).

body_statement_count returns the count of statements in a function's own body,
not descending into nested scopes (HC-P014).

Cases parse real Python: a `def f` with two assignments (2), a `def f` whose body
is a single `pass` (1), and a `def f` with two assignments plus a nested `def g`
holding one statement — the nested def counts as one statement of f's own body and
g's inner statement is not descended into (3). The nested case pins the
non-descent: a full-walk count would return more than 3. A stub returning 0 fails
every case.
"""

from honest_parse import parse, walk


def _fdef(src):
    root = parse(src.encode("utf-8"), "python").root_node
    for n in walk(root):
        if n.type == "function_definition":
            return n
    return None


# Each case: a real source and the count of statements in the function's own body.
_CASES = [
    {"source": "def f():\n    a = 1\n    b = 2\n", "expect": 2},
    {"source": "def f():\n    pass\n", "expect": 1},
    {
        # a = 1, b = 2, and the nested `def g` statement: 3. g's inner c = 3 is
        # not descended into.
        "source": "def f():\n    a = 1\n    b = 2\n    def g():\n        c = 3\n",
        "expect": 3,
    },
]


def probe_body_statement_count():
    """body_statement_count counts own-body statements, a nested def as one, not its insides."""
    try:
        from honest_check import body_statement_count
    except ImportError as exc:
        return [f"cannot import body_statement_count: {exc}"]

    bad = []
    for case in _CASES:
        fdef = _fdef(case["source"])
        if fdef is None:
            bad.append(f"test setup: no function_definition in {case['source']!r}")
            continue
        got = body_statement_count(fdef)
        if got != case["expect"]:
            bad.append(
                f"body_statement_count({case['source']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad

"""Honest probe for honest-check's own_body (Scenario: own_body).

own_body returns the body descendants belonging to a function itself, not
descending into a deeper nested def, lambda or decorated def — those statements
are the inner scope's own.

The scenario fixes the MEMBERSHIP RELATION, not the collection's exact format, so
this probe tests that relation over real nodes: in `def f` holding `x = 1` and a
nested `def g` holding `y = 2`, own_body's result carries a node for `x = 1` (the
function's own statement) and no node for `y = 2` (the nested scope's own). The
two directions make it non-vacuous: a stub that returns an empty collection fails
the "carries x = 1" check, and a stub that returns the whole walk (descending into
g) fails the "excludes y = 2" check.
"""

from honest_parse import parse, walk


def _fdef(src):
    root = parse(src.encode("utf-8"), "python").root_node
    for n in walk(root):
        if n.type == "function_definition":
            return n
    return None


_SOURCE = "def f():\n    x = 1\n    def g():\n        y = 2\n"


def probe_own_body():
    """own_body carries the function's own statements and excludes a nested def's."""
    try:
        from honest_check import own_body
    except ImportError as exc:
        return [f"cannot import own_body: {exc}"]

    bad = []
    fdef = _fdef(_SOURCE)
    if fdef is None:
        return [f"test setup: no function_definition in {_SOURCE!r}"]
    got = own_body(fdef)
    texts = {n.text.decode() for n in got}
    if "x = 1" not in texts:
        bad.append(
            f"own_body(def f) -> texts {sorted(texts)!r}, missing the function's "
            f"own statement 'x = 1'"
        )
    if "y = 2" in texts:
        bad.append(
            f"own_body(def f) -> texts {sorted(texts)!r}, wrongly descended into "
            f"nested def g and carried 'y = 2'"
        )
    return bad

"""Honest probe for honest-check's mutated_names (Scenario: mutated_names).

mutated_names returns the names an assignment or augmented assignment targets
directly in a function body — the left of each `x = ...` or `x += ...` whose
target is a plain identifier.

One case parses a real `def f` whose body holds `a = 1` (plain assignment),
`b += 2` (augmented assignment), `obj.attr = 3` (attribute target, not a plain
identifier) and `c, d = 1, 2` (tuple target, not a plain identifier). The
statements handed in are the function's descendant nodes. mutated_names must
return exactly the plain-identifier targets {a, b}. The excluded `obj.attr` and
`c, d` are what make it non-vacuous: a stub returning every assignment target, or
an empty set, fails. Compared as a set so list or set return shape both pass.
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


_SOURCE = "def f():\n    a = 1\n    b += 2\n    obj.attr = 3\n    c, d = 1, 2\n"
_EXPECT = {"a", "b"}


def probe_mutated_names():
    """mutated_names returns the plain-identifier assignment targets, not attribute or tuple ones."""
    try:
        from honest_check import mutated_names
    except ImportError as exc:
        return [f"cannot import mutated_names: {exc}"]

    bad = []
    root = parse(_SOURCE.encode("utf-8"), "python").root_node
    ctx = _ctx(root)
    fdef = None
    for n in walk(root):
        if n.type == "function_definition":
            fdef = n
            break
    if fdef is None:
        return [f"test setup: no function_definition in {_SOURCE!r}"]
    statements = list(walk(fdef))
    got = mutated_names(ctx, statements)
    if set(got) != _EXPECT:
        bad.append(
            f"mutated_names over {_SOURCE!r} -> {sorted(got)!r}, "
            f"expected {sorted(_EXPECT)!r}"
        )
    return bad

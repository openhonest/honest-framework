# scenario: _checked_tree wraps the original clean tree
# inherits: hd=python/honest-parse/honest-parse.hd::_checked_tree -> feature=specs/features/honest-parse.feature::_checked_tree wraps the original clean tree
"""Verify that _checked_tree wraps the original clean tree."""


def probe__checked_tree_clean():
    try:
        from honest_parse import _checked_tree, parse
    except ImportError as exc:
        return [f"cannot import _checked_tree: {exc}"]

    tree = parse(b"value = 1\n", "python")
    got = _checked_tree(tree, "clean.py", "python")
    if not isinstance(got, dict) or got.keys() != {"ok"} or got["ok"] is not tree:
        return [f"_checked_tree returned {got!r}, expected the identical clean tree in the ok arm"]
    return []

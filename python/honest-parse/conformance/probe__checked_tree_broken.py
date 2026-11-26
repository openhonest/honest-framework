# scenario: _checked_tree returns a located fault for a recovered tree
# inherits: hd=python/honest-parse/honest-parse.hd::_checked_tree -> feature=specs/features/honest-parse.feature::_checked_tree returns a located fault for a recovered tree
"""Verify that _checked_tree returns a located fault for a recovered tree."""


def probe__checked_tree_broken():
    try:
        from honest_parse import _checked_tree, parse
    except ImportError as exc:
        return [f"cannot import _checked_tree: {exc}"]

    tree = parse(b"value = 1\ndef f(:\n", "python")
    result = _checked_tree(tree, "broken.py", "python")
    detail = result.get("err", {}) if isinstance(result, dict) else {}
    observed = (detail.get("code"), detail.get("category"), detail.get("detail"))
    expected = ("syntax_error", "client", {"path": "broken.py", "line": 2, "col": 7})
    message = detail.get("message", "")
    if observed != expected or not all(word in message for word in ("broken.py", "python", "line 2", "column 7")):
        return [f"expected the first recovery location, got {result!r}"]
    return []

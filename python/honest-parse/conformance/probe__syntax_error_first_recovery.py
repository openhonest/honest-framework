# scenario: _syntax_error reports the first recovery node location
# inherits: hd=python/honest-parse/honest-parse.hd::_syntax_error -> feature=specs/features/honest-parse.feature::_syntax_error reports the first recovery node location
"""Verify that _syntax_error reports the first recovery node location."""


def probe__syntax_error_first_recovery():
    try:
        from honest_parse import _syntax_error, parse
    except ImportError as exc:
        return [f"cannot import _syntax_error: {exc}"]

    tree = parse(b"value = 1\ndef f(:\n", "python")
    result = _syntax_error(tree.root_node, "broken.py", "python")
    detail = result.get("err", {}) if isinstance(result, dict) else {}
    observed = (detail.get("code"), detail.get("category"), detail.get("detail"))
    expected = ("syntax_error", "client", {"path": "broken.py", "line": 2, "col": 7})
    message = detail.get("message", "")
    if observed != expected or not all(word in message for word in ("broken.py", "python", "line 2", "column 7")):
        return [f"expected the first recovery location, got {result!r}"]
    return []

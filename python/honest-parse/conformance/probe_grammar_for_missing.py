# scenario: grammar_for returns a fault for a missing grammar
# inherits: hd=python/honest-parse/honest-parse.hd::grammar_for -> feature=specs/features/honest-parse.feature::grammar_for returns a fault for a missing grammar
"""Verify that grammar_for returns a fault for a missing grammar."""


def probe_grammar_for_missing():
    try:
        from honest_parse import grammar_for
    except ImportError as exc:
        return [f"cannot import grammar_for: {exc}"]

    result = grammar_for("unknown-grammar")
    detail = result.get("err", {}) if isinstance(result, dict) else {}
    observed = (detail.get("code"), detail.get("category"), detail.get("detail"))
    expected = ("unknown_grammar", "server", {"language": "unknown-grammar"})
    if observed != expected:
        return [f"expected unknown grammar fault {expected!r}, got {result!r}"]
    return []

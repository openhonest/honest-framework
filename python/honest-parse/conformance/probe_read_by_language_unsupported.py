# scenario: read_by_language returns the missing grammar fault
# inherits: hd=python/honest-parse/honest-parse.hd::read_by_language -> feature=specs/features/honest-parse.feature::read_by_language returns the missing grammar fault
"""Verify that read_by_language returns the missing grammar fault."""


def probe_read_by_language_unsupported():
    try:
        from honest_parse import read_by_language
    except ImportError as exc:
        return [f"cannot import read_by_language: {exc}"]

    result = read_by_language(b"value = 1\n", "unknown-grammar")
    detail = result.get("err", {}) if isinstance(result, dict) else {}
    observed = (detail.get("code"), detail.get("category"), detail.get("detail"))
    expected = ("unknown_grammar", "server", {"language": "unknown-grammar"})
    if observed != expected:
        return [f"expected unknown grammar fault {expected!r}, got {result!r}"]
    return []

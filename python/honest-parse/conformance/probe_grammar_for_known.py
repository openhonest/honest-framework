# scenario: grammar_for returns the known grammar handle
# inherits: hd=python/honest-parse/honest-parse.hd::grammar_for -> feature=specs/features/honest-parse.feature::grammar_for returns the known grammar handle
"""Verify that grammar_for returns the known grammar handle."""


def probe_grammar_for_known():
    try:
        from honest_parse import _LANGUAGES, grammar_for
    except ImportError as exc:
        return [f"cannot import grammar_for: {exc}"]

    expected = _LANGUAGES["python"]
    got = grammar_for("python")
    if got is not expected:
        return [f"grammar_for returned {got!r}, expected the Python table handle"]
    return []

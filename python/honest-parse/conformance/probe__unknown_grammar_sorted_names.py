# scenario: _unknown_grammar reports the request and sorted supported names
# inherits: hd=python/honest-parse/honest-parse.hd::_unknown_grammar -> feature=specs/features/honest-parse.feature::_unknown_grammar reports the request and sorted supported names
"""Verify that _unknown_grammar reports the request and sorted supported names."""


def probe__unknown_grammar_sorted_names():
    try:
        from honest_parse import _unknown_grammar
    except ImportError as exc:
        return [f"cannot import _unknown_grammar: {exc}"]

    language = "unknown-grammar"
    names = "css, elixir, go, hd, html, javascript, jinja, php, python, ruby"
    got = _unknown_grammar(language)
    detail = got.get("err", {}) if isinstance(got, dict) else {}
    message = detail.get("message", "")
    observed = (detail.get("code"), detail.get("category"), detail.get("detail"))
    expected = ("unknown_grammar", "server", {"language": language})
    if observed != expected or language not in message or names not in message:
        return [f"expected {language!r} and the sorted supported names {names!r} in a server fault, got {got!r}"]
    return []

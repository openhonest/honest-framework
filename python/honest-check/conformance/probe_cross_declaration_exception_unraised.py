# scenario: cross_declaration requires a verified exception export to be named in raises
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration requires a verified exception export to be named in raises
_SOURCES = {
    'src/example/__init__.py': b'from .errors import LocalError as PublicError\n\n__all__ = ["PublicError"]\n',
    'src/example/errors.py': b'class LocalError(Exception):\n    pass\n',
}
_DECLARATION = 'module example\n  layer correctness\n  fn run : () -> int note "declared ahead of implementation"\n'


def probe_cross_declaration_exception_unraised():
    """Cross the real Python package fixture using only HC-REF005."""
    from honest_check import cross_declaration
    from honest_design import read_hd

    declaration = read_hd(_DECLARATION)["ok"]["modules"][0]
    sources = [{"path": path, "text": source} for path, source in _SOURCES.items()]
    findings = cross_declaration(sources, declaration, _SOURCES["src/example/__init__.py"], ["HC-REF005"])
    actual = [
        (row["rule_id"], row["severity"], "PublicError" in row["message"])
        for row in findings
    ]
    expected = [("HC-REF005", "error", True)]
    if actual != expected:
        return [f"cross_declaration returned {findings!r}, expected one missing declaration for PublicError"]
    return []

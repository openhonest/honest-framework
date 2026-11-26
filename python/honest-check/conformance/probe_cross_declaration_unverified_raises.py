# scenario: cross_declaration keeps findings for unresolved exports and ordinary functions despite raises
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration keeps findings for unresolved exports and ordinary functions despite raises
_SOURCES = {
    'src/example/__init__.py': b'from .absent import MissingError\n\n__all__ = ["MissingError", "uncarded", "wrong_arity"]\n\ndef uncarded():\n    return 1\n\ndef wrong_arity(left, right):\n    return left + right\n',
}
_DECLARATION = 'module example\n  layer correctness\n  fn wrong_arity : (left: int) -> int raises MissingError, uncarded, wrong_arity note "declares one parameter"\n'


def probe_cross_declaration_unverified_raises():
    """Cross the real Python package fixture using only HC-REF005."""
    from honest_check import cross_declaration
    from honest_design import read_hd

    declaration = read_hd(_DECLARATION)["ok"]["modules"][0]
    sources = [{"path": path, "text": source} for path, source in _SOURCES.items()]
    findings = cross_declaration(sources, declaration, _SOURCES["src/example/__init__.py"], ["HC-REF005"])
    actual = sorted(
        (
            row["rule_id"],
            row["severity"],
            tuple(name for name in ("MissingError", "uncarded", "wrong_arity") if name in row["message"]),
        )
        for row in findings
    )
    expected = [
        ("HC-REF005", "error", ("MissingError",)),
        ("HC-REF005", "error", ("uncarded",)),
        ("HC-REF005", "error", ("wrong_arity",)),
    ]
    if actual != expected:
        return [f"cross_declaration returned {findings!r}, expected two missing exports and the arity error"]
    return []

# scenario: cross_declaration accepts a verified raised exception export without function arity
# inherits: hd=python/honest-check/honest-check.hd::cross_declaration -> feature=specs/features/honest-check.feature::cross_declaration accepts a verified raised exception export without function arity
_SOURCES = {
    'src/example/__init__.py': b'from .errors import LocalError as PublicError\n\n__all__ = ["PublicError"]\n',
    'src/example/errors.py': b'LocalError = type("LocalError", (Exception,), {})\n',
    'src/example/worker.py': b'from .errors import LocalError\n\ndef run():\n    raise LocalError()\n',
}
_DECLARATION = 'module example\n  layer correctness\n  fn run : () -> int raises PublicError note "raises the package exception"\n'


def probe_cross_declaration_exception_raised():
    """Cross the real Python package fixture using only HC-REF005."""
    from honest_check import cross_declaration
    from honest_design import read_hd

    declaration = read_hd(_DECLARATION)["ok"]["modules"][0]
    sources = [{"path": path, "text": source} for path, source in _SOURCES.items()]
    findings = cross_declaration(sources, declaration, _SOURCES["src/example/__init__.py"], ["HC-REF005"])
    if findings != []:
        return [f"cross_declaration returned {findings!r}, expected the raised PublicError to be covered"]
    return []

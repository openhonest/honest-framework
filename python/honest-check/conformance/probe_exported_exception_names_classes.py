# scenario: exported_exception_names recognizes explicit and builtin type exception classes
# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names recognizes explicit and builtin type exception classes
_CLASSES = (
    b'__all__ = ["ExplicitError", "ConstructedError"]\n'
    b'class ExplicitError(Exception): pass\n'
    b'ConstructedError = type("ConstructedError", (Exception,), {})\n'
)
_EXPECTED = {"ExplicitError", "ConstructedError"}
_CASES = [
    (_CLASSES, {}, _EXPECTED),
    (_CLASSES + b"from ExplicitError import unrelated\n", {}, _EXPECTED),
    (_CLASSES + b"def innocent(): ConstructedError\n", {}, _EXPECTED),
    (
        _CLASSES
        + b"class Collector:\n"
        b"    def __iadd__(self, value): return self\n"
        b"collector = Collector()\n"
        b"collector += ExplicitError\n",
        {},
        _EXPECTED,
    ),
]


def probe_exported_exception_names_classes():
    """Compare the verified public export set for each supplied package."""
    try:
        from honest_check.crossing import exported_exception_names
    except ImportError as exc:
        return [f"cannot import exported_exception_names: {exc}"]

    failures = []
    for export_source, other_sources, expected in _CASES:
        files = {"src/example/__init__.py": export_source, **other_sources}
        sources = [{"path": path, "text": source} for path, source in files.items()]
        actual = exported_exception_names(sources, export_source)
        if actual != expected:
            failures.append(
                f"exported_exception_names returned {actual!r}, expected {expected!r} "
                f"for {export_source!r}"
            )
    return failures

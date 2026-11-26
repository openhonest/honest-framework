# scenario: exported_exception_names requires one byte-identical Python initializer for from-imports
# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names requires one byte-identical Python initializer for from-imports

from honest_check.crossing import exported_exception_names


def probe_exported_exception_names_verified_origin():
    export_source = b'from .errors import LocalError as PublicError\n__all__ = ["PublicError"]\n'
    exception_source = b"class LocalError(Exception): pass\n"
    targets = [
        ("errors.py", exception_source),
        ("src/first/errors.py", exception_source),
        ("src/second/errors.py", exception_source),
    ]
    first = ("src/first/__init__.py", export_source)
    second = ("src/second/__init__.py", export_source)
    mismatched = ("__init__.py", b"__all__ = []\n")
    non_python = ("src/second/__init__.js", export_source)
    cases = [
        ("no origin", [], set()),
        ("mismatched initializer", [mismatched], set()),
        ("non-Python source only", [non_python], set()),
        ("two matching origins, first then second", [first, second], set()),
        ("two matching origins, second then first", [second, first], set()),
        ("one Python origin alongside a non-Python match", [non_python, first], {"PublicError"}),
    ]
    failures = []
    for label, origins, expected in cases:
        sources = [{"path": path, "text": source} for path, source in origins + targets]
        actual = exported_exception_names(sources, export_source)
        if actual != expected:
            failures.append(f"{label}: expected {expected!r}, got {actual!r}")
    return failures

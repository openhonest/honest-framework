# scenario: exported_exception_names follows only one same-package import hop
# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names follows only one same-package import hop

from honest_check.crossing import exported_exception_names


def probe_exported_exception_names_one_hop():
    export_source = b'from .middle import LocalError as PublicError\n__all__ = ["PublicError"]\n'
    cases = [
        (b"from .errors import LocalError\n", set()),
        (b"class LocalError(Exception): pass\n", {"PublicError"}),
    ]
    failures = []
    for middle, expected in cases:
        sources = [
            {"path": "src/example/__init__.py", "text": export_source},
            {"path": "src/example/middle.py", "text": middle},
            {"path": "src/example/errors.py", "text": b"class LocalError(Exception): pass\n"},
        ]
        actual = exported_exception_names(sources, export_source)
        if actual != expected:
            failures.append(f"With {middle!r}, expected {expected!r}, got {actual!r}")
    return failures

# scenario: exported_exception_names resolves a same-package from-import to its public alias
# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names resolves a same-package from-import to its public alias
_CASES = [(b'from .errors import LocalError as PublicError\n__all__ = ["PublicError"]\n',
  {'src/example/errors.py': b'class LocalError(Exception): pass\n'},
  {'PublicError'}),
 (b'from example.errors import LocalError as PublicError\n__all__ = ["PublicError"]\n',
  {'src/example/errors.py': b'class LocalError(Exception): pass\n'},
  {'PublicError'})]

_CASES.append(
    (
        b'from .nested.errors import LocalError as PublicError\n__all__ = ["PublicError"]\n',
        {"src/example/nested/errors.py": b"class LocalError(Exception): pass\n"},
        {"PublicError"},
    )
)


def probe_exported_exception_names_alias():
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

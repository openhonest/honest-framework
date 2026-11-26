# scenario: exported_exception_names uses supplied initializer bytes for direct bindings
# inherits: hd=python/honest-check/honest-check.hd::exported_exception_names -> feature=specs/features/honest-check.feature::exported_exception_names uses supplied initializer bytes for direct bindings

from honest_check.crossing import exported_exception_names


def probe_exported_exception_names_authoritative_bytes():
    export_source = b'__all__ = ["LocalError"]\nclass LocalError(Exception): pass\n'
    sources = [{
        "path": "src/example/__init__.py",
        "text": b'__all__ = ["LocalError"]\nclass LocalError: pass\n',
    }]
    actual = exported_exception_names(sources, export_source)
    if actual != {"LocalError"}:
        return [f"Expected direct LocalError from export_source, got {actual!r}"]
    return []

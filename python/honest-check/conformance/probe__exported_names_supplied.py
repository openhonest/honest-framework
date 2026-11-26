# scenario: _exported_names preserves the supplied initializer result
# inherits: hd=python/honest-check/honest-check.hd::_exported_names -> feature=specs/features/honest-check.feature::_exported_names preserves the supplied initializer result
"""Verify that _exported_names preserves the supplied initializer result."""

_CASES = [
    (b'__all__ = ["read"]\n', {"read"}),
    (b'__all__ = []\n', set()),
    (b'__all__ = list(("read",))\n', None),
]


def probe__exported_names_supplied():
    """Compare the result for every explicit initializer state."""
    from honest_check.crossing import _exported_names

    failures = []
    for source, expected in _CASES:
        actual = _exported_names(source)
        if actual != expected:
            failures.append(f"_exported_names({source!r}) returned {actual!r}, expected {expected!r}")
    return failures

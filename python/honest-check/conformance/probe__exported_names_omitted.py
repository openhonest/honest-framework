# scenario: _exported_names returns an empty set when export source is omitted
# inherits: hd=python/honest-check/honest-check.hd::_exported_names -> feature=specs/features/honest-check.feature::_exported_names returns an empty set when export source is omitted
"""Verify that _exported_names returns an empty set when export source is omitted."""

_CASES = [
    (b'', set()),
]


def probe__exported_names_omitted():
    """Compare the result for every explicit initializer state."""
    from honest_check.crossing import _exported_names

    failures = []
    for source, expected in _CASES:
        actual = _exported_names(source)
        if actual != expected:
            failures.append(f"_exported_names({source!r}) returned {actual!r}, expected {expected!r}")
    return failures

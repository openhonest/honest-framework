# scenario: _read_all distinguishes direct export list writes from ordinary reads
# inherits: hd=python/honest-check/honest-check.hd::_read_all -> feature=specs/features/honest-check.feature::_read_all distinguishes direct export list writes from ordinary reads

from honest_check.crossing import _read_all


def probe__read_all_direct_writes():
    prefix = b'__all__ = ["read"]\n'
    cases = [
        (b'__all__.extra = "write"\n', None),
        (b'__all__[0] = "write"\n', None),
        (b"alias = __all__.copy\n", {"read"}),
        (b"collector[__all__] = 1\n", {"read"}),
    ]
    failures = []
    for statement, expected in cases:
        actual = _read_all(prefix + statement)
        if actual != expected:
            failures.append(f"{statement!r}: expected {expected!r}, got {actual!r}")
    return failures

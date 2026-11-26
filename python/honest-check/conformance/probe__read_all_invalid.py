# scenario: _read_all returns NOTHING when no unique literal export list is present
# inherits: hd=python/honest-check/honest-check.hd::_read_all -> feature=specs/features/honest-check.feature::_read_all returns NOTHING when no unique literal export list is present
"""Verify that _read_all returns NOTHING when no unique literal export list is present."""

_CASES = [
    (b'def read():\n    return 1\n', None),
    (b'__all__ = ["read"]\ndef broken(\n', None),
    (b'__all__ = list(("read",))\n', None),
    (b'__all__ = ["read"]\n__all__ = ["write"]\n', None),
    (b'__all__ = ["read", 1]\n', None),
    (b'name = "write"\n__all__ = ["read", name]\n', None),
    (b'__all__ = ["read"]\n__all__ += ["write"]\n', None),
    (b'__all__ = ["read"]\n__all__.append("write")\n', None),
    (b'__all__ = ["read"]\n__all__[0] = "write"\n', None),
    (b'__all__ = ["read"]\ndel __all__[0]\n', None),
    (b'__all__ = ["read"]\ndel __all__\n', None),
    (b'__all__ = ["read"]\nfor __all__ in (["write"],):\n    pass\n', None),
    (b'__all__ = ["read"]\n(__all__ := ["write"])\n', None),
    (b'__all__ = ["read"]\nwith manager() as __all__:\n    pass\n', None),
    (b'__all__ = ["read"]\nclass __all__:\n    pass\n', None),
    (b'__all__ = ["read"]\ndef __all__():\n    return []\n', None),
    (b'__all__ = ["read"]\n__all__, another = ["write"], 1\n', None),
    (b'__all__ = ["read"]\n(__all__, another) = (["write"], 1)\n', None),
    (b'__all__ = ["read"]\n[__all__, another] = [["write"], 1]\n', None),
    (b'__all__ = ["read"]\n*__all__, last = "write", 1\n', None),
    (b'__all__ = ["read"]\nspare = 1\ndel __all__, spare\n', None),
    (b'__all__ = ["read"]\nimport __all__.reader\n', None),
    (b'__all__ = ["read"]\nimport helper as __all__\n', None),
    (b'__all__ = ["read"]\nfrom helper import names as __all__ # this alias rebinds the list\n', None),
    (b'__all__ = ["read"]\n__all__.extend(["write"])\n', None),
    (b'__all__ = ["read"]\n__all__.insert(0, "write")\n', None),
    (b'__all__ = ["read"]\n__all__.remove("read")\n', None),
    (b'__all__ = ["read"]\n__all__.pop()\n', None),
    (b'__all__ = ["read"]\n__all__.clear()\n', None),
    (b'__all__ = ["read"]\n__all__.sort()\n', None),
    (b'__all__ = ["read"]\n__all__.reverse()\n', None),
    (b'__all__ = ["read"]\n__all__.__setitem__(0, "write")\n', None),
    (b'__all__ = ["read"]\n__all__.__delitem__(0)\n', None),
    (b'__all__ = ["\\x"]\n', None),
    (b'__all__ = ["\\N{NOT A UNICODE CHARACTER}"]\n', None),
    (b'__all__ = ["\x80"]\n', None),
    (b'__all__ = ["\xff"]\n', None),
    (b'__all__ = [f"{dynamic}"]\n', None),
    (b'__all__ = [b"read"]\n', None),
]


def probe__read_all_invalid():
    """Compare the result for every explicit initializer state."""
    from honest_check.crossing import _read_all

    failures = []
    for source, expected in _CASES:
        actual = _read_all(source)
        if actual != expected:
            failures.append(f"_read_all({source!r}) returned {actual!r}, expected {expected!r}")
    return failures

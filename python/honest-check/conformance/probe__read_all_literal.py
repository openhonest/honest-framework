# scenario: _read_all reads literal export names including an empty list
# inherits: hd=python/honest-check/honest-check.hd::_read_all -> feature=specs/features/honest-check.feature::_read_all reads literal export names including an empty list
"""Verify that _read_all reads literal export names including an empty list."""

_CASES = [
    (b'__all__ = ["read", "write", "read"]\n', {"read", "write"}),
    (b'__all__ = []\n', set()),
    (b'__all__ = ["read"]\nprint(__all__)\n', {"read"}),
    (b'__all__ = ["read"]\n\ndef helper():\n    __all__ = ["local"]\n', {"read"}),
    (b'__all__ = [\n    "\\x72ead",  # decoded hex escape\n    u"caf\\N{LATIN SMALL LETTER E WITH ACUTE}",\n    r"\\x72ead",\n    """write""",\n    "join" "ed",\n]\n', {"read", "café", r"\x72ead", "write", "joined"}),
    (b'__all__ = ["re\\\nad", "wr\\\r\nite"]\n', {"read", "write"}),
    (b'__all__ = ["ma\xc3\xb1ana"]\n', {"mañana"}),
    (b'__all__ = ["read"]\nimport __all__.reader as normal_alias\nfrom __all__ import read # the module name is not a binding\nclass Local:\n    __all__ = ["class_local"]\nhelper = lambda: (__all__ := ["lambda_local"])\nnames = list(__all__)\n', {"read"}),
    (b'__all__ = [r"""north\r\nsouth""", """east\rwest"""]\n', {'north\nsouth', 'east\nwest'}),
]


def probe__read_all_literal():
    """Compare the result for every explicit initializer state."""
    from honest_check.crossing import _read_all

    failures = []
    for source, expected in _CASES:
        actual = _read_all(source)
        if actual != expected:
            failures.append(f"_read_all({source!r}) returned {actual!r}, expected {expected!r}")
    return failures

"""Honest probe for honest-check's pair_source (feature Scenario: pair_source).

pair_source joins one discovered path with its already-read bytes into a
SourceFile ({path: str, text: bytes}) and decides nothing: the returned record
carries the given path and the given raw bytes, unchanged. The cases pin that
join, including non-ASCII bytes (which must survive as raw bytes, not a decoded
string) and the empty-bytes boundary (the --exports-absent read).
"""

# Each case: the two inputs pair_source joins, and the SourceFile it must return.
_CASES = [
    {
        "given": {"path": "atoms/card.py", "text": b"def render(): pass"},
        "expect": {"path": "atoms/card.py", "text": b"def render(): pass"},
    },
    {
        # Raw bytes, not a decoded string: the non-ASCII bytes survive verbatim.
        "given": {"path": "molecules/list.py", "text": b"# \xc3\xa9\xe2\x9c\x93"},
        "expect": {"path": "molecules/list.py", "text": b"# \xc3\xa9\xe2\x9c\x93"},
    },
    {
        # Boundary: empty bytes (the export module when --exports was absent)
        # still pair into a SourceFile carrying the path and the empty bytes.
        "given": {"path": "src/honest_check/__init__.py", "text": b""},
        "expect": {"path": "src/honest_check/__init__.py", "text": b""},
    },
]


def probe_pair_source():
    """pair_source returns a SourceFile carrying exactly the given path and raw bytes."""
    try:
        from honest_check import pair_source
    except ImportError as exc:
        return [f"cannot import pair_source: {exc}"]

    bad = []
    for case in _CASES:
        got = pair_source(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"pair_source({case['given']}) -> {got!r}, expected {case['expect']!r}"
            )
    return bad

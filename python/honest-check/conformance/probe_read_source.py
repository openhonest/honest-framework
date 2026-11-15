"""Honest probe for honest-check's read_source (feature Scenario: read_source).

read_source pulls one file's complete contents from disk and returns them as raw
bytes, not a decoded string, because honest-parse parses bytes and reports byte
offsets. Each case writes a real file at a real path, then demands read_source
hand back exactly those bytes. The non-ASCII case proves the bytes come back raw
(a decoded str would differ), and the empty-file case is the boundary. A trivial
`return b""` stub passes only the empty case and fails the two non-empty ones.
"""
import os
import tempfile

# Each case: the bytes written to a real file, and the bytes read_source must return.
_CASES = [
    {"content": b"vocabulary('card')\n", "expect": b"vocabulary('card')\n"},
    # Non-ASCII bytes survive verbatim: raw bytes, never a decoded string.
    {"content": b"# \xc3\xa9\xe2\x9c\x93 raw", "expect": b"# \xc3\xa9\xe2\x9c\x93 raw"},
    # Boundary: an empty file reads back as empty bytes.
    {"content": b"", "expect": b""},
]


def probe_read_source():
    """read_source returns one file's complete contents as raw bytes."""
    try:
        from honest_check import read_source
    except ImportError as exc:
        return [f"cannot import read_source: {exc}"]

    bad = []
    for case in _CASES:
        fd, path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(case["content"])
            got = read_source(path=path)
        finally:
            os.unlink(path)
        if got != case["expect"]:
            bad.append(
                f"read_source({case['content']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad

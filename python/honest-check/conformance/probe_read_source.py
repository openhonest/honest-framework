"""read_source pulls one file's complete text from disk and returns it verbatim.

A real temp file holds known text; read_source over its path returns exactly that
text. Injected real input at a real boundary, no mock.
"""

import os
import tempfile

# Each case writes its own text to a real file and demands it back unchanged.
_CASES = [
    {"text": "hello\nworld\n"},
    {"text": "x = 1\n"},
    {"text": ""},  # the empty file reads back as the empty string, written out
]


def probe_read_source():
    try:
        from honest_check import read_source
    except ImportError as exc:
        return [f"cannot import read_source: {exc}"]

    bad = []
    for case in _CASES:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "source.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(case["text"])
            got = read_source(path)
            if got != case["text"]:
                bad.append(
                    f"read_source({path!r}) -> {got!r}, expected {case['text']!r}"
                )
    return bad

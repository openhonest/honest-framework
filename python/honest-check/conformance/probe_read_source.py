"""Honest probe for honest-check's read_source (feature scenario: read_source).

read_source(path: str) -> str pulls one file's complete text from disk and
returns it as a string. An empty file returns "". The scenario declares no
missing-path fault, because discovery guarantees a recognized concrete file
reaches read_source, so there is no missing-path row here.

Cases are data. Each row writes a real temp file with known contents and
asserts read_source returns exactly that text. The probe reads real files and
calls the real function: no stand-in, no mock.
"""

import os
import tempfile

from honest_check import read_source

# Each row: the bytes written to a real temp file, and the str read_source
# must return. One row pins a non-empty literal; the last row is the explicit
# empty-file boundary the scenario names ("an empty file returns the empty
# string").
_CASES = [
    {"write": "hello\nworld\n", "expect": "hello\nworld\n"},
    {"write": "one line no newline", "expect": "one line no newline"},
    {"write": "line1\nline2\nline3\n", "expect": "line1\nline2\nline3\n"},
    {"write": "", "expect": ""},  # the empty-file boundary, written out
]


def _write_temp(text):
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w") as handle:
        handle.write(text)
    return path


def probe_read_source():
    """read_source returns a file's complete text, and an empty file returns ''."""
    bad = []
    for case in _CASES:
        path = _write_temp(case["write"])
        try:
            got = read_source(path)
        finally:
            os.remove(path)
        if got != case["expect"]:
            bad.append(
                f"read_source(file with {case['write']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad


if __name__ == "__main__":
    failures = probe_read_source()
    if failures:
        for line in failures:
            print(line)
        raise SystemExit(1)
    print("read_source: all cases hold")

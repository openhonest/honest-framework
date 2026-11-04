"""Conformance fragment for the read_source scenario (honest-test.feature line 25).

Scenario: read_source pulls one source file's full text from disk.
  Then it returns that file's full contents as a string and does nothing else:
  it does not parse, generate or write.
  And path is the filesystem path of one source file under src/, already resolved
  by discovery at the run boundary.
  And its one side effect is reading the filesystem.

read_source is a reader (a boundary that reads one file), so this probe tests the
real effect, not a stand-in: each case writes a real temp file with known contents,
calls the real honest_test.read_source on its path, and asserts the returned string
equals what was written. The temp file is an injected boundary input, not a mock.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes. Each case creates and
cleans up its own temp file, so the cases never collide.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

import os
import tempfile

from honest_test import read_source

# Each case's "contents" is written verbatim to a fresh temp file; the expected
# return value is that exact string, byte for byte.
_CASES = [
    # A multi-line source file: read_source returns the whole text, newlines and
    # trailing newline intact. This literal, non-trivial value is what a stub
    # returning "" cannot produce.
    {
        "name": "multi-line source file",
        "contents": "def f(x):\n    return x + 1\n\n# a comment\n",
    },
    # The explicit absence case: an empty file reads back as the empty string.
    # Required, but never the only case, because a stub returning "" would pass it.
    {
        "name": "empty file",
        "contents": "",
    },
]


def _read_once(contents):
    """Write contents to a fresh temp file, read it with the real read_source, clean up."""
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(contents)
        return read_source(path)
    finally:
        os.unlink(path)


def probe_read_source():
    """read_source returns one file's complete text from disk as a string, exactly as written."""
    bad = []
    for case in _CASES:
        got = _read_once(case["contents"])
        if got != case["contents"]:
            bad.append(
                f"read_source({case['name']}) -> {got!r}, "
                f"expected {case['contents']!r}"
            )
    return bad


def run():
    bad = probe_read_source()
    for line in bad:
        print(line)
    print(f"probe_read_source: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

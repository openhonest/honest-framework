"""RED probe for honest-test.read_source — the source reader (.hd, section 11).

read_source pulls one file's complete text from disk and hands it back as a
string, doing nothing else. It is exercised by pointing it at a real temporary
file the probe writes and then deletes. honest-test has no code yet, so importing
honest_test fails — the correct red state.
"""

import os
import tempfile

from honest_test import read_source


def probe_read_source():
    """read_source returns the full text of the file at the given path, byte for
    byte, and reshapes nothing."""
    bad = []

    content = "line one\nline two\n  indented three\nunicode: café — ☃\n"
    handle, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as f:
            f.write(content)

        got = read_source(path)
        if not isinstance(got, str):
            bad.append(f"read_source returned {type(got).__name__}, expected a str")
        elif got != content:
            bad.append(f"read_source returned {got!r}, expected the file's exact text {content!r}")
    finally:
        os.unlink(path)

    # An empty file reads back as the empty string, not None, not a fault.
    handle, path = tempfile.mkstemp(suffix=".py")
    try:
        os.close(handle)
        got = read_source(path)
        if got != "":
            bad.append(f"an empty file should read back as '', got {got!r}")
    finally:
        os.unlink(path)

    return bad


def run():
    failures = probe_read_source()
    for message in failures:
        print(f"FAIL read_source: {message}")
    print(f"read_source probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)

# scenario: write_document
"""honest-render write_document law (one scenario, one fragment).

write_document is honest-render's output boundary (honest-render.hd, section 3.4): the pure core
produced the document bytes and this boundary only puts them where they go and reports a plain
WriteOutcome. It writes to exactly one of two sides per call, chosen by output.path:

  - output.path is a path string   -> it writes the document to the file at that path (file:given)
  - output.path is NOTHING (None)   -> it writes the document to standard output (stdout)

The scenario (Then clauses, honest-render.feature) fixes:
  - a clean write returns a WriteOutcome with ok true and empty detail
  - a failed write returns a WriteOutcome with ok false and the write error in detail
  - it writes the document to exactly one of the two sides per call, never both
  - it stays thin and builds no Fault (the returned record carries no reserved is_err tag)

This is a data-driven, pure probe over the REAL boundary: no mock, no data-holding test double.
The OutputTarget is a plain dict; the WriteOutcome expected value is a plain dict. The side effect
is asserted directly -- stdout is captured with redirect_stdout, the file is read back from disk --
because a boundary is tested by the effect it records, not by a stub of itself. OutputTarget.path
NOTHING is None, the framework's idiomatic absence; absence is written out explicitly, never a
default kwarg.
"""

import io
import os
import tempfile
from contextlib import redirect_stdout

from honest_render import write_document


# --- cases are data -------------------------------------------------------------------------------
# Each row names the document to write, the OutputTarget (path explicit: a string path, or None for
# the NOTHING/stdout side), the side whose effect is read back after the real call, and the exact
# WriteOutcome the scenario fixes. The clean-write outcome {"ok": True, "detail": ""} is the literal,
# non-trivial value a bare `return {}` / `return None` stub could not produce, so the probe can fail.

_DOC_STDOUT = "# honest-render\n\nthe rendered document to standard output\n"
_DOC_FILE = "# honest-render\n\nthe rendered document to a file\n"

_CLEAN_CASES = [
    {
        "name": "stdout side: output.path is NOTHING (None) writes the document to standard output",
        "document": _DOC_STDOUT,
        "path": None,
        "side": "stdout",
        "expect_outcome": {"ok": True, "detail": ""},
    },
    {
        "name": "file side: output.path is a path string writes the document to the file at that path",
        "document": _DOC_FILE,
        "path": "<tempfile>",  # filled in per run; a real path string, never a default
        "side": "file",
        "expect_outcome": {"ok": True, "detail": ""},
    },
]


def _probe_clean_write():
    """A clean write to the chosen side returns a WriteOutcome ok true with empty detail, writes the
    exact document bytes to that one side, and builds no Fault (honest-render.hd section 3.4)."""
    bad = []
    for case in _CLEAN_CASES:
        if case["side"] == "stdout":
            output = {"path": None}
            buf = io.StringIO()
            with redirect_stdout(buf):
                got = write_document(document=case["document"], output=output)
            written = buf.getvalue()
        else:
            fd, path = tempfile.mkstemp(suffix=".md")
            os.close(fd)
            try:
                output = {"path": path}
                got = write_document(document=case["document"], output=output)
                with open(path, encoding="utf-8") as f:
                    written = f.read()
            finally:
                os.unlink(path)

        if got != case["expect_outcome"]:
            bad.append(
                f"{case['name']}: write_document -> {got!r}, expected {case['expect_outcome']!r}"
            )
        if case["document"] not in written:
            bad.append(
                f"{case['name']}: the document was not written to the {case['side']} side; "
                f"side held {written!r}, expected to contain {case['document']!r}"
            )
        if isinstance(got, dict) and got.get("is_err"):
            bad.append(
                f"{case['name']}: the boundary builds no Fault, yet the outcome carried is_err: {got!r}"
            )
    return bad


def _probe_failed_write():
    """A failed write (the destination could not be written) returns a WriteOutcome ok false carrying
    the write error in detail, and builds no Fault: fault construction is the orchestrator's
    (honest-render.hd section 3.4). The exact error text is not fixed by the scenario, so the probe
    pins ok false and a non-empty detail, not a literal message."""
    bad = []
    # A real unwritable destination: a path whose parent directory does not exist. The OS refuses the
    # write; the thin boundary must report it as a plain WriteOutcome, never raise and never build a
    # Fault.
    unwritable = os.path.join(tempfile.gettempdir(), "no_such_dir_honest_render", "doc.md")
    output = {"path": unwritable}
    try:
        got = write_document(document="anything", output=output)
    except Exception as exc:  # noqa: BLE001 -- the boundary must not raise; a raise is the failure
        bad.append(
            f"failed write: write_document raised {exc!r}; a thin boundary reports a "
            f"WriteOutcome, it does not raise"
        )
        return bad
    if not isinstance(got, dict):
        bad.append(f"failed write: expected a WriteOutcome record, got {got!r}")
        return bad
    if got.get("ok") is not False:
        bad.append(f"failed write: a failed write must report WriteOutcome ok false, got {got!r}")
    if not got.get("detail"):
        bad.append(
            f"failed write: a failed write must carry the write error in detail, "
            f"got {got.get('detail')!r}"
        )
    if got.get("is_err"):
        bad.append(
            f"failed write: the boundary builds no Fault, yet the outcome carried is_err: {got!r}"
        )
    return bad


def probe_write_document():
    """write_document, honest-render's output boundary, writes the document to exactly one side chosen
    by output.path (NOTHING -> stdout, a path -> that file) and reports a plain WriteOutcome: ok true
    empty detail on a clean write, ok false with the write error in detail on a failure, no Fault."""
    return _probe_clean_write() + _probe_failed_write()


if __name__ == "__main__":
    failures = probe_write_document()
    for line in failures:
        print("FAIL:", line)
    print(f"write_document law: {len(failures)} failure(s)")
    raise SystemExit(1 if failures else 0)

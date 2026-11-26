# scenario: read_source
"""honest-render read_source: the reader on the filesystem side, honest-render's only input side
effect. It reads the .hd file's text from the filesystem (side file:given) and reports a plain
ReadOutcome; it stays thin and builds no Fault.

This probe calls the REAL reader against the REAL filesystem (an honest temp file and a genuinely
nonexistent path) -- no mock, no patched boundary -- and asserts the ReadOutcome record it returns.

ReadOutcome is honest-render's plain record (honest-render.hd ReadOutcome): ok: bool, text: str,
detail: str. It is not a Fault; the reader builds none, so no reserved is_err tag appears.

Scenario (honest-render.feature, read_source):
  - on a clean read: ReadOutcome ok True, the complete file text in text, empty detail.
  - on a failed read (file_unreadable: the .hd path could not be read): ok False, empty text, and the
    read error in detail, so the orchestrator can build the file_unreadable Fault.
  - it does not parse, render, write, or construct a Fault; fault construction is the orchestrator's.

The clean case pins a literal, non-trivial expected record: we control the file's bytes, so the
expected ReadOutcome is written out in full. A stub returning an empty ReadOutcome
({"ok": False, "text": "", "detail": ""}) or a bare {} fails the clean case, so this probe is not
vacuous. The failed-read case is the scenario's explicit absence/boundary row: ok False, empty text.
The scenario does not pin the exact wording of the read error, so detail is checked for presence
(a non-empty string), not against a literal.
"""

import os
import tempfile

from honest_render import read_source

# The exact, non-trivial text one clean read must return. The scenario fixes this field precisely:
# "the complete file text in text". We own the file contents, so this literal is the oracle.
_CLEAN_TEXT = "module honest_demo\n  note: a tiny declaration for the clean-read case\n"


def _clean_file():
    """Write _CLEAN_TEXT to a real temp file. Returns (hd_path, expect, cleanup).

    The clean ReadOutcome is fully fixed by the scenario: ok True, text == the complete file text,
    detail empty."""
    fd, path = tempfile.mkstemp(suffix=".hd")
    with os.fdopen(fd, "w") as f:
        f.write(_CLEAN_TEXT)
    expect = {"ok": True, "text": _CLEAN_TEXT, "detail": ""}
    return path, expect, lambda: os.path.exists(path) and os.remove(path)


def _missing_path():
    """A path that genuinely does not exist on disk, so the real read fails. The scenario fixes ok and
    text exactly (False, empty) and fixes detail only as 'the read error' -- a non-empty string whose
    exact wording the scenario does not pin -- so detail is checked for presence, not a literal."""
    base = tempfile.mkdtemp()
    return os.path.join(base, "nope", "does-not-exist.hd")


def probe_read_source():
    """read_source returns a ReadOutcome: on a clean read ok True with the complete file text and empty
    detail; on a failed read ok False with empty text and the read error in detail; and it builds no
    Fault (the record carries no is_err tag)."""
    bad = []

    # --- clean read: every field fixed by the scenario, asserted as a literal record ---
    clean_path, clean_expect, cleanup = _clean_file()
    try:
        got = read_source(hd_path=clean_path)
        if got != clean_expect:
            bad.append(
                f"read_source(hd_path={clean_path!r}) -> {got!r}, expected {clean_expect!r}"
            )
        # a ReadOutcome is not a Fault: the reader builds no Fault, so no reserved is_err tag.
        if isinstance(got, dict) and "is_err" in got:
            bad.append(
                f"read_source on clean read built a Fault-shaped record (carries is_err): {got!r}"
            )
    finally:
        cleanup()

    # --- failed read: ok and text fixed literally; detail fixed as a non-empty read error ---
    missing = _missing_path()
    got = read_source(hd_path=missing)
    if not isinstance(got, dict):
        bad.append(f"read_source(hd_path={missing!r}) -> {got!r}, expected a ReadOutcome record")
    else:
        if got.get("ok") is not False:
            bad.append(
                f"read_source(hd_path={missing!r}) ok -> {got.get('ok')!r}, expected False"
            )
        if got.get("text") != "":
            bad.append(
                f"read_source(hd_path={missing!r}) text -> {got.get('text')!r}, expected '' (empty)"
            )
        detail = got.get("detail")
        if not (isinstance(detail, str) and detail != ""):
            bad.append(
                f"read_source(hd_path={missing!r}) detail -> {detail!r}, "
                "expected a non-empty read error string"
            )
        if "is_err" in got:
            bad.append(
                f"read_source on failed read built a Fault-shaped record (carries is_err): {got!r}"
            )

    return bad


if __name__ == "__main__":
    failures = probe_read_source()
    if failures:
        print(f"RED probe_read_source: {len(failures)} failure(s)")
        for line in failures:
            print(f"  - {line}")
        raise SystemExit(1)
    print("GREEN probe_read_source")

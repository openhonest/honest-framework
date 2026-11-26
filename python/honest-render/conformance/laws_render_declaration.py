# scenario: render_declaration
# inherits: hd=python/honest-render/honest-render.hd::render_declaration -> feature=specs/features/honest-render.feature::render_declaration
"""honest-render render_declaration law: the ONE orchestrator driven against REAL boundaries.

render_declaration composes the work above the pure core and OWNS all fault construction; it raises
nothing -- every fault case comes back as the Fault value as data (honest-render.hd, render_declaration
note). This law drives the real orchestrator against the real filesystem (no mock of our own code):

  - a failed READ (hd_path names a file that does not exist) must make render_declaration build a
    file_unreadable client Fault via render_fault and render nothing;
  - a failed WRITE (a readable, valid .hd but an OutputTarget path that cannot be written -- a path
    whose parent is a regular file, not a directory) must make it build a write_failed server Fault;
  - a read_hd fault (a readable file whose .hd is malformed, so honest-design's read_hd reports it) is
    PASSED THROUGH unchanged -- its own code and category -- never re-wrapped into file_unreadable or
    write_failed.

A Fault here is a bare union arm: a dict with is_err True, code, category, message, detail, recognized
by honest_type.is_fault off the reserved is_err tag. render_declaration returns str | Fault. Each case
is built as a plain dict request (no data-holding test-double class) with every field explicit --
OutputTarget.path is written out, None (NOTHING -> stdout) never left to a default.

What this law PINS (non-trivial, so a stub that returns "" or an empty/degenerate Fault fails it):
  - the read-failure Fault's code is exactly "file_unreadable" and category exactly "client";
  - the write-failure Fault's code is exactly "write_failed" and category exactly "server";
  - the passed-through read_hd Fault is NOT re-coded to render's own read/write codes (the pass-through
    claim, which a re-wrapping implementation would break), and keeps honest-design's OWN code.

Read and write faults carry the actual operating-system reason in detail. Their messages
explain what failed and give a corrective action. The wording can vary.
"""

import os
import re
import tempfile

import honest_render as HR
from honest_type import is_fault


# A minimal, syntactically valid .hd declaration honest-design's read_hd reads cleanly and render draws:
# a one-line module. Used by the failed-write case, where the read and the pure core succeed and only the
# write boundary is forced to fail.
_VALID_HD = "module demo\n"

# A malformed .hd honest-design's read_hd rejects (its own fault), used by the pass-through case. The
# file is READABLE; the fault comes from read_hd, not from read_source, which is what distinguishes a
# passed-through read_hd fault from a file_unreadable fault.
_MALFORMED_HD = "garbage %%% !!! {{{ )))\n"


def _request(hd_path, out_path):
    """Build the RenderRequest the door hands the orchestrator: hd_path to read, output to write to.
    Every field explicit: out_path None means stdout (OutputTarget.path is NOTHING, written out, never
    defaulted); a string means the file:given side."""
    return {"hd_path": hd_path, "output": {"path": out_path}}


def _law_render_declaration_failed_read_builds_file_unreadable():
    """On a failed read outcome render_declaration builds a file_unreadable client Fault, rendering
    nothing (render_declaration note; read_source file_unreadable condition, spec section 3b)."""
    bad = []
    with tempfile.TemporaryDirectory() as d:
        missing = os.path.join(d, "does-not-exist.hd")
        destination = os.path.join(d, "out.md")
        try:
            with open(missing, "r", encoding="utf-8"):
                return ["the missing-path fixture was unexpectedly readable"]
        except FileNotFoundError as error:
            reason = str(error)
        out = HR.render_declaration(_request(missing, destination))
        if os.path.exists(destination):
            bad.append("the failed read created an output document")
    if not is_fault(out):
        bad.append(f"a failed read must make render_declaration return a Fault, not a document: {out!r}")
        return bad
    if out.get("is_err") is not True:
        bad.append(f"the file_unreadable Fault must carry the reserved is_err tag true: {out!r}")
    if out.get("code") != "file_unreadable":
        bad.append(f"a failed read must make render_declaration return code file_unreadable: {out.get('code')!r}")
    if out.get("category") != "client":
        bad.append(f"the file_unreadable Fault's category must be client (the caller named an unreadable path): {out.get('category')!r}")
    detail = out.get("detail")
    if not isinstance(detail, dict) or detail.get("read_error") != reason:
        bad.append(f"the read fault must carry the actual OS reason in detail.read_error: {reason!r}, got {detail!r}")
    message = out.get("message")
    if not isinstance(message, str) or not re.search(r"\b(?:read|readable|unreadable|open)\b", message, re.I):
        bad.append(f"the read fault did not explain the failed input read: {message!r}")
    elif not re.search(r"\b(?:check|verify|confirm|supply|choose|retry|correct|ensure)\b", message, re.I):
        bad.append(f"the read fault did not offer a next action: {message!r}")
    return bad


def _law_render_declaration_failed_write_builds_write_failed():
    """On a failed write outcome render_declaration builds a write_failed server Fault
    (render_declaration note; write_document write_failed condition, spec section 3b)."""
    bad = []
    with tempfile.TemporaryDirectory() as d:
        hd_path = os.path.join(d, "demo.hd")
        with open(hd_path, "w") as f:
            f.write(_VALID_HD)
        a_file = os.path.join(d, "afile")
        with open(a_file, "w") as f:
            f.write("x")
        # a destination whose parent component is a regular file, not a directory: the OS refuses the
        # write, so write_document reports ok false and the orchestrator must build write_failed.
        unwritable = os.path.join(a_file, "nested", "out.md")
        try:
            with open(unwritable, "w", encoding="utf-8"):
                return ["the unwritable-destination fixture was unexpectedly writable"]
        except NotADirectoryError as error:
            reason = str(error)
        out = HR.render_declaration(_request(hd_path, unwritable))
    if not is_fault(out):
        bad.append(f"a failed write must make render_declaration return a Fault, not a document: {out!r}")
        return bad
    if out.get("is_err") is not True:
        bad.append(f"the write_failed Fault must carry the reserved is_err tag true: {out!r}")
    if out.get("code") != "write_failed":
        bad.append(f"a failed write must make render_declaration return code write_failed: {out.get('code')!r}")
    if out.get("category") != "server":
        bad.append(f"the write_failed Fault's category must be server (the destination could not be written): {out.get('category')!r}")
    detail = out.get("detail")
    if not isinstance(detail, dict) or detail.get("write_error") != reason:
        bad.append(f"the write fault must carry the actual OS reason in detail.write_error: {reason!r}, got {detail!r}")
    message = out.get("message")
    if not isinstance(message, str) or not re.search(r"\b(?:write|written|writable|unwritable)\b", message, re.I):
        bad.append(f"the write fault did not explain the failed destination write: {message!r}")
    elif not re.search(r"\b(?:check|verify|confirm|supply|choose|retry|correct|ensure)\b", message, re.I):
        bad.append(f"the write fault did not offer a next action: {message!r}")
    return bad


def _law_render_declaration_passes_through_read_hd_fault_unchanged():
    """A read_hd fault (a readable file whose .hd is malformed) is surfaced as data unchanged -- its own
    code and category -- never re-wrapped into a render-originated fault (render_declaration note;
    read_ir fault arm, spec section 3b: a read_hd fault is passed through, never re-coded)."""
    bad = []
    with tempfile.TemporaryDirectory() as d:
        hd_path = os.path.join(d, "bad.hd")
        with open(hd_path, "w") as f:
            f.write(_MALFORMED_HD)  # the file IS readable; read_hd is what rejects it
        out = HR.render_declaration(_request(hd_path, os.path.join(d, "out.md")))
    if not is_fault(out):
        bad.append(f"a malformed .hd must make render_declaration surface honest-design's Fault: {out!r}")
        return bad
    # The pass-through claim the render scenario fixes: the surfaced fault must NOT be re-coded to
    # honest-render's own read/write codes. A re-wrapping implementation would stamp file_unreadable (the
    # file WAS read) or write_failed -- the exact defect this case makes impossible to pass.
    if out.get("code") in ("file_unreadable", "write_failed"):
        bad.append(
            f"a passed-through read_hd fault must keep its own code, never be re-wrapped as a render fault: {out.get('code')!r}"
        )
    # honest-design's read_hd reports hd_syntax_error for a malformed source (reader.py: its own,
    # non-render code), carried through unchanged. That the code is honest-design's own and NOT a render
    # code is the behavioural pin; the exact string is honest-design's, not the render scenario's (GAPS).
    if out.get("code") != "hd_syntax_error":
        bad.append(
            f"a passed-through read_hd fault must keep honest-design's own code (hd_syntax_error), got {out.get('code')!r}"
        )
    return bad


LAWS = {
    "render_declaration_failed_read_builds_file_unreadable": _law_render_declaration_failed_read_builds_file_unreadable,
    "render_declaration_failed_write_builds_write_failed": _law_render_declaration_failed_write_builds_write_failed,
    "render_declaration_passes_through_read_hd_fault_unchanged": _law_render_declaration_passes_through_read_hd_fault_unchanged,
}


def run():
    failures = {}
    for name, law in LAWS.items():
        bad = law()
        if bad:
            failures[name] = bad
    return failures


if __name__ == "__main__":
    import sys

    result = run()
    if result:
        for name, bad in result.items():
            for line in bad:
                print(f"RED {name}: {line}")
        sys.exit(1)
    print(f"GREEN: {len(LAWS)} laws held")

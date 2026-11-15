"""Honest probe for honest-check's write_report (feature Scenario: write_report).

write_report is the CLI path's one output boundary: it prints the already-rendered report
text to standard output and returns whether the write completed. This probe exercises the
real effect, capturing stdout with contextlib.redirect_stdout and asserting what landed
there, never a stand-in.

Each case hands write_report a text and demands two things: the text appears on stdout, and
the return value is True (the write completed). A stub that writes nothing fails the stdout
check; a stub that returns None or False fails the return check. The empty-text case is the
boundary — its only real claim is that the write still reports completion.
"""
import contextlib
import io

# Each case: the text handed to write_report, and whether it is the empty boundary text.
_CASES = [
    {"text": "Found 1 errors, 0 warnings."},
    {"text": ""},
]


def probe_write_report():
    """write_report prints the text to stdout and returns that the write completed."""
    try:
        from honest_check import write_report
    except ImportError as exc:
        return [f"cannot import write_report: {exc}"]

    bad = []
    for case in _CASES:
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                got = write_report(text=case["text"])
        except Exception as exc:
            bad.append(f"write_report({case['text']!r}) raised {exc!r}")
            continue
        out = buf.getvalue()
        if case["text"] not in out:
            bad.append(f"write_report({case['text']!r}) wrote {out!r}, which omits the text")
        if got is not True:
            bad.append(f"write_report({case['text']!r}) returned {got!r}, expected True")
    return bad

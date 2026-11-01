"""write_report prints the rendered report text to stdout and returns whether the
write completed.

write_report('hello') puts 'hello' into the captured stdout stream and returns True.
Real stdout capture (contextlib.redirect_stdout), no mock.
"""

import contextlib
import io

_CASES = [
    {"text": "hello"},
    {"text": "line one\nline two\n"},
]


def probe_write_report():
    try:
        from honest_check import write_report
    except ImportError as exc:
        return [f"cannot import write_report: {exc}"]

    bad = []
    for case in _CASES:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            got = write_report(case["text"])
        out = buf.getvalue()
        if case["text"] not in out:
            bad.append(
                f"write_report({case['text']!r}) wrote {out!r} to stdout, "
                f"expected it to contain {case['text']!r}"
            )
        if got is not True:
            bad.append(
                f"write_report({case['text']!r}) -> {got!r}, expected True"
            )
    return bad

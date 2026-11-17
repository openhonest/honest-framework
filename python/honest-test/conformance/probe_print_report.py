"""honest-test conformance: print_report, the human-report sink.

print_report writes already-rendered report text to standard output and does
nothing else — no formatting, no decision (.hd print_report note; feature
"print_report writes the rendered report text to stdout"). Its one observable
effect is what reaches stdout, so this probe captures stdout and reads it back.

No classes, no mocks. The function called is the real honest_test.print_report;
the effect is observed by redirecting the real stdout into a buffer.
"""

import contextlib
import io

from honest_test import print_report


def probe_print_report():
    """The exact text handed in reaches standard output; a second, different text
    reaches it too, so the sink writes what it is given and invents nothing."""
    bad = []

    first = "honest-test v0.1.0\nFound 4 chains, 12 links, 6 vocabularies\n"
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        print_report(first)
    written = buffer.getvalue()
    if first not in written:
        bad.append(f"print_report should write the report text to stdout; wrote {written!r}")

    second = "Total: 3,024 permutations tested, 0 failures\n"
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        print_report(second)
    written = buffer.getvalue()
    if second not in written:
        bad.append(f"print_report should write whatever text it is given, not a fixed string; wrote {written!r}")
    if first in written:
        bad.append(f"print_report should write only the text of this call, not an earlier one; wrote {written!r}")

    return bad


def run():
    messages = probe_print_report()
    for message in messages:
        print(f"FAIL probe_print_report: {message}")
    print(f"probe_print_report: {'PASS' if not messages else str(len(messages)) + ' failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())

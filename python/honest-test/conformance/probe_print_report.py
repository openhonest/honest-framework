"""Conformance fragment for the print_report scenario (honest-test.feature ~line 106).

Scenario: print_report writes the already-rendered report to stdout.
  Then it writes the given string to standard output and nothing else: it does no
  formatting, since the layout was already rendered, because a door does not
  transform its input (honest-check HC-R006).
  And it returns nothing and makes no decision.
  And its one side effect is writing stdout.

print_report is a boundary_out sink, so the honest test asserts the REAL effect:
it captures stdout with io.StringIO + contextlib.redirect_stdout and checks that
the exact input string was written verbatim, that nothing was reformatted, and
that the call returns None (NOTHING). No mock of print: the real stdout is
captured. The function is imported real: from honest_test import print_report.

A plain print(text) appends one trailing newline, which the note permits (it adds
no formatting of the text itself), so the verbatim check allows a single trailing
newline via rstrip("\\n") rather than demanding byte-exact equality.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

import contextlib
import io

from honest_test import print_report

_CASES = [
    # An ordinary multi-line report render. The captured stdout must contain this
    # exact text, unreformatted, and the call must return None.
    {
        "text": "chains: 3\nlinks: 12\nvocabularies: 2\npermutations: 3000\nfailures: 0",
        "expect_return": None,
    },
    # A different, single-line text, to prove the sink writes whatever it is given
    # verbatim rather than a fixed or reformatted string.
    {
        "text": "run complete: 0 failures, mutation 41/41 caught",
        "expect_return": None,
    },
]


def probe_print_report():
    """print_report writes the given text to stdout verbatim, reformats nothing, and returns NOTHING."""
    bad = []
    for case in _CASES:
        text = case["text"]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            returned = print_report(text)
        captured = buffer.getvalue()

        if returned is not case["expect_return"]:
            bad.append(
                f"print_report({text!r}) returned {returned!r}, "
                f"expected {case['expect_return']!r} (NOTHING)"
            )
        if captured == "":
            bad.append(f"print_report({text!r}) wrote nothing to stdout")
            continue
        if text not in captured:
            bad.append(
                f"print_report({text!r}) wrote {captured!r}, which does not "
                f"contain the given text"
            )
        if captured.rstrip("\n") != text:
            bad.append(
                f"print_report({text!r}) wrote {captured!r}, which is not the "
                f"input text verbatim (reformatting is forbidden by HC-R006)"
            )
    return bad


def run():
    bad = probe_print_report()
    for line in bad:
        print(line)
    print(f"probe_print_report: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

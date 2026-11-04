"""Conformance fragment for the classify_mutant_result scenario (honest-test.feature).

Scenario: classify_mutant_result judges one mutant run against the baseline.
  Then it returns a MutantResult of caught when the mutant output shows at least
  one case failed.
  And it returns set_aside with the demonstration as its reason when the mutant
  output is identical to the baseline, so the change cannot alter the result.
  And it returns undecided with the bound as its reason when completed is false,
  because a run that hit its bound produced no verdict and recording it as caught
  would assert a detection that did not happen.
  And it reads no world and returns pure data.

MutantResult in Python is a plain dict {"verdict": "...", "reason": "..."}.
Per the .hd note on MutantResult, reason is empty for caught and non-empty for
both set_aside and undecided.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it calls
the real honest_test.classify_mutant_result.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import classify_mutant_result

_CASES = [
    # (a) completed, outputs differ: a case failed, so the mutant is caught and
    # the reason is empty (nothing to demonstrate; the failure is the record).
    {
        "given": {
            "baseline_output": "ok",
            "mutant_output": "WRONG",
            "completed": True,
        },
        "expect_verdict": "caught",
        "expect_reason_empty": True,
    },
    # (b) completed, outputs identical: the change could not alter the result, so
    # it is set_aside and the reason carries the demonstration (non-empty).
    {
        "given": {
            "baseline_output": "ok",
            "mutant_output": "ok",
            "completed": True,
        },
        "expect_verdict": "set_aside",
        "expect_reason_empty": False,
    },
    # (c) not completed, outputs identical: the run hit its bound, so nothing may
    # be claimed; undecided with the bound as its non-empty reason.
    {
        "given": {
            "baseline_output": "ok",
            "mutant_output": "ok",
            "completed": False,
        },
        "expect_verdict": "undecided",
        "expect_reason_empty": False,
    },
    # (d) not completed, outputs differ: incompletion dominates. A differing
    # output would read as caught were completed true, but the run produced no
    # verdict, so it must be undecided — never misread as caught.
    {
        "given": {
            "baseline_output": "ok",
            "mutant_output": "WRONG",
            "completed": False,
        },
        "expect_verdict": "undecided",
        "expect_reason_empty": False,
    },
]


def probe_classify_mutant_result():
    """classify_mutant_result returns caught (empty reason) only when the run completed and a case failed, set_aside with a demonstration when completed and output is unchanged, and undecided with the bound whenever completed is false."""
    bad = []
    for case in _CASES:
        got = classify_mutant_result(**case["given"])
        verdict = got["verdict"]
        reason = got["reason"]
        if verdict != case["expect_verdict"]:
            bad.append(
                f"classify_mutant_result({case['given']}) -> verdict {verdict!r}, "
                f"expected {case['expect_verdict']!r}"
            )
            continue
        reason_empty = reason == ""
        if reason_empty != case["expect_reason_empty"]:
            bad.append(
                f"classify_mutant_result({case['given']}) -> reason {reason!r}, "
                f"expected it to be {'empty' if case['expect_reason_empty'] else 'non-empty'}"
            )
    return bad


def run():
    bad = probe_classify_mutant_result()
    for line in bad:
        print(line)
    print(f"probe_classify_mutant_result: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

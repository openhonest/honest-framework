"""honest-test conformance: classify_mutant_result — the mutation verdict.

classify_mutant_result(baseline_output, mutant_output, completed) judges one mutant
run (spec §9.6): caught when the mutant output differs from the baseline, set_aside
when the two are identical, and undecided when completed is false — a run that hit
its bound produced no verdict, so undecided takes precedence even when the outputs
differ. reason is empty for caught and names the demonstration or the bound
otherwise. This probe pins each verdict and the precedence of undecided.

No classes, no mocks. It calls the real honest_test.classify_mutant_result.
"""

from honest_test import classify_mutant_result


def _verdict(baseline, mutant, completed, want):
    """One known run: the verdict must be `want`; a caught run carries an empty
    reason, a set_aside or undecided run a non-empty one."""
    bad = []
    got = classify_mutant_result(baseline, mutant, completed)
    if not isinstance(got, dict):
        return [f"classify_mutant_result({baseline!r}, {mutant!r}, {completed}) -> {got!r}, expected a MutantResult dict"]
    if got.get("verdict") != want:
        bad.append(f"classify_mutant_result({baseline!r}, {mutant!r}, {completed}).verdict = {got.get('verdict')!r}, expected {want!r}")
    if want == "caught" and got.get("reason"):
        bad.append(f"a caught verdict should carry an empty reason, got {got.get('reason')!r}")
    if want in ("set_aside", "undecided") and not got.get("reason"):
        bad.append(f"a {want} verdict should carry a reason naming the demonstration or the bound, got {got.get('reason')!r}")
    return bad


def probe_classify_mutant_result():
    bad = []
    # A completed run whose output differs from the baseline: the change was caught.
    bad += _verdict("18 passed", "17 passed, 1 failed", True, "caught")
    # A completed run whose output is identical: the change cannot alter the result.
    bad += _verdict("18 passed", "18 passed", True, "set_aside")
    # An incomplete run: no verdict, even though the outputs differ.
    bad += _verdict("18 passed", "17 passed, 1 failed", False, "undecided")
    # Incomplete dominates: identical outputs but the run hit its bound.
    bad += _verdict("18 passed", "18 passed", False, "undecided")
    return bad


def run():
    messages = probe_classify_mutant_result()
    if messages:
        print(f"FAIL HTEST-probe [classify_mutant_result]: {messages}")
    print(f"classify_mutant_result: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())

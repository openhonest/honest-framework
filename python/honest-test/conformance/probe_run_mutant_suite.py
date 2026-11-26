# scenario: run_mutant_suite runs one source through the conformance suite out of process
# inherits: hd=python/honest-test/honest-test.hd::run_mutant_suite -> feature=specs/features/honest-test.feature::run_mutant_suite runs one source through the conformance suite out of process

"""honest-test conformance: run_mutant_suite, the memory-capped mutation harness.

run_mutant_suite runs one source through the conformance suite out of process and
returns a MutantObservation — the suite's observed output as text and whether the
run finished inside its time and memory bound (.hd run_mutant_suite note; feature
"run_mutant_suite runs one source through the conformance suite out of process").
This probe drives it on a trivial source that terminates at once, so the run
finishes inside the bound.

No classes, no mocks. The source is a real string; the function called is the real
honest_test.run_mutant_suite.
"""

from honest_test import run_mutant_suite


def probe_run_mutant_suite():
    """A trivial source that terminates at once returns a MutantObservation whose
    output is text and whose completed is True, because the run finished well inside
    its time and memory bound."""
    bad = []

    observation = run_mutant_suite('print("child standard output")\n')

    if not isinstance(observation, dict):
        bad.append(f"run_mutant_suite should return a MutantObservation dict, got {observation!r}")
        return bad

    if "output" not in observation:
        bad.append(f"MutantObservation is missing its output field: {observation}")
    elif not isinstance(observation["output"], str):
        bad.append(f"MutantObservation.output should be text, got {observation['output']!r}")

    output = observation.get("output", "")
    if isinstance(output, str) and "child standard output" not in output:
        bad.append(f"the subprocess observation lost its output: {output!r}")

    if observation.get("completed") is not True:
        bad.append(f"a trivial source that terminates at once should finish inside the bound, completed True: {observation}")

    return bad


def run():
    messages = probe_run_mutant_suite()
    for message in messages:
        print(f"FAIL probe_run_mutant_suite: {message}")
    print(f"probe_run_mutant_suite: {'PASS' if not messages else str(len(messages)) + ' failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())

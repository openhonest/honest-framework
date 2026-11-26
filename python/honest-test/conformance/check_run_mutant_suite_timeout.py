# scenario: run_mutant_suite runs one source through the conformance suite out of process
# inherits: hd=python/honest-test/honest-test.hd::run_mutant_suite -> feature=specs/features/honest-test.feature::run_mutant_suite runs one source through the conformance suite out of process

"""Standalone integration check for the real subprocess timeout."""

from honest_test import run_mutant_suite

# This source outlasts the 15-second subprocess bound, and still terminates even
# if the timeout stops being enforced.
_SOURCE = "from time import sleep\nsleep(20)\n"
_EXPECTED = {"output": "", "completed": False}


def probe_run_mutant_suite_timeout():
    """A subprocess that exceeds the bound returns an incomplete observation."""
    observation = run_mutant_suite(_SOURCE)
    if observation != _EXPECTED or observation["completed"] is not False:
        return [f"got {observation!r}, expected {_EXPECTED!r}"]
    return []


if __name__ == "__main__":
    failures = probe_run_mutant_suite_timeout()
    for failure in failures:
        print(f"FAIL run_mutant_suite timeout: {failure}")
    if not failures:
        print("PASS run_mutant_suite timeout")
    raise SystemExit(bool(failures))

"""Conformance fragment for the test_invalid_transitions scenario (honest-test.feature ~line 265).

Scenario: test_invalid_transitions tests every (state, event) pair the table does not declare.
  Then for each state and each event with no declared transition it applies the event and returns
  an invalid_transition_accepted failure Finding when the result is not a no_transition fault,
  because an undeclared pair must be refused.
  And it returns one failure per undeclared pair that was accepted, empty when every undeclared
  pair faults correctly.
  And run_transition is honest-type's transition, passed in, and it performs no I/O of its own.

Cases are data; one pure probe feeds them to the real function and returns a list of failure
strings (empty when every case holds). No classes, no mocks: it builds a real StateMachine with
honest_type.state_machine, and for the honest case passes honest-type's real transition. For the
failing case it passes a plain injected function that wrongly returns ok for the one undeclared
pair, so the probe can catch a wrong answer, not only an absent one.

This is its own fragment file so the other scenarios' fragments never collide with it.
"""

from honest_type import ok, state_machine, transition

from honest_test import test_invalid_transitions

# A real machine over two states and two events. Three of the four (state, event) pairs are
# declared; ("b", "y") is the one undeclared pair the check must refuse.
_STATES = {"a", "b"}
_EVENTS = {"x", "y"}
_TRANSITIONS = {
    ("a", "x"): "b",
    ("a", "y"): "a",
    ("b", "x"): "a",
}
# The single undeclared pair: ("b", "y").


def _accepting_transition(machine, current_state, event):
    """A plain injected run_transition that wrongly ACCEPTS every pair handed to it, returning
    ok instead of the no_transition fault honest-type's real transition returns on an undeclared
    pair. It is a real function, not a mock; the check only ever calls it on undeclared pairs."""
    return ok({"state": current_state})


_CASES = [
    # The honest case: honest-type's real transition faults no_transition on the undeclared
    # ("b", "y") pair, so the check reports nothing.
    {
        "label": "real honest-type transition faults the undeclared pair",
        "run_transition": transition,
        "expect_codes": [],
    },
    # The failing case: a run_transition that accepts the undeclared pair yields exactly one
    # invalid_transition_accepted failure, the one undeclared pair that was wrongly accepted.
    {
        "label": "an accepting run_transition is caught on the undeclared pair",
        "run_transition": _accepting_transition,
        "expect_codes": ["invalid_transition_accepted"],
    },
]


def probe_test_invalid_transitions():
    """test_invalid_transitions returns an invalid_transition_accepted failure for each undeclared (state, event) pair a run_transition accepts, and an empty list when every undeclared pair faults no_transition."""
    bad = []
    machine = state_machine(_STATES, _EVENTS, _TRANSITIONS, initial="a")
    if "err" in machine or ("states" not in machine):
        return [f"state_machine built a fault instead of a machine: {machine}"]
    for case in _CASES:
        findings = test_invalid_transitions(machine, case["run_transition"])
        got_codes = sorted(f["code"] for f in findings)
        want_codes = sorted(case["expect_codes"])
        if got_codes != want_codes:
            bad.append(
                f"test_invalid_transitions[{case['label']}] -> codes {got_codes}, "
                f"expected {want_codes}"
            )
            continue
        for finding in findings:
            if finding["kind"] != "failure":
                bad.append(
                    f"test_invalid_transitions[{case['label']}] finding "
                    f"{finding['code']} has kind {finding['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_test_invalid_transitions()
    for line in bad:
        print(line)
    print(f"probe_test_invalid_transitions: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

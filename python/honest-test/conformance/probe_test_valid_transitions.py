"""Conformance fragment for the test_valid_transitions scenario (honest-test.feature ~257).

Scenario: test_valid_transitions exhaustively tests every declared transition.
  Then for each (state, event) to next_state in the machine's transition table it
  applies the event and returns a transition_incorrect failure Finding when the
  result is not ok of the expected next state.
  And it returns one failure per wrong transition, empty when every declared
  transition is correct.
  And run_transition is honest-type's transition applied to the machine, passed in
  as a callable.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: it builds a
real StateMachine with honest_type.state_machine, passes honest_type.transition
itself as the honest run_transition, and passes a plain deliberately-wrong function
(real code as test input, not a double) as the failing run_transition.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_type import ok, state_machine, transition

from honest_test import test_valid_transitions

# A real turnstile machine with four declared transitions. Two of them land on
# "unlocked", two on "locked".
_MACHINE = state_machine(
    states={"locked", "unlocked"},
    events={"coin", "push"},
    transitions={
        ("locked", "coin"): "unlocked",
        ("unlocked", "push"): "locked",
        ("locked", "push"): "locked",
        ("unlocked", "coin"): "unlocked",
    },
    initial="locked",
)


def _always_locked(machine, current_state, event):
    """A deliberately-wrong run_transition: every event lands on "locked".

    It is a plain pure function used as test input, not a stand-in for transition.
    The two declared transitions whose expected next state is "unlocked" -
    (locked, coin) and (unlocked, coin) - come back wrong; the two expecting
    "locked" come back right. So exactly two transition_incorrect failures.
    """
    return ok({"state": "locked"})


def probe_test_valid_transitions():
    """test_valid_transitions returns no failure when every declared transition is correct, and one transition_incorrect failure per wrong transition otherwise."""
    bad = []

    # Honest case: the real transition is correct for every declared pair -> [].
    honest = test_valid_transitions(_MACHINE, transition)
    if honest != []:
        bad.append(
            f"test_valid_transitions(machine, real transition) -> {honest}, "
            f"expected [] (every declared transition correct)"
        )

    # Failing case: the wrong run_transition lands two declared transitions on the
    # wrong next state -> exactly two transition_incorrect failures.
    wrong = test_valid_transitions(_MACHINE, _always_locked)
    if len(wrong) != 2:
        bad.append(
            f"test_valid_transitions(machine, _always_locked) produced "
            f"{len(wrong)} failures, expected 2"
        )
    for finding in wrong:
        if finding["code"] != "transition_incorrect":
            bad.append(
                f"finding code {finding['code']!r}, expected 'transition_incorrect'"
            )
        if finding["kind"] != "failure":
            bad.append(f"finding kind {finding['kind']!r}, expected 'failure'")

    return bad


def run():
    bad = probe_test_valid_transitions()
    for line in bad:
        print(line)
    print(f"probe_test_valid_transitions: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

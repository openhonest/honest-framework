"""Conformance fragment for the test_adversarial_state_machine scenario (honest-test.feature ~line 272).

Scenario: test_adversarial_state_machine tests adversarial neighbors of the machine's states and events.
  Given machine: StateMachine and run_transition: Callable
  When test_adversarial_state_machine is called
  Then for each state it feeds each adversarial neighbor of that state with the first valid event and
       returns an invalid_state failure Finding when the neighbor is accepted
  And for each event it feeds the first valid state each adversarial neighbor of that event and
       returns an invalid_event failure Finding when the neighbor is accepted
  And it returns one failure per accepted neighbor, empty when every neighbor is rejected.

Cases are data; one pure probe feeds them to the real function and returns a list of failure strings
(empty when every case holds). No classes, no mocks: it builds a real StateMachine with honest-type's
state_machine(), and for the honest case hands honest-type's real transition() as run_transition. For
the two failing cases it injects a real plain function that wrongly accepts one class of adversarial
neighbor. The real honest_test.test_adversarial_state_machine is called; the sibling-authored
adversarial_neighbors it invokes is never touched here.

Standalone fragment; run_conformance.py / laws_htest.py are untouched.
"""

from honest_type import ok
from honest_type.state_machine import state_machine, transition

from honest_test import test_adversarial_state_machine

# A single-state, single-event machine. One member per set keeps the adversarial neighbors of a state
# (or event) from ever coinciding with another declared state (or event), so the real transition()
# rejects every neighbor with invalid_state / invalid_event and the honest case is a clean empty list.
_MACHINE = state_machine(
    states={"start"},
    events={"go"},
    transitions={("start", "go"): "start"},
    initial="start",
)


def _accept_state_neighbors(machine, current_state, event):
    """A dishonest transition that wrongly ACCEPTS any state not in the machine (an adversarial state
    neighbor), while deferring every valid-state call to the real transition. It never accepts an
    adversarial event neighbor, so only invalid_state failures are produced."""
    if current_state not in machine["states"]:
        return ok({"state": machine["initial"]})
    return transition(machine, current_state, event)


def _accept_event_neighbors(machine, current_state, event):
    """A dishonest transition that wrongly ACCEPTS any event not in the machine (an adversarial event
    neighbor), while deferring every valid-event call to the real transition. It never accepts an
    adversarial state neighbor, so only invalid_event failures are produced."""
    if event not in machine["events"]:
        return ok({"state": machine["initial"]})
    return transition(machine, current_state, event)


_CASES = [
    # HONEST: real honest-type transition rejects every adversarial neighbor -> empty list.
    {
        "label": "real transition rejects every neighbor",
        "run_transition": transition,
        "expect_empty": True,
        "expect_code": None,
    },
    # FAILING: a run_transition that wrongly accepts state neighbors -> invalid_state failures.
    {
        "label": "accepts a state-neighbor",
        "run_transition": _accept_state_neighbors,
        "expect_empty": False,
        "expect_code": "invalid_state",
    },
    # FAILING: a run_transition that wrongly accepts event neighbors -> invalid_event failures.
    {
        "label": "accepts an event-neighbor",
        "run_transition": _accept_event_neighbors,
        "expect_empty": False,
        "expect_code": "invalid_event",
    },
]


def probe_test_adversarial_state_machine():
    """test_adversarial_state_machine returns an empty list when every adversarial neighbor is rejected,
    and one failure Finding (code invalid_state for a state neighbor, invalid_event for an event neighbor,
    kind failure) per neighbor a dishonest run_transition accepts."""
    bad = []
    for case in _CASES:
        got = test_adversarial_state_machine(_MACHINE, case["run_transition"])
        if case["expect_empty"]:
            if got != []:
                bad.append(
                    f"test_adversarial_state_machine({case['label']}) -> {got}, expected []"
                )
            continue
        if not got:
            bad.append(
                f"test_adversarial_state_machine({case['label']}) -> [], "
                f"expected at least one {case['expect_code']} failure"
            )
            continue
        for finding in got:
            if finding["code"] != case["expect_code"]:
                bad.append(
                    f"test_adversarial_state_machine({case['label']}) produced a finding "
                    f"with code {finding['code']!r}, expected {case['expect_code']!r}"
                )
            if finding["kind"] != "failure":
                bad.append(
                    f"test_adversarial_state_machine({case['label']}) produced a finding "
                    f"with kind {finding['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_test_adversarial_state_machine()
    for line in bad:
        print(line)
    print(f"probe_test_adversarial_state_machine: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

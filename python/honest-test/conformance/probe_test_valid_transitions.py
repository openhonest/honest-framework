"""honest-test conformance: test_valid_transitions — every declared transition is correct.

The spec (§5.1): for each (state, event) -> next_state in the machine's transition table,
apply the event and emit a transition_incorrect failure when the result is not ok of the
expected next state. honest-type's bare-union model carries ok of a manifest as the manifest
itself ({"state": next_state}) and a fault as a dict carrying "code". This probe builds a
tiny turnstile machine as data and injects run_transition two ways: a correct one, which
must yield no findings, and one that returns the wrong next state, which must yield one
transition_incorrect failure per declared transition.

No classes, no mocks. It calls the real honest_test.test_valid_transitions.
"""

from honest_test import test_valid_transitions


def _machine():
    return {
        "states": ["locked", "unlocked"],
        "events": ["coin", "push"],
        "transitions": {
            ("locked", "coin"): "unlocked",
            ("locked", "push"): "locked",
            ("unlocked", "push"): "locked",
        },
        "initial": "locked",
        "terminal": [],
    }


def _correct_transition(machine, state, event):
    """A correct transition: the next-state manifest on a declared pair, the matching
    fault on an unknown state, unknown event, or undeclared pair."""
    if state not in machine["states"]:
        return {"code": "invalid_state"}
    if event not in machine["events"]:
        return {"code": "invalid_event"}
    key = (state, event)
    if key in machine["transitions"]:
        return {"state": machine["transitions"][key]}
    return {"code": "no_transition"}


def _wrong_next(machine, state, event):
    """Buggy: a declared transition lands in the wrong next state."""
    key = (state, event)
    if key in machine["transitions"]:
        return {"state": "WRONG"}
    return _correct_transition(machine, state, event)


def probe_test_valid_transitions():
    bad = []
    machine = _machine()

    clean = test_valid_transitions(machine, _correct_transition)
    if clean != []:
        bad.append(f"every declared transition correct should yield no findings, got {clean!r}")

    flagged = test_valid_transitions(machine, _wrong_next)
    declared = len(machine["transitions"])
    if len(flagged) != declared:
        bad.append(f"a wrong next state should yield one finding per declared transition ({declared}), got {len(flagged)}")
    for f in flagged:
        if f.get("code") != "transition_incorrect":
            bad.append(f"a wrong transition should carry code 'transition_incorrect', got {f.get('code')!r}")
        if f.get("kind") != "failure":
            bad.append(f"a transition_incorrect finding should be a failure, got kind {f.get('kind')!r}")
    return bad


def run():
    messages = probe_test_valid_transitions()
    if messages:
        print(f"FAIL HTEST-probe [test_valid_transitions]: {messages}")
    print(f"test_valid_transitions: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())

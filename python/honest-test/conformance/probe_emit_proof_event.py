"""honest-test conformance: emit_proof_event, the proof-event sink.

emit_proof_event emits one hf.proof.checked event through the injected honest-observe
runtime and does nothing else, making no decision because the event is already built
(.hd emit_proof_event note; spec §8.5; feature "emit_proof_event emits one proof
event through the injected observe runtime"). Its one observable effect is the call
to the injected runtime, so this probe injects a recording runtime and reads back
what it received.

No classes, no mocks. The runtime is a real pure closure defined here that records
each call into a list — a genuine injected boundary plug, not a stand-in for a
collaborator the sink reaches on its own. The function called is the real
honest_test.emit_proof_event. A ProofEvent is a dict (.hd type ProofEvent).
"""

from honest_test import emit_proof_event


def probe_emit_proof_event():
    """The injected runtime is called exactly once, and the emission names the
    hf.proof.checked event and carries the function it proved, so the proof event
    reaches honest-observe through the one injected seam."""
    bad = []

    captured = []

    def recording_runtime(*args, **kwargs):
        captured.append((args, kwargs))

    event = {
        "function_name": "mymod.double",
        "scenario": "double doubles its input",
        "cases_run": 7,
        "outcome": "proved",
        "line_coverage": 100,
        "branch_coverage": 100,
    }

    emit_proof_event(event, recording_runtime)

    if len(captured) != 1:
        bad.append(f"emit_proof_event should call the injected runtime exactly once, saw {len(captured)} calls")
        return bad

    blob = repr(captured[0])
    if "mymod.double" not in blob:
        bad.append(f"the emission should carry the function it proved: {captured[0]}")
    if "hf.proof.checked" not in blob:
        bad.append(f"the emission should name the hf.proof.checked event: {captured[0]}")

    return bad


def run():
    messages = probe_emit_proof_event()
    for message in messages:
        print(f"FAIL probe_emit_proof_event: {message}")
    print(f"probe_emit_proof_event: {'PASS' if not messages else str(len(messages)) + ' failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())

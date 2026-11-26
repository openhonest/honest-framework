# scenario: build_ack_event
"""Red test fragment for the honest-alerts `build_ack_event` scenario (one scenario only).

build_ack_event is the pure constructor of the alert.acknowledged event payload
(honest-alerts.hd, section 9.1 / 10 / 4.1): parts in, AckPayload out, no world and no fault.

The scenario (specs/features/honest-alerts.feature) fixes, clause by clause:

  - message_id is carried onto the payload so the mailbox projection can match acks to
    their message;
  - actor_ref is the acknowledging actor, placed on the payload under the field named
    `actor` (NEVER `actor_id`) as pure identity whose id serves actor- or broadcast-scoped
    acks;
  - reply_payload reaches the payload (for example the chosen reply option's payload);
  - acknowledged_at, read at the boundary and passed in, reaches the payload; this pure
    function never calls now();
  - session is placed on the payload under the field named `session` (NEVER `session_id`)
    as a typed SessionId when the ack came in under a DOM session, and NOTHING (None) when
    it did not -- the explicit absence case;
  - it places NO scope word on the payload: there is no scope field, so the only keys are
    message_id, actor, acknowledged_at, reply_payload and session.

Honest form: cases are data, one pure probe feeds them to the real build_ack_event, faults
are returned as a list of strings (the probe never raises to signal a failure). The ActorRef
and the AckPayload are plain dicts (no test-double classes); NOTHING is None. Every field of
every input is stated in full, with no default kwargs; absence (session NOTHING, empty
reply_payload) is written out explicitly as None / {}.

Run directly:
  cd python && uv run --package honest-alerts \
    python honest-alerts/conformance/laws_build_ack_event.py
"""

from honest_alerts import build_ack_event


# The acknowledging actor: pure identity, carries no session (ActorRef = {type, id, tenant_id}).
_ACTOR = {"type": "user", "id": "u1", "tenant_id": None}


_CASES = [
    # A session-scoped ack: it came in under DOM session "sess-7". The whole payload is pinned
    # as a literal, non-trivial expected value: message_id carried through, the actor on the
    # `actor` field (never actor_id), reply_payload passed straight through, acknowledged_at
    # passed straight through (never a now() call), the session on the `session` field (never
    # session_id), and NO scope word anywhere.
    {
        "given": {
            "message_id": "m1",
            "actor_ref": _ACTOR,
            "reply_payload": {"choice": "approve", "note": "ok by me"},
            "session": "sess-7",
            "acknowledged_at": 1700000000,
        },
        "expect": {
            "message_id": "m1",
            "actor": _ACTOR,
            "acknowledged_at": 1700000000,
            "reply_payload": {"choice": "approve", "note": "ok by me"},
            "session": "sess-7",
        },
    },
    # The explicit absence case: the ack did not come in under a DOM session, so session is
    # NOTHING (None), carried as None on the payload (not dropped, not defaulted). An empty
    # reply_payload is carried whole as {} (written out explicitly, never a default).
    {
        "given": {
            "message_id": "m2",
            "actor_ref": _ACTOR,
            "reply_payload": {},
            "session": None,
            "acknowledged_at": 1700000500,
        },
        "expect": {
            "message_id": "m2",
            "actor": _ACTOR,
            "acknowledged_at": 1700000500,
            "reply_payload": {},
            "session": None,
        },
    },
]


def probe_build_ack_event():
    """build_ack_event assembles the AckPayload from its parts -- message_id, the acknowledging
    actor (on the `actor` field), acknowledged_at, reply_payload and the acking session (on the
    `session` field, NOTHING when none) -- with no scope word on the payload: pure, parts in,
    payload out."""
    bad = []
    for case in _CASES:
        got = build_ack_event(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"build_ack_event(message_id={case['given']['message_id']!r}, "
                f"session={case['given']['session']!r}) -> {got}, expected {case['expect']}"
            )
    return bad


def run():
    bad = probe_build_ack_event()
    for line in bad:
        print("FAIL:", line)
    if not bad:
        print("laws_build_ack_event: ok")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(run())

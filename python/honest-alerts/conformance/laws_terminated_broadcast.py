# scenario: terminated_broadcast
"""Red test fragment for the `terminated_broadcast` scenario (honest-alerts, section 4.1).

Honest, data-driven, pure: cases are rows, one pure probe feeds each row to the REAL
terminated_broadcast and returns a list of failure strings (empty when the case holds).
No classes, no mocks, no patched boundary -- the real function is imported and called.

terminated_broadcast is the broadcast-scoped row of the scope_terminated dispatch
(honest-alerts.hd line 314):

    fn terminated_broadcast : (acks: list<any>, actor_ref: ActorRef, viewing_session: SessionId | NOTHING) -> bool

What the scenario fixes (specs/features/honest-alerts.feature, scenario terminated_broadcast):
  - acks is the alert.acknowledged event slice for THIS message, already selected by is_terminated.
  - actor_ref and viewing_session are both ignored: a broadcast-scoped ack by ANY one recipient
    terminates for EVERY viewer, the waiter (viewing_session = NOTHING) included.
  - It is terminated (True) when the acks slice is non-empty, that is, when ANY recipient
    acknowledged; False when the slice is empty (no recipient acknowledged).
  - Pure: an event slice in, a boolean out, no world and no fault.

Each row pins a concrete, non-trivial literal boolean the scenario fixes: a non-empty acks slice
-> True (by ANY recipient, including an ack whose actor is NOT this actor_ref, because the slice was
already selected for this broadcast message), and the explicit absence case: an empty slice -> False.

An alert.acknowledged event is an honest-observe Event envelope (any, because honest-observe owns the
type); its payload carries message_id, the acknowledging actor as an ActorRef (payload.actor), the
acking session (payload.session), acknowledged_at and reply_payload (honest-alerts.hd line 181, the
AckPayload note). The broadcast row reads none of those fields -- only whether the slice is non-empty
-- so the rows carry a faithful payload but the assertion depends only on slice length.

Hook constraint honoured: NO default kwargs in any builder; every field of the ack event and every
case input is written out explicitly. Absence is written as NOTHING (the module-owned sentinel,
resolved to None here until the module exports it), never left to a default. No data-holding
test-double classes: plain dicts and one plain builder function.
"""

# NOTHING: the absence arm of `SessionId | NOTHING` and of ActorRef.id/tenant_id. Resolved to None
# until the module exports its sentinel; the waiter view the scenario names explicitly.
try:  # pragma: no cover - resolved once the module exports its sentinel
    from honest_alerts import NOTHING
except ImportError:
    NOTHING = None


def _ack(message_id, acknowledged_at, actor, session, reply_payload):
    """An alert.acknowledged event envelope as is_terminated hands it in the slice (section 4.1).

    Every field explicit; no default kwargs. Faithful to the AckPayload note (honest-alerts.hd
    line 181): message_id, actor (ActorRef), acknowledged_at, reply_payload, session.
    """
    return {
        "event_type": "alert.acknowledged",
        "payload": {
            "message_id": message_id,
            "actor": actor,
            "acknowledged_at": acknowledged_at,
            "reply_payload": reply_payload,
            "session": session,
        },
    }


# The recipient actor whose mailbox is being computed. Ignored by this row, present so every row of
# the scope_terminated dispatch shares one signature. ActorRef is {type, id, tenant_id}
# (honest-alerts.hd line 67); every field written out, absence as NOTHING.
_RECIPIENT = {"type": "dom", "id": "actor-7", "tenant_id": NOTHING}

# A different actor than the recipient, for the "any recipient" distinction from the actor-scoped row.
_SOMEONE_ELSE = {"type": "dom", "id": "actor-99", "tenant_id": NOTHING}

# Each row is one input and the exact boolean it must produce. The behaviour lives in the data.
_CASES = [
    # Non-empty slice, ack by the recipient actor itself -> terminated for every viewer (True).
    {
        "name": "ack by a recipient -> terminated for every viewer",
        "given": {
            "acks": [
                _ack(
                    message_id="m1",
                    acknowledged_at=1500,
                    actor=_RECIPIENT,
                    session="sess-1",
                    reply_payload=NOTHING,
                )
            ],
            "actor_ref": _RECIPIENT,
            "viewing_session": "sess-other",
        },
        "expect": True,
    },
    # Non-empty slice, ack by ANOTHER actor (payload.actor.id != actor_ref.id). The slice was already
    # selected for this (broadcast) message, so ANY ack terminates. This distinguishes the broadcast
    # row from the actor-scoped row, which would return False for an ack by a non-recipient.
    {
        "name": "ack by any one recipient (not this actor) -> still terminated",
        "given": {
            "acks": [
                _ack(
                    message_id="m1",
                    acknowledged_at=1500,
                    actor=_SOMEONE_ELSE,
                    session="sess-9",
                    reply_payload=NOTHING,
                )
            ],
            "actor_ref": _RECIPIENT,
            "viewing_session": "sess-other",
        },
        "expect": True,
    },
    # The waiter view: viewing_session is NOTHING, yet a non-empty slice still terminates (the waiter
    # is included). viewing_session is ignored for the broadcast row; written out explicitly.
    {
        "name": "waiter view (viewing_session NOTHING) with an ack -> terminated",
        "given": {
            "acks": [
                _ack(
                    message_id="m1",
                    acknowledged_at=1500,
                    actor=_SOMEONE_ELSE,
                    session=NOTHING,
                    reply_payload=NOTHING,
                )
            ],
            "actor_ref": _RECIPIENT,
            "viewing_session": NOTHING,
        },
        "expect": True,
    },
    # Multiple acks in the slice -> still terminated (non-empty). Pins that the answer is slice
    # non-emptiness, not a single-element quirk.
    {
        "name": "several acks in the slice -> terminated",
        "given": {
            "acks": [
                _ack(
                    message_id="m1",
                    acknowledged_at=1500,
                    actor=_RECIPIENT,
                    session="sess-1",
                    reply_payload=NOTHING,
                ),
                _ack(
                    message_id="m1",
                    acknowledged_at=1600,
                    actor=_SOMEONE_ELSE,
                    session="sess-2",
                    reply_payload=NOTHING,
                ),
            ],
            "actor_ref": _RECIPIENT,
            "viewing_session": "sess-other",
        },
        "expect": True,
    },
    # The explicit absence case the scenario names: an empty ack slice means no recipient
    # acknowledged, so the broadcast message is NOT terminated (False). A stub `return True` fails
    # here; the True rows above fail a stub `return False`.
    {
        "name": "empty ack slice (no recipient acknowledged) -> not terminated",
        "given": {
            "acks": [],
            "actor_ref": _RECIPIENT,
            "viewing_session": "sess-other",
        },
        "expect": False,
    },
    # Absence case under the waiter view too: empty slice, NOTHING viewing_session -> False.
    {
        "name": "empty ack slice, waiter view -> not terminated",
        "given": {
            "acks": [],
            "actor_ref": _RECIPIENT,
            "viewing_session": NOTHING,
        },
        "expect": False,
    },
]


def probe_terminated_broadcast():
    """terminated_broadcast returns True whenever the ack slice for this message is non-empty (any
    recipient acknowledged, every viewer and the waiter included) and False when the slice is empty."""
    bad = []

    # Import inside the probe so a missing function reds as a behaviour failure line (the behaviour is
    # not yet present), never a bare collection/import crash.
    try:
        from honest_alerts import terminated_broadcast
    except ImportError as exc:
        return [f"terminated_broadcast is not importable from honest_alerts: {exc}"]

    for case in _CASES:
        got = terminated_broadcast(**case["given"])
        if got is not case["expect"]:
            bad.append(
                f"{case['name']}: terminated_broadcast({case['given']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )

    return bad


if __name__ == "__main__":
    import sys

    failures = probe_terminated_broadcast()
    if failures:
        for line in failures:
            print("FAIL:", line)
        sys.exit(1)
    print("ok: terminated_broadcast probe passed")

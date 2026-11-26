# scenario: terminated_actor
"""Red test for the terminated_actor scenario of honest-alerts (specs/features/honest-alerts.feature).

Scenario clause under test:
  "it is the actor-scoped row of the scope_terminated dispatch, answering whether an
   actor-scoped message has been acknowledged for every viewer ... it is terminated when some
   ack's payload.actor_id equals actor_ref.id, that is, when the recipient actor acknowledged
   on any one of its sessions ... viewing_session is ignored here; an actor-scoped ack
   terminates for every viewer, the waiter (viewing_session = NOTHING) included ... an ack from
   a non-recipient does not terminate an actor-scoped message (no ack whose actor_id equals
   actor_ref.id)."

terminated_actor is the pure "actor" row of the scope_terminated dispatch table
(honest-alerts.hd line 79; fn declared at line 311):

    fn terminated_actor : (acks: list<any>, actor_ref: ActorRef, viewing_session: SessionId | NOTHING) -> bool

It is a pure function: an alert.acknowledged event slice and the recipient actor in, a boolean
out, no world and no fault. The honest way to test a pure function is to call it with data and
assert the exact boolean it must return. No mock, no stub of our own code, no circular oracle:
each expected value is a literal True/False written out in the case data.

The payload shape is NOT flat. The alert.acknowledged event carries an AckPayload
(honest-alerts.hd type AckPayload, lines 180-184) whose actor field is an ActorRef, not a flat
id string. The .hd is explicit for this row (line 312): "It is terminated when some ack's
payload.actor.id equals actor_ref.id (payload.actor is an ActorRef, so its id is read as
payload.actor.id, never as a payload.actor_id field)". So each ack here nests
{"actor": {"type": ..., "id": ...}} under payload, and the match reads payload.actor.id. A
fragment that read payload.actor_id would be testing a shape the module forbids; this one does
not.

An alert.acknowledged event is an honest-observe Event envelope (any, because honest-observe owns
the type): {"event_type": "alert.acknowledged", "timestamp": int, "payload": AckPayload}. acks
is the slice already selected by is_terminated (every ack whose payload.message_id equals the
message's id), so these cases pass that slice directly.

An ActorRef is pure identity: {"type": ActorType, "id": str | NOTHING, "tenant_id": str | NOTHING}
(honest-alerts.hd type ActorRef); terminated_actor reads actor_ref.id for the match.

No default kwargs in any builder here: every field of every ack and every actor ref is passed
explicitly, and absence (session, tenant_id, viewing_session) is written as None (NOTHING)
explicitly, never left to a default. No data-holding classes: plain dicts and functions.
"""

from honest_alerts import terminated_actor


def _actor_ref(type_, id_, tenant_id):
    """An ActorRef (honest-alerts.hd type ActorRef): pure identity, every field explicit."""
    return {"type": type_, "id": id_, "tenant_id": tenant_id}


def _ack(message_id, acknowledged_at, actor, reply_payload, session):
    """One alert.acknowledged Event envelope carrying an AckPayload (honest-alerts.hd lines 180-184).

    actor is an ActorRef (payload.actor); the actor-scoped match reads payload.actor.id. Every
    field is passed explicitly; session absence is written as None (NOTHING), not defaulted.
    """
    return {
        "event_type": "alert.acknowledged",
        "timestamp": acknowledged_at,
        "payload": {
            "message_id": message_id,
            "actor": actor,
            "acknowledged_at": acknowledged_at,
            "reply_payload": reply_payload,
            "session": session,
        },
    }


_RECIPIENT = _actor_ref("user", "u1", None)
_OTHER = _actor_ref("user", "u2", None)

_CASES = [
    # The recipient actor acknowledged: terminated for every viewer. (literal True)
    {
        "given": {
            "acks": [_ack("m1", 1500, _actor_ref("user", "u1", None), {}, "s1")],
            "actor_ref": _RECIPIENT,
            "viewing_session": "s1",
        },
        "expect": True,
    },
    # viewing_session is ignored: a recipient ack terminates the waiter view (NOTHING) too. (literal True)
    {
        "given": {
            "acks": [_ack("m1", 1500, _actor_ref("user", "u1", None), {}, None)],
            "actor_ref": _RECIPIENT,
            "viewing_session": None,
        },
        "expect": True,
    },
    # The recipient acked on one of its sessions among several acks: still terminated. (literal True)
    {
        "given": {
            "acks": [
                _ack("m1", 1400, _actor_ref("user", "u2", None), {}, "sX"),
                _ack("m1", 1500, _actor_ref("user", "u1", None), {}, "s9"),
            ],
            "actor_ref": _RECIPIENT,
            "viewing_session": "s9",
        },
        "expect": True,
    },
    # An ack from a non-recipient only: no ack whose actor.id equals actor_ref.id, NOT terminated. (literal False)
    {
        "given": {
            "acks": [_ack("m1", 1500, _OTHER, {}, "s1")],
            "actor_ref": _RECIPIENT,
            "viewing_session": "s1",
        },
        "expect": False,
    },
    # Absence case: no acks at all, so NOT terminated. (explicit absence -> False)
    {
        "given": {
            "acks": [],
            "actor_ref": _RECIPIENT,
            "viewing_session": None,
        },
        "expect": False,
    },
]


def probe_terminated_actor():
    """An actor-scoped message terminates for every viewer when the recipient actor acked, and only then."""
    bad = []
    for case in _CASES:
        got = terminated_actor(**case["given"])
        if got != case["expect"]:
            bad.append(f"terminated_actor({case['given']}) -> {got!r}, expected {case['expect']!r}")
    return bad


if __name__ == "__main__":
    failures = probe_terminated_actor()
    if failures:
        print(f"RED: {len(failures)} failure(s)")
        for f in failures:
            print("  -", f)
    else:
        print("GREEN: terminated_actor holds for every case")

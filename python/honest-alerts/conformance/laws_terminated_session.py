# scenario: terminated_session
"""Red test for the terminated_session scenario of honest-alerts (specs/features/honest-alerts.feature).

Scenario clauses under test (terminated_session, the session-scoped row of the scope_terminated
dispatch):
  "it is terminated only when viewing_session is not NOTHING and some ack's acking session
   (payload.session) equals viewing_session"
  "viewing_session of NOTHING is the waiter view and equals no session, so the NOTHING case
   returns false and a session dismissal never ends a waiting send_and_wait"
  "a session-scoped ack by one DOM session therefore terminates only for that same session;
   other sessions of the same actor still see it; it is pure, a boolean out, no world and no fault"

terminated_session is a pure function: an ack slice and the viewer in, a boolean out. The honest
way to exercise it is to call the real function on data rows and assert the boolean it returns.
No mock, no stand-in -- it reads no world. Each row states its ack slice and viewer in full and the
boolean the scenario fixes.

The .hd signature is terminated_session(acks, actor_ref, viewing_session) -> bool. acks is the
alert.acknowledged event slice already selected by is_terminated for this message; each ack is an
alert.acknowledged event whose payload (type AckPayload) carries the acking session under
payload.session (honest-alerts.hd type AckPayload record: message_id, actor, acknowledged_at,
reply_payload, session: SessionId | NOTHING). The field is session, NEVER session_id. actor_ref is
unused by this row, present only so every row of the dispatch shares one signature (honest-alerts.hd
terminated_session). viewing_session is a SessionId | NOTHING, the viewer the read is taken for;
NOTHING is the waiter view and matches no session.

No builder here takes a default keyword argument: every field of every ActorRef, AckPayload and
alert.acknowledged event is stated explicitly at each call site, and absence (the ack that came in
under no DOM session, an ActorRef carrying no tenant) is written as None explicitly, never left to a
default. The data is plain dicts assembled by plain functions; there is no data-holding class.
"""

from honest_alerts import terminated_session

# honest-alerts represents NOTHING as Python None (a SessionId | NOTHING slot carries either an
# opaque session string or the absence). The waiter view is viewing_session None.
NOTHING = None


def _actor_ref(type_, id_, tenant_id):
    """A flat ActorRef (honest-alerts.hd type ActorRef record: type, id, tenant_id): pure identity,
    no session. Unused by this dispatch row but part of the shared signature. Every field is passed
    explicitly by the caller; there is no default."""
    return {"type": type_, "id": id_, "tenant_id": tenant_id}


def _ack_event(message_id, acting_actor, acknowledged_at, reply_payload, session):
    """One alert.acknowledged event (an acks element). Its payload is an AckPayload
    (honest-alerts.hd: message_id, actor, acknowledged_at, reply_payload, session). terminated_session
    reads payload.session -- the DOM session the acknowledgment came in under -- NEVER
    payload.session_id. session of None (NOTHING) means the ack did not come in under a DOM session.
    Every field is passed explicitly by the caller; there is no default."""
    return {
        "event_type": "alert.acknowledged",
        "aggregate_id": message_id,
        "payload": {
            "message_id": message_id,
            "actor": acting_actor,
            "acknowledged_at": acknowledged_at,
            "reply_payload": reply_payload,
            "session": session,
        },
    }


# One recipient ActorRef, reused across the rows as the (unused) actor_ref argument. Stated in full.
_RECIPIENT = _actor_ref("user", "recipient-1", NOTHING)

# Ack events, each stating its session and every other AckPayload field in full.
_ACK_S1 = _ack_event("m1", _RECIPIENT, 1000, {}, "s1")
_ACK_S2 = _ack_event("m1", _RECIPIENT, 1000, {}, "s2")
_ACK_S3 = _ack_event("m1", _RECIPIENT, 1000, {}, "s3")
_ACK_NO_SESSION = _ack_event("m1", _RECIPIENT, 1000, {}, NOTHING)


# Each case states the ack slice and the viewer in full and the boolean the scenario fixes.
# The waiter-view rows (viewing_session None) are the explicit absence cases the scenario names
# ("the NOTHING case returns false ... a session dismissal never ends a waiting send_and_wait").
_CASES = [
    {
        "name": "matching-session-ack-terminates",
        "given": {"acks": [_ACK_S1], "actor_ref": _RECIPIENT, "viewing_session": "s1"},
        "expect": True,
    },
    {
        "name": "other-session-ack-does-not-terminate",
        "given": {"acks": [_ACK_S2], "actor_ref": _RECIPIENT, "viewing_session": "s1"},
        "expect": False,
    },
    {
        "name": "match-among-several-acks",
        "given": {
            "acks": [_ACK_S2, _ACK_S3, _ACK_S1],
            "actor_ref": _RECIPIENT,
            "viewing_session": "s1",
        },
        "expect": True,
    },
    {
        "name": "waiter-view-never-matches-a-session-scoped-ack",
        "given": {"acks": [_ACK_S1], "actor_ref": _RECIPIENT, "viewing_session": NOTHING},
        "expect": False,
    },
    {
        "name": "waiter-view-never-matches-a-no-session-ack",
        "given": {"acks": [_ACK_NO_SESSION], "actor_ref": _RECIPIENT, "viewing_session": NOTHING},
        "expect": False,
    },
    {
        "name": "no-acks-not-terminated-for-a-session",
        "given": {"acks": [], "actor_ref": _RECIPIENT, "viewing_session": "s1"},
        "expect": False,
    },
    {
        "name": "no-acks-not-terminated-for-the-waiter",
        "given": {"acks": [], "actor_ref": _RECIPIENT, "viewing_session": NOTHING},
        "expect": False,
    },
]


def probe_terminated_session():
    """terminated_session is terminated only when viewing_session is not NOTHING and some ack's
    payload.session equals viewing_session; the waiter view (NOTHING) matches no session, and a
    session-scoped ack by one DOM session terminates only for that same session."""
    bad = []
    for case in _CASES:
        got = terminated_session(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"terminated_session({case['name']}: {case['given']}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )
    return bad


if __name__ == "__main__":
    failures = probe_terminated_session()
    for line in failures:
        print(line)
    raise SystemExit(1 if failures else 0)

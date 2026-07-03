"""honest-alerts conformance laws: the mailbox projection and message termination (section 4).

The portable surface is value cases in suite.json (checked by value-check.py). These laws pin the same
pure functions for the per-module gate and drive 100% coverage: recipient matching in all its branches,
every termination condition (ttl at and past its edge, acknowledgment in each scope, event with and
without a filter, never), and the mailbox projection's recipient, time-window, termination, and ordering
behaviour. Pure assertions: data in, data out. Time is epoch seconds.
"""

from honest_alerts import ACK_SCOPES, TERMINATION_CONDITIONS, is_terminated, mailbox, recipient_matches


def _sent(message_id, recipient, sent_at, termination, ack_scope="actor"):
    """An alert.sent event carrying a message, shaped as the mailbox reads it (section 4.1)."""
    return {
        "event_type": "alert.sent",
        "timestamp": sent_at,
        "payload": {
            "message_id": message_id,
            "recipient": recipient,
            "sent_at": sent_at,
            "ack_scope": ack_scope,
            "termination": termination,
        },
    }


def _ack(message_id, at, actor_id=None, session_id=None):
    """An alert.acknowledged event (section 4.1)."""
    return {
        "event_type": "alert.acknowledged",
        "timestamp": at,
        "payload": {"message_id": message_id, "actor_id": actor_id, "session_id": session_id},
    }


def _law_exports():
    import honest_alerts

    bad = []
    expected = ["mailbox", "is_terminated", "recipient_matches", "TERMINATION_CONDITIONS", "ACK_SCOPES"]
    if sorted(getattr(honest_alerts, "__all__", [])) != sorted(expected):
        bad.append(f"__all__ should be exactly the public surface: {getattr(honest_alerts, '__all__', None)}")
    missing = [name for name in expected if not hasattr(honest_alerts, name)]
    if missing:
        bad.append(f"__all__ names not importable: {missing}")
    return bad


def _law_vocabularies():
    bad = []
    if TERMINATION_CONDITIONS != frozenset({"ttl", "acknowledged", "event", "never"}):
        bad.append(f"TERMINATION_CONDITIONS should be the four declared conditions: {TERMINATION_CONDITIONS}")
    if ACK_SCOPES != frozenset({"session", "actor", "broadcast"}):
        bad.append(f"ACK_SCOPES should be the three declared scopes: {ACK_SCOPES}")
    return bad


def _law_recipient_matches():
    bad = []
    user = {"type": "user", "id": "u1", "tenant_id": "acme"}
    if recipient_matches({"type": "dom", "id": None}, user) is not False:
        bad.append("a different actor type does not match")
    if recipient_matches({"type": "dom", "id": None}, {"type": "dom", "id": "s1"}) is not True:
        bad.append("a None recipient id broadcasts to every actor of that type")
    if recipient_matches({"type": "user", "id": "u1"}, user) is not True:
        bad.append("a matching id matches")
    if recipient_matches({"type": "user", "id": "u2"}, user) is not False:
        bad.append("a non-matching id does not match")
    if recipient_matches({"type": "user", "id": "u1", "tenant_id": "other"}, user) is not False:
        bad.append("a recipient tenant_id must equal the actor's")
    if recipient_matches({"type": "user", "id": "u1", "tenant_id": "acme"}, user) is not True:
        bad.append("a matching tenant_id matches")
    return bad


def _law_terminated_ttl():
    bad = []
    event = _sent("m1", {"type": "user", "id": "u1"}, 1000, {"condition": "ttl", "ttl_seconds": 10})
    actor = {"type": "user", "id": "u1"}
    if is_terminated(event, actor, [event], 1005) is not False:
        bad.append("a ttl message is live before it expires")
    if is_terminated(event, actor, [event], 1010) is not False:
        bad.append("a ttl message is live exactly at its edge (sent_at + ttl)")
    if is_terminated(event, actor, [event], 1011) is not True:
        bad.append("a ttl message is terminated one second past its edge")
    return bad


def _law_terminated_acknowledged():
    bad = []
    actor = {"type": "user", "id": "u1", "session_id": "s1"}
    # session scope
    ses = _sent("m1", {"type": "user", "id": "u1"}, 1000, {"condition": "acknowledged"}, ack_scope="session")
    if is_terminated(ses, actor, [ses], 2000) is not False:
        bad.append("a session-scope message with no ack is live")
    if is_terminated(ses, actor, [ses, _ack("m1", 1500, session_id="s1")], 2000) is not True:
        bad.append("a session-scope message is terminated once this session acks")
    if is_terminated(ses, actor, [ses, _ack("m1", 1500, session_id="s2")], 2000) is not False:
        bad.append("a session-scope message stays live when a different session acks")
    # actor scope
    act = _sent("m2", {"type": "user", "id": "u1"}, 1000, {"condition": "acknowledged"}, ack_scope="actor")
    if is_terminated(act, actor, [act, _ack("m2", 1500, actor_id="u1")], 2000) is not True:
        bad.append("an actor-scope message is terminated once the actor acks")
    if is_terminated(act, actor, [act, _ack("m2", 1500, actor_id="u2")], 2000) is not False:
        bad.append("an actor-scope message stays live when a different actor acks")
    # broadcast scope
    bc = _sent("m3", {"type": "dom", "id": None}, 1000, {"condition": "acknowledged"}, ack_scope="broadcast")
    if is_terminated(bc, actor, [bc], 2000) is not False:
        bad.append("a broadcast message with no ack is live")
    if is_terminated(bc, actor, [bc, _ack("m3", 1500, actor_id="anyone")], 2000) is not True:
        bad.append("a broadcast message is terminated once any recipient acks")
    return bad


def _law_terminated_event():
    bad = []
    actor = {"type": "user", "id": "u1"}
    spec = {"condition": "event", "event_type": "system.maintenance_completed"}
    msg = _sent("m1", {"type": "user", "id": "u1"}, 1000, spec)
    done = {"event_type": "system.maintenance_completed", "timestamp": 1500, "payload": {}}
    early = {"event_type": "system.maintenance_completed", "timestamp": 900, "payload": {}}
    if is_terminated(msg, actor, [msg], 2000) is not False:
        bad.append("an event-terminated message is live before the terminating event")
    if is_terminated(msg, actor, [msg, done], 2000) is not True:
        bad.append("an event-terminated message ends when the terminating event is appended")
    if is_terminated(msg, actor, [msg, early], 2000) is not False:
        bad.append("a terminating event before the message was sent does not count")
    at_send = {"event_type": "system.maintenance_completed", "timestamp": 1000, "payload": {}}
    if is_terminated(msg, actor, [msg, at_send], 2000) is not True:
        bad.append("a terminating event at exactly the send time counts (the >= edge)")
    # with a payload filter
    fspec = {"condition": "event", "event_type": "job.finished", "event_filter": {"job_id": "j9"}}
    fmsg = _sent("m2", {"type": "user", "id": "u1"}, 1000, fspec)
    match = {"event_type": "job.finished", "timestamp": 1500, "payload": {"job_id": "j9"}}
    miss = {"event_type": "job.finished", "timestamp": 1500, "payload": {"job_id": "j0"}}
    if is_terminated(fmsg, actor, [fmsg, match], 2000) is not True:
        bad.append("an event filter that matches terminates the message")
    if is_terminated(fmsg, actor, [fmsg, miss], 2000) is not False:
        bad.append("an event filter that does not match leaves the message live")
    return bad


def _law_terminated_never():
    bad = []
    actor = {"type": "user", "id": "u1"}
    msg = _sent("m1", {"type": "user", "id": "u1"}, 1000, {"condition": "never"})
    if is_terminated(msg, actor, [msg], 9999999) is not False:
        bad.append("a never-terminated message is always live")
    return bad


def _law_mailbox():
    bad = []
    actor = {"type": "user", "id": "u1"}
    mine_new = _sent("m2", {"type": "user", "id": "u1"}, 2000, {"condition": "never"})
    mine_old = _sent("m1", {"type": "user", "id": "u1"}, 1000, {"condition": "never"})
    not_mine = _sent("m3", {"type": "user", "id": "u2"}, 1000, {"condition": "never"})
    future = _sent("m4", {"type": "user", "id": "u1"}, 5000, {"condition": "never"})
    gone = _sent("m5", {"type": "user", "id": "u1"}, 1000, {"condition": "ttl", "ttl_seconds": 5})
    at_now = _sent("m6", {"type": "user", "id": "u1"}, 3000, {"condition": "never"})
    events = [mine_new, mine_old, not_mine, future, gone, at_now]

    pending = mailbox(actor, events, 3000)
    ids = [e["payload"]["message_id"] for e in pending]
    if ids != ["m1", "m2", "m6"]:
        bad.append(f"mailbox includes a message sent at exactly at_time (the <= edge), oldest first, excluding others/future/terminated: {ids}")
    if mailbox({"type": "user", "id": "nobody"}, events, 3000) != []:
        bad.append("an actor with no messages has an empty mailbox")
    return bad


_LAWS = {
    "exports": _law_exports,
    "vocabularies": _law_vocabularies,
    "recipient_matches": _law_recipient_matches,
    "terminated_ttl": _law_terminated_ttl,
    "terminated_acknowledged": _law_terminated_acknowledged,
    "terminated_event": _law_terminated_event,
    "terminated_never": _law_terminated_never,
    "mailbox": _law_mailbox,
}


def run():
    violations = {name: law() for name, law in _LAWS.items()}
    failed = {name: msgs for name, msgs in violations.items() if msgs}
    passed = len(_LAWS) - len(failed)
    for name, msgs in failed.items():
        print(f"FAIL HA-law [{name}]: {msgs}")
    print(f"HA laws: {passed} passed, {len(failed)} failed, {len(_LAWS)} total")
    return 0 if not failed else 1

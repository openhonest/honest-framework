# scenario: mailbox
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::mailbox -> feature=specs/features/honest-alerts.feature::mailbox
"""Red test for the mailbox scenario of honest-alerts (specs/features/honest-alerts.feature).

Scenario clauses under test (feature lines 119-126):

  "it keeps the alert.sent events whose recipient matches actor_ref and whose sent_at is at or
   before at_time, invokes is_terminated for each (handing it actor_ref, at_time, events and
   viewing_session) to drop the terminated ones, and returns the pending Messages ordered by
   sent_at ascending"

  "viewing_session is an explicit SessionId or NOTHING, never a defaulted optional ... it is passed
   straight through to is_terminated unchanged and no session is read off actor_ref"

  "a session-scoped ack terminates only when an ack's acking session equals viewing_session, and
   viewing_session of NOTHING (the waiter view) never matches, so a session dismissal never ends a
   waiter" (is_terminated clause, exercised through mailbox's fold over the given events)

mailbox is a pure projection over the events handed to it:
    mailbox(actor_ref, at_time, events, viewing_session) -> list<Message> | Fault
(honest-alerts.hd, fn mailbox). It reads nothing but the given events. The honest way to exercise a
pure function is to call it on data and compare the returned Messages against literal expected
values written out here. No mock, no stand-in, no recomputation from the function under test.

Each alert.sent event carries the Message as its payload (run_send emits alert.sent with the Message
as payload). Each alert.acknowledged event carries an AckPayload (honest-alerts.hd type AckPayload):
message_id, actor (an ActorRef), session (a SessionId | NOTHING), acknowledged_at, reply_payload.
is_terminated selects the ack slice by payload.message_id and, for a session-scoped message,
terminates only when some ack's payload.session equals viewing_session. The ack's acting identity is
read as payload.actor.id and the acking session as payload.session (never actor_id / session_id).

The expected value this probe pins is the ordered list of Messages mailbox must return, compared by
message_id, so an empty-stub mailbox (returning []) fails every non-absence case.

CONSTRAINTS honoured here: no default kwargs in any builder -- every field is passed explicitly, and
every absence (viewing_session, tenant_id, the inapplicable TerminationSpec fields) is written out as
None. No data-holding test-double classes; the records are plain dicts built by plain functions.
"""

from honest_alerts import is_terminated, mailbox


NOTHING = None


def _actor(type_, id_, tenant_id):
    """A flat ActorRef (honest-alerts.hd type ActorRef): pure identity, carries no session.
    tenant_id is written out explicitly, NOTHING when the reference is not tenant-scoped."""
    return {"type": type_, "id": id_, "tenant_id": tenant_id}


def _ttl_termination(ttl_seconds):
    """A ttl TerminationSpec (honest-alerts.hd type TerminationSpec). Only ttl_seconds applies; the
    fields that do not apply to the ttl condition are NOTHING, written out, never absent."""
    return {
        "condition": "ttl",
        "ttl_seconds": ttl_seconds,
        "event_type": NOTHING,
        "event_filter": NOTHING,
    }


def _acknowledged_termination():
    """An acknowledged TerminationSpec: the message ends when its ack_scope is satisfied. No field
    carries the condition here (the message's ack_scope does), so every optional field is NOTHING."""
    return {
        "condition": "acknowledged",
        "ttl_seconds": NOTHING,
        "event_type": NOTHING,
        "event_filter": NOTHING,
    }


def _message(message_id, recipient, sent_at, termination, ack_scope):
    """A flat Message (honest-alerts.hd type Message). Every field is passed explicitly; the optional
    fields this projection does not read are still written out as NOTHING, never defaulted."""
    return {
        "message_id": message_id,
        "message_type": "order.placed",
        "message_version": "v1",
        "sender": _actor("user", "sender-1", NOTHING),
        "recipient": recipient,
        "channel": "dom",
        "subject_label_id": "subject.order_placed",
        "body_label_id": NOTHING,
        "payload": {},
        "dom_surface": "toast",
        "dom_target": NOTHING,
        "reply_required": False,
        "reply_options": NOTHING,
        "resume_token": NOTHING,
        "termination": termination,
        "ack_scope": ack_scope,
        "sent_at": sent_at,
    }


def _sent_event(message):
    """An honest-observe alert.sent Event carrying the Message as its payload."""
    return {
        "event_type": "alert.sent",
        "payload": message,
        "timestamp": message["sent_at"],
    }


def _ack_event(message_id, actor_ref, session, acknowledged_at):
    """An honest-observe alert.acknowledged Event carrying an AckPayload (honest-alerts.hd type
    AckPayload): actor is an ActorRef (read as payload.actor.id), session is the acking SessionId or
    NOTHING (read as payload.session). Both are passed explicitly, absence written as NOTHING."""
    return {
        "event_type": "alert.acknowledged",
        "payload": {
            "message_id": message_id,
            "actor": actor_ref,
            "acknowledged_at": acknowledged_at,
            "reply_payload": {},
            "session": session,
        },
        "timestamp": acknowledged_at,
    }


def _is_fault(value):
    """True when value is the honest-alerts Fault arm (reserved is_err tag true). Read directly off
    the returned value; nothing is recomputed from mailbox, so this is not a circular oracle."""
    if isinstance(value, dict):
        return value.get("is_err") is True
    return getattr(value, "is_err", None) is True


def _ids(result):
    """The message_id sequence of a returned list<Message>, the literal the cases compare against."""
    return [m["message_id"] for m in result]


_ME = _actor("user", "me", NOTHING)
_OTHER = _actor("user", "other", NOTHING)

# Two live ttl messages addressed to me, one addressed to someone else, one sent in the future
# (after at_time). The projection must keep only the two live, matching, in-time messages and
# return them sent_at ascending.
_M_OLD = _message("m-old", _ME, 100, _ttl_termination(1000), "session")
_M_NEW = _message("m-new", _ME, 200, _ttl_termination(1000), "session")
_M_OTHER = _message("m-other", _OTHER, 150, _ttl_termination(1000), "session")
_M_AT_TIME = _message("m-at-time", _ME, 300, _ttl_termination(1000), "session")
_M_FUTURE = _message("m-future", _ME, 301, _ttl_termination(1000), "session")

# A session-scoped acknowledged message to me, used to exercise the session-scoped ack fold.
_M_SESSION = _message("m-session", _ME, 100, _acknowledged_termination(), "session")


_CASES = [
    {
        "name": "keeps-matching-in-time-live-ordered-oldest-first",
        "given": {
            "actor_ref": _ME,
            "at_time": 300,
            "events": [
                _sent_event(_M_NEW),     # deliberately out of order in the event list
                _sent_event(_M_OTHER),   # addressed to another actor -> excluded
                _sent_event(_M_OLD),
                _sent_event(_M_AT_TIME),
                _sent_event(_M_FUTURE),  # sent_at 301 > at_time 300 -> excluded
            ],
            "viewing_session": "sess-A",
        },
        "expect_ids": ["m-old", "m-new", "m-at-time"],
    },
    {
        "name": "session-ack-matching-viewing-session-terminates",
        "given": {
            "actor_ref": _ME,
            "at_time": 300,
            "events": [
                _sent_event(_M_SESSION),
                _ack_event("m-session", _ME, "sess-A", 150),
            ],
            "viewing_session": "sess-A",
        },
        # The ack's session equals the viewing_session, so the message is terminated for this viewer.
        "expect_ids": [],
    },
    {
        "name": "session-ack-under-a-different-session-does-not-terminate-for-this-viewer",
        "given": {
            "actor_ref": _ME,
            "at_time": 300,
            "events": [
                _sent_event(_M_SESSION),
                _ack_event("m-session", _ME, "sess-B", 150),
            ],
            "viewing_session": "sess-A",
        },
        # The ack came in under sess-B; this read is taken for sess-A, so it stays pending.
        "expect_ids": ["m-session"],
    },
    {
        "name": "waiter-view-NOTHING-never-matches-a-session-ack",
        "given": {
            "actor_ref": _ME,
            "at_time": 300,
            "events": [
                _sent_event(_M_SESSION),
                _ack_event("m-session", _ME, "sess-A", 150),
            ],
            "viewing_session": NOTHING,
        },
        # The waiter belongs to no DOM session; viewing_session of NOTHING matches no ack session,
        # so a session dismissal never ends the waiter and the message stays pending.
        "expect_ids": ["m-session"],
    },
    {
        "name": "no-events-is-an-empty-mailbox",
        "given": {
            "actor_ref": _ME,
            "at_time": 300,
            "events": [],
            "viewing_session": "sess-A",
        },
        # The explicit absence case: nothing handed in, nothing pending.
        "expect_ids": [],
    },
]


def probe_mailbox():
    """mailbox returns exactly the alert.sent Messages addressed to the actor and in-time, with the
    terminated ones dropped for the viewer the read is taken for (viewing_session passed through to
    is_terminated unchanged, NOTHING being the waiter view that no session ack terminates), ordered
    by sent_at ascending."""
    bad = []
    for case in _CASES:
        g = case["given"]
        got = mailbox(g["actor_ref"], g["at_time"], g["events"], g["viewing_session"])
        if _is_fault(got):
            bad.append(
                f"mailbox({case['name']}) -> Fault {got!r}; expected list<Message> with ids "
                f"{case['expect_ids']} (no undeclared ack_scope here, so no server Fault is owed)"
            )
            continue
        if not isinstance(got, list):
            bad.append(
                f"mailbox({case['name']}) -> {got!r}; expected a list<Message> with ids {case['expect_ids']}"
            )
            continue
        got_ids = _ids(got)
        if got_ids != case["expect_ids"]:
            bad.append(
                f"mailbox({case['name']}) -> ids {got_ids}, expected {case['expect_ids']}"
            )
    return bad


def probe_mailbox_forwards_scope_fault():
    """A Fault from the termination rule survives the mailbox projection."""
    message = _message("invalid-scope", _ME, 299, _acknowledged_termination(), "unknown")
    events = [_sent_event(message)]
    expected = is_terminated(message, _ME, 300, events, NOTHING)
    actual = mailbox(_ME, 300, events, NOTHING)
    failures = []
    if not _is_fault(expected) or expected["code"] != "unknown_ack_scope" or expected["category"] != "server":
        failures.append(f"is_terminated returned {expected!r}, expected unknown_ack_scope server Fault")
    if actual != expected:
        failures.append(f"mailbox returned {actual!r}, expected the unchanged termination Fault {expected!r}")
    return failures


if __name__ == "__main__":
    failures = probe_mailbox() + probe_mailbox_forwards_scope_fault()
    for line in failures:
        print(line)
    raise SystemExit(1 if failures else 0)

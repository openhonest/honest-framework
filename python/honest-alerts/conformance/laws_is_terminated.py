# scenario: is_terminated
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::is_terminated -> feature=specs/features/honest-alerts.feature::is_terminated
"""Red test for the is_terminated scenario of honest-alerts (specs/features/honest-alerts.feature).

is_terminated decides whether one message has terminated for the viewer the read is taken for at
at_time -- the predicate mailbox folds with. It reads msg.termination and branches on its condition:

  - ttl: terminated when at_time is past sent_at + ttl_seconds (the edge is still live);
  - event: terminated when an event of the spec's event_type at or after sent_at matches the
    optional event_filter;
  - never: never terminated;
  - acknowledged: it selects the alert.acknowledged event slice for this message (every event
    whose payload.message_id equals the message's id) and dispatches on the message's ack_scope
    through the scope_terminated table (session / actor / broadcast) plus a no-match row.

The ack-scope rows the scenario fixes (feature lines 136-139):
  - session: terminated only when an ack's acking session equals viewing_session; viewing_session
    of NOTHING (the waiter view) never matches, so a session dismissal never ends a waiter;
  - actor: terminated for every viewer on an ack by the recipient actor; an ack from a
    non-recipient (no ack whose payload.actor.id equals actor_ref.id) does NOT terminate;
  - broadcast: terminated for every viewer on an ack by any recipient; an ack from a non-recipient
    does NOT terminate when the ack slice for this message is empty;
  - no-match row: ack_scope is a bounded AckScope fixed at build time, so a value the table does
    not carry is a program bug, not client input -- is_terminated returns a server Fault via
    alerts_fault (code unknown_ack_scope, category server; spec section 6b) rather than a silent
    False.

Signature (explorer module_ir): is_terminated(msg, actor_ref, at_time, events, viewing_session) ->
bool | Fault, pure, reached by import. msg is a Message record; events is the honest-observe event
slice mailbox was handed; viewing_session is an explicit SessionId or NOTHING (None), never a
defaulted optional. The AckPayload fields are `actor` (an ActorRef) and `session`: this probe reads
payload.actor.id and payload.session, NEVER actor_id or session_id (honest-alerts.hd type AckPayload).

Honest form: cases are data, one pure probe feeds them to the real is_terminated, faults are a list
of strings. Message, ActorRef, TerminationSpec and events are plain dicts (no data-holding classes).
There is ONE flat-record builder, `_flat`, driven by a table of field names: each shape (ActorRef,
honest-observe event) is a row naming its own keys, and every call site passes the shape name
explicitly, so the near-identical per-shape builders collapse into one function over a table rather
than two shape-identical copies. There are NO per-shape wrapper functions around `_flat`: a wrapper
that only forwards a fixed shape name would be a second builder of identical shape, the very finding
this fragment fixes, so `_flat("actor", ...)` and `_flat("event", ...)` are written at the call
site directly. NOTHING is None, and every absence (ttl_seconds, event_type, event_filter, session,
actor) is written out explicitly as None at the call site, never left to a default kwarg. A Fault is recognized by the
reserved is_err tag being true (honest-alerts.hd type Fault), read directly off the returned value,
never recomputed from the function under test, so this is not a circular oracle.

Run directly:
  cd python && uv run --package honest-alerts \
    python honest-alerts/conformance/laws_is_terminated.py
"""

from honest_alerts import is_terminated


# --- one flat-record builder over a table of field names; no default kwargs -------------------
#
# The honest-code finding this fragment fixes: the old `_actor` and `_event` helpers were two
# shape-identical flat builders differing only in their field words. An earlier collapse added
# `_flat` but KEPT `_actor` and `_event` as one-line wrappers that only forwarded a fixed shape
# name -- so two shape-identical functions still remained. Those wrappers are DROPPED here: `_flat`
# is the only flat-record builder, and every call site passes its shape name ("actor" / "event")
# explicitly. The builder itself holds no shape; each distinct shape is a named field tuple below.

_FIELDS = {
    "actor": ("type", "id", "tenant_id"),          # a flat ActorRef (honest-alerts.hd type ActorRef)
    "event": ("event_type", "timestamp", "payload"),  # a flat honest-observe event
}


def _flat(shape, *values):
    """Build one flat record of the named `shape` by zipping its declared field names (from _FIELDS)
    to the values passed at the call site. One function over a table of field names, so an ActorRef
    and an honest-observe event do not need two shape-identical builders. Every field is passed
    explicitly; an id, tenant_id or any absent field is written as None at the call site, never
    defaulted. A value count that does not match the shape's field count is a test authoring bug and
    is surfaced loudly rather than silently truncated."""
    fields = _FIELDS[shape]
    if len(values) != len(fields):
        raise AssertionError(
            f"_flat({shape!r}) expects {len(fields)} values {fields}, got {len(values)}: {values!r}"
        )
    return dict(zip(fields, values))


def _termination(condition, ttl_seconds, event_type, event_filter):
    """A TerminationSpec (honest-alerts.hd type TerminationSpec): a field that does not apply to the
    chosen condition is NOTHING (None), written out explicitly at the call site, never absent and
    never defaulted. This shape carries values of several kinds (a str, an int-or-None, a dict-or-
    None) rather than three interchangeable scalars, so it is its own builder, not a _flat row."""
    return {
        "condition": condition,
        "ttl_seconds": ttl_seconds,
        "event_type": event_type,
        "event_filter": event_filter,
    }


def _message(message_id, recipient, sent_at, termination, ack_scope):
    """A Message record (honest-alerts.hd type Message); only the fields is_terminated reads are
    varied per case (message_id, recipient, sent_at, termination, ack_scope). The rest are held at
    well-formed constants so each case still states its input in full."""
    return {
        "message_id": message_id,
        "message_type": "order.placed",
        "message_version": "v1",
        "sender": _flat("actor", "framework", None, None),
        "recipient": recipient,
        "channel": None,
        "subject_label_id": "subject.order_placed",
        "body_label_id": None,
        "payload": {},
        "dom_surface": None,
        "dom_target": None,
        "reply_required": False,
        "reply_options": None,
        "resume_token": None,
        "termination": termination,
        "ack_scope": ack_scope,
        "sent_at": sent_at,
    }


def _sent(msg):
    """The alert.sent honest-observe event carrying a message (its payload is the Message)."""
    return _flat("event", "alert.sent", msg["sent_at"], msg)


def _ack(message_id, acknowledged_at, actor, session):
    """An alert.acknowledged honest-observe event, its payload the AckPayload build_ack_event emits
    (honest-alerts.hd type AckPayload): message_id, the acknowledging actor (an ActorRef under the
    key `actor`), the acking session (SessionId or NOTHING under the key `session`), acknowledged_at,
    reply_payload. Every field is passed at the call site; actor or session of NOTHING is None."""
    return _flat("event", "alert.acknowledged", acknowledged_at, {
        "message_id": message_id,
        "actor": actor,
        "acknowledged_at": acknowledged_at,
        "reply_payload": {},
        "session": session,
    })


# The actor whose mailbox is being computed: the recipient user u1.
_RECIP = _flat("actor", "user", "u1", None)
# A different, non-recipient actor.
_OTHER = _flat("actor", "user", "u2", None)
# A broadcast message's recipient: every active DOM session (id NOTHING).
_ALL_DOM = _flat("actor", "dom", None, None)

# ---- Messages, one per termination condition / ack_scope under test ----

_TTL = _message("m_ttl", _RECIP, 1000, _termination("ttl", 10, None, None), "actor")
_EVENT = _message("m_ev", _RECIP, 1000,
                  _termination("event", None, "system.maintenance_completed", None), "actor")
_EVENT_FILTERED = _message("m_evf", _RECIP, 1000,
                           _termination("event", None, "job.finished", {"job_id": "j9"}), "actor")
_NEVER = _message("m_never", _RECIP, 1000, _termination("never", None, None, None), "actor")
_ACK_SESSION = _message("m_ses", _RECIP, 1000,
                        _termination("acknowledged", None, None, None), "session")
_ACK_ACTOR = _message("m_act", _RECIP, 1000,
                      _termination("acknowledged", None, None, None), "actor")
_ACK_BROADCAST = _message("m_bc", _ALL_DOM, 1000,
                          _termination("acknowledged", None, None, None), "broadcast")
# A message whose ack_scope is a value the scope_terminated table does not carry: a program bug,
# reaching the dispatch's no-match row.
_ACK_UNKNOWN = _message("m_unk", _RECIP, 1000,
                        _termination("acknowledged", None, None, None), "everywhere")


# Each case states its Message, the viewer, at_time, the event slice, viewing_session, and the exact
# bool the scenario fixes. The acknowledged cases carry their own alert.acknowledged events in the
# slice alongside the message's alert.sent event. "expect" is a literal bool; the one no-match case
# is checked separately as a Fault.
_CASES = [
    # ---- ttl: terminated when at_time is PAST sent_at + ttl_seconds (the edge is still live) ----
    {"msg": _TTL, "actor_ref": _RECIP, "at_time": 1005, "events": [_sent(_TTL)],
     "viewing_session": "s1", "expect": False},   # before the edge
    {"msg": _TTL, "actor_ref": _RECIP, "at_time": 1010, "events": [_sent(_TTL)],
     "viewing_session": "s1", "expect": False},   # exactly at the edge, still live
    {"msg": _TTL, "actor_ref": _RECIP, "at_time": 1011, "events": [_sent(_TTL)],
     "viewing_session": "s1", "expect": True},    # one second past the edge, terminated

    # ---- event: terminated when a matching event at or after sent_at appears ----
    {"msg": _EVENT, "actor_ref": _RECIP, "at_time": 2000, "events": [_sent(_EVENT)],
     "viewing_session": "s1", "expect": False},   # no terminating event yet
    {"msg": _EVENT, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_EVENT),
                _flat("event", "system.maintenance_completed", 1000, {})],
     "viewing_session": "s1", "expect": True},    # terminating event at sent_at
    {"msg": _EVENT, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_EVENT),
                _flat("event", "system.maintenance_completed", 1500, {})],
     "viewing_session": "s1", "expect": True},    # terminating event after sent_at
    {"msg": _EVENT, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_EVENT),
                _flat("event", "system.maintenance_completed", 900, {})],
     "viewing_session": "s1", "expect": False},   # event before sent_at does not count

    # event with a payload filter: a match terminates, a miss does not
    {"msg": _EVENT_FILTERED, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_EVENT_FILTERED),
                _flat("event", "job.finished", 1500, {"job_id": "j9"})],
     "viewing_session": "s1", "expect": True},
    {"msg": _EVENT_FILTERED, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_EVENT_FILTERED),
                _flat("event", "job.finished", 1500, {"job_id": "j0"})],
     "viewing_session": "s1", "expect": False},

    # ---- never: never terminated, even far in the future ----
    {"msg": _NEVER, "actor_ref": _RECIP, "at_time": 9_999_999, "events": [_sent(_NEVER)],
     "viewing_session": "s1", "expect": False},

    # ---- acknowledged / session scope ----
    {"msg": _ACK_SESSION, "actor_ref": _RECIP, "at_time": 2000, "events": [_sent(_ACK_SESSION)],
     "viewing_session": "s1", "expect": False},   # no ack yet
    {"msg": _ACK_SESSION, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_ACK_SESSION), _ack("m_ses", 1500, _RECIP, "s1")],
     "viewing_session": "s1", "expect": True},    # this viewing session acked
    {"msg": _ACK_SESSION, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_ACK_SESSION), _ack("m_ses", 1500, _RECIP, "s2")],
     "viewing_session": "s1", "expect": False},   # a different session acked, still live here
    {"msg": _ACK_SESSION, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_ACK_SESSION), _ack("m_ses", 1500, _RECIP, "s1")],
     "viewing_session": None, "expect": False},   # the waiter view (NOTHING) never matches a session ack

    # ---- acknowledged / actor scope ----
    {"msg": _ACK_ACTOR, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_ACK_ACTOR), _ack("m_act", 1500, _RECIP, "s9")],
     "viewing_session": "s1", "expect": True},    # the recipient actor acked (any session) -> every viewer
    {"msg": _ACK_ACTOR, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_ACK_ACTOR), _ack("m_act", 1500, _RECIP, "s9")],
     "viewing_session": None, "expect": True},    # terminates for the waiter too (viewing_session ignored)
    {"msg": _ACK_ACTOR, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_ACK_ACTOR), _ack("m_act", 1500, _OTHER, "s9")],
     "viewing_session": "s1", "expect": False},   # an ack from a non-recipient does NOT terminate

    # ---- acknowledged / broadcast scope ----
    {"msg": _ACK_BROADCAST, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_ACK_BROADCAST), _ack("m_bc", 1500, _flat("actor", "user", "whoever", None), "sx")],
     "viewing_session": "s1", "expect": True},    # any recipient acked -> every viewer
    {"msg": _ACK_BROADCAST, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_ACK_BROADCAST), _ack("m_bc", 1500, _flat("actor", "user", "whoever", None), "sx")],
     "viewing_session": None, "expect": True},    # terminates for the waiter too
    {"msg": _ACK_BROADCAST, "actor_ref": _RECIP, "at_time": 2000, "events": [_sent(_ACK_BROADCAST)],
     "viewing_session": "s1", "expect": False},   # the ack slice for this message is empty: not terminated
    # a broadcast ack addressed to a DIFFERENT message does not count (slice for THIS message empty)
    {"msg": _ACK_BROADCAST, "actor_ref": _RECIP, "at_time": 2000,
     "events": [_sent(_ACK_BROADCAST),
                _ack("some_other_message", 1500, _flat("actor", "user", "whoever", None), "sx")],
     "viewing_session": "s1", "expect": False},
]

# The no-match row: an ack_scope the scope_terminated table does not carry -> a server Fault, not a
# bool (code unknown_ack_scope, category server; spec section 6b).
_FAULT_CASE = {
    "msg": _ACK_UNKNOWN, "actor_ref": _RECIP, "at_time": 2000,
    "events": [_sent(_ACK_UNKNOWN), _ack("m_unk", 1500, _RECIP, "s1")],
    "viewing_session": "s1",
}


_SENTINEL = object()


def _is_fault(value):
    """True when value is the honest-alerts Fault arm: a record carrying the reserved is_err tag set
    true (honest-alerts.hd type Fault). Read directly off the returned value; nothing is recomputed
    from is_terminated, so this is not a circular oracle."""
    if isinstance(value, dict):
        return value.get("is_err") is True
    return getattr(value, "is_err", None) is True


def _field(value, name):
    """Read one field off a returned Fault, dict or record."""
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _call(case):
    """Call the real is_terminated once with the declared 5-param signature
    (msg, actor_ref, at_time, events, viewing_session). A call that does not match that signature --
    the declared behavior being absent -- is captured and returned as a sentinel so the probe records
    it as a fault rather than crashing, keeping faults-as-data. A correct implementation returns a
    bool or a Fault."""
    try:
        return is_terminated(
            case["msg"],
            case["actor_ref"],
            case["at_time"],
            case["events"],
            case["viewing_session"],
        )
    except TypeError as exc:
        return (_SENTINEL, f"call did not match the declared signature: {exc}")


def _describes_no_match(message, arrived, accepted):
    """Check the authored value, accepted alternatives and the reason the dispatch refused it."""
    if not isinstance(message, str):
        return False
    text = message.casefold()
    no_match = any(
        phrase in text
        for phrase in ("matched no", "no branch match", "no matching branch", "does not match any branch")
    )
    return no_match and arrived in text and all(value in text for value in accepted)


def probe_is_terminated():
    """is_terminated decides, for the viewer the read is taken for, whether one message has
    terminated at at_time: ttl past its edge, a matching event at or after sent_at, never for never,
    and the acknowledged condition dispatched on ack_scope (session equals viewing_session with the
    waiter never matching; actor on an ack by the recipient actor; broadcast on an ack by any
    recipient; an ack from a non-recipient terminating neither actor- nor broadcast-scoped), with
    the dispatch's no-match row returning a server Fault via alerts_fault (unknown_ack_scope)."""
    bad = []
    for case in _CASES:
        got = _call(case)
        if isinstance(got, tuple) and got and got[0] is _SENTINEL:
            bad.append(
                f"is_terminated(msg={case['msg']['message_id']!r}, "
                f"ack_scope={case['msg']['ack_scope']!r}) {got[1]}"
            )
            continue
        if got != case["expect"]:
            bad.append(
                f"is_terminated(msg={case['msg']['message_id']!r}, "
                f"ack_scope={case['msg']['ack_scope']!r}, "
                f"condition={case['msg']['termination']['condition']!r}, "
                f"at_time={case['at_time']}, viewing_session={case['viewing_session']!r}) "
                f"-> {got!r}, expected {case['expect']!r}"
            )

    # The no-match row: a value the scope_terminated table does not carry is a program bug, so
    # is_terminated returns a server Fault (code unknown_ack_scope, category server), never a bool.
    got = _call(_FAULT_CASE)
    if isinstance(got, tuple) and got and got[0] is _SENTINEL:
        bad.append(f"is_terminated(ack_scope='everywhere') {got[1]}")
        return bad
    if not _is_fault(got):
        bad.append(
            f"is_terminated(ack_scope='everywhere') -> {got!r}, expected a server Fault arm "
            f"(is_err true, code unknown_ack_scope, category server) for the dispatch no-match row"
        )
    else:
        code = _field(got, "code")
        category = _field(got, "category")
        if code != "unknown_ack_scope":
            bad.append(f"is_terminated no-match Fault code -> {code!r}, expected 'unknown_ack_scope'")
        if category != "server":
            bad.append(f"is_terminated no-match Fault category -> {category!r}, expected 'server'")
        detail = _field(got, "detail")
        accepted = detail.get("accepted") if isinstance(detail, dict) else None
        if not isinstance(accepted, (list, tuple, set)) or sorted(accepted) != ["actor", "broadcast", "session"]:
            bad.append(f"unknown_ack_scope must carry the declared scope alternatives in detail.accepted: {detail!r}")
        if not isinstance(detail, dict) or detail.get("arrived") != "everywhere":
            bad.append(f"unknown_ack_scope must carry 'everywhere' in detail.arrived: {detail!r}")
        message_text = _field(got, "message")
        if not _describes_no_match(message_text, "everywhere", ["actor", "broadcast", "session"]):
            bad.append(f"unknown_ack_scope must explain the unmatched scope and name every accepted scope: {message_text!r}")
    return bad


def run():
    bad = probe_is_terminated()
    for line in bad:
        print("FAIL:", line)
    if not bad:
        print("laws_is_terminated: ok")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(run())

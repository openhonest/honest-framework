"""honest-alerts conformance laws: the mailbox projection and message termination (section 4).

The portable surface is value cases in suite.json (checked by value-check.py). These laws pin the same
pure functions for the per-module gate and drive 100% coverage: recipient matching in all its branches,
every termination condition (ttl at and past its edge, acknowledgment in each scope, event with and
without a filter, never), and the mailbox projection's recipient, time-window, termination, and ordering
behaviour. Pure assertions: data in, data out. Time is epoch seconds.
"""

from honest_alerts import (
    ACK_SCOPES,
    ACTOR_TYPES,
    CHANNELS,
    DOM_SURFACES,
    LIFECYCLE_EVENTS,
    REPLY_STYLES,
    TERMINATION_CONDITIONS,
    advance,
    alert_lifecycle,
    delivery_plan,
    execute_deliveries,
    is_terminated,
    mailbox,
    matching_routes,
    message_type_matches,
    recipient_matches,
    supervise,
    validate_actor_ref,
    validate_alert_route,
    validate_channel_config,
    validate_escalation_rule,
    validate_message,
    validate_reply_option,
    validate_termination,
)


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
    expected = [
        "mailbox",
        "is_terminated",
        "recipient_matches",
        "TERMINATION_CONDITIONS",
        "ACK_SCOPES",
        "ACTOR_TYPES",
        "validate_actor_ref",
        "DOM_SURFACES",
        "REPLY_STYLES",
        "CHANNELS",
        "validate_termination",
        "validate_reply_option",
        "validate_message",
        "validate_channel_config",
        "validate_escalation_rule",
        "validate_alert_route",
        "message_type_matches",
        "matching_routes",
        "delivery_plan",
        "supervise",
        "execute_deliveries",
        "alert_lifecycle",
        "LIFECYCLE_EVENTS",
        "advance",
    ]
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
    if ACTOR_TYPES != frozenset(
        {
            "user", "role", "tenant", "admin", "anonymous",
            "chain", "state_machine", "job", "projection",
            "framework", "auth", "webhook_inbound",
            "dom", "email", "sms", "webhook_outbound", "slack", "teams",
        }
    ):
        bad.append(f"ACTOR_TYPES should be the declared human, process, system, and interface types: {ACTOR_TYPES}")
    if DOM_SURFACES != frozenset({"banner", "toast", "modal", "badge", "inline"}):
        bad.append(f"DOM_SURFACES should be the five declared surfaces: {DOM_SURFACES}")
    if REPLY_STYLES != frozenset({"primary", "secondary", "danger", "warning"}):
        bad.append(f"REPLY_STYLES should be the four declared styles: {REPLY_STYLES}")
    if CHANNELS != frozenset({"dom", "email", "sms", "webhook", "slack", "teams"}):
        bad.append(f"CHANNELS should be the full declared channel set: {CHANNELS}")
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


def _law_validate_actor_ref():
    bad = []
    if validate_actor_ref({"type": "user", "id": "u1"}) != {"ok": {"type": "user", "id": "u1"}}:
        bad.append("a declared actor type passes")
    if validate_actor_ref({"type": "dom"}) != {"ok": {"type": "dom"}}:
        bad.append("id and tenant_id are optional")
    ghost = validate_actor_ref({"type": "ghost"})
    if ghost != {"err": {"code": "invalid_actor_type", "message": "'ghost' is not a declared actor type", "category": "client", "detail": "ghost"}}:
        bad.append(f"an undeclared actor type is a full invalid_actor_type client fault: {ghost}")
    return bad


def _law_validate_termination():
    bad = []
    from honest_alerts.message import _TERMINATION_REQUIRED

    if set(_TERMINATION_REQUIRED) != TERMINATION_CONDITIONS:
        bad.append(f"_TERMINATION_REQUIRED must cover exactly the declared conditions: {set(_TERMINATION_REQUIRED)}")
    if validate_termination({"condition": "ttl", "ttl_seconds": 10}) != {"ok": {"condition": "ttl", "ttl_seconds": 10}}:
        bad.append("a ttl termination with ttl_seconds passes")
    if validate_termination({"condition": "acknowledged"}) != {"ok": {"condition": "acknowledged"}}:
        bad.append("an acknowledged termination needs no extra fields")
    if validate_termination({"condition": "never"}) != {"ok": {"condition": "never"}}:
        bad.append("a never termination needs no extra fields")
    if validate_termination({"condition": "event", "event_type": "x.done"}) != {"ok": {"condition": "event", "event_type": "x.done"}}:
        bad.append("an event termination with event_type passes")
    bogus = validate_termination({"condition": "bogus"})
    if bogus != {"err": {"code": "invalid_termination", "message": "'bogus' is not a declared termination condition", "category": "client", "detail": "bogus"}}:
        bad.append(f"an undeclared condition is a full invalid_termination fault: {bogus}")
    no_ttl = validate_termination({"condition": "ttl"})
    if no_ttl != {"err": {"code": "incomplete_termination", "message": "a 'ttl' termination is missing required fields: ['ttl_seconds']", "category": "client", "detail": ["ttl_seconds"]}}:
        bad.append(f"a ttl termination without ttl_seconds is a full incomplete_termination fault: {no_ttl}")
    no_event = validate_termination({"condition": "event"})
    if no_event != {"err": {"code": "incomplete_termination", "message": "a 'event' termination is missing required fields: ['event_type']", "category": "client", "detail": ["event_type"]}}:
        bad.append(f"an event termination without event_type is a full incomplete_termination fault: {no_event}")
    return bad


def _law_validate_reply_option():
    bad = []
    if validate_reply_option({"option_id": "approve", "label_id": "alerts.approve"}) != {"ok": {"option_id": "approve", "label_id": "alerts.approve"}}:
        bad.append("a reply option with option_id and label_id passes")
    styled = {"option_id": "reject", "label_id": "alerts.reject", "style": "danger"}
    if validate_reply_option(styled) != {"ok": styled}:
        bad.append("a declared style passes")
    incomplete = validate_reply_option({"option_id": "approve"})
    if incomplete != {"err": {"code": "incomplete_reply_option", "message": "a reply option is missing required fields: ['label_id']", "category": "client", "detail": ["label_id"]}}:
        bad.append(f"a reply option missing label_id is a full incomplete_reply_option fault: {incomplete}")
    bad_style = validate_reply_option({"option_id": "a", "label_id": "b", "style": "neon"})
    if bad_style != {"err": {"code": "invalid_reply_style", "message": "'neon' is not a declared reply style", "category": "client", "detail": "neon"}}:
        bad.append(f"an undeclared style is a full invalid_reply_style fault: {bad_style}")
    return bad


def _valid_message(**overrides):
    """A minimal valid message; overrides adjust one field for the negative cases."""
    message = {
        "message_id": "m1",
        "message_type": "order.placed",
        "message_version": "1",
        "sender": {"type": "framework"},
        "recipient": {"type": "user", "id": "u1"},
        "subject_label_id": "alerts.order_placed",
        "payload": {},
        "reply_required": False,
        "termination": {"condition": "ttl", "ttl_seconds": 10},
        "ack_scope": "session",
        "sent_at": 1000,
    }
    message.update(overrides)
    return message


def _law_validate_message():
    bad = []
    ok_msg = _valid_message()
    if validate_message(ok_msg) != {"ok": ok_msg}:
        bad.append(f"a complete, well-formed message passes: {validate_message(ok_msg)}")
    # optional fields present and valid
    rich = _valid_message(dom_surface="toast", reply_options=[{"option_id": "ok", "label_id": "l"}])
    if validate_message(rich) != {"ok": rich}:
        bad.append(f"valid optional dom_surface and reply_options pass: {validate_message(rich)}")
    # missing required field
    incomplete = _valid_message()
    del incomplete["sent_at"]
    miss = validate_message(incomplete)
    if miss != {"err": {"code": "incomplete_message", "message": "message is missing required fields: ['sent_at']", "category": "client", "detail": ["sent_at"]}}:
        bad.append(f"a message missing a required field is a full incomplete_message fault: {miss}")
    # invalid sender / recipient propagate the actor fault
    bad_sender = validate_message(_valid_message(sender={"type": "ghost"}))
    if bad_sender.get("err", {}).get("code") != "invalid_actor_type":
        bad.append(f"an invalid sender propagates invalid_actor_type: {bad_sender}")
    bad_recipient = validate_message(_valid_message(recipient={"type": "ghost"}))
    if bad_recipient.get("err", {}).get("code") != "invalid_actor_type":
        bad.append(f"an invalid recipient propagates invalid_actor_type: {bad_recipient}")
    # invalid termination propagates
    bad_term = validate_message(_valid_message(termination={"condition": "bogus"}))
    if bad_term.get("err", {}).get("code") != "invalid_termination":
        bad.append(f"an invalid termination propagates invalid_termination: {bad_term}")
    # invalid ack_scope
    bad_scope = validate_message(_valid_message(ack_scope="everywhere"))
    if bad_scope != {"err": {"code": "invalid_ack_scope", "message": "'everywhere' is not a declared ack scope", "category": "client", "detail": "everywhere"}}:
        bad.append(f"an undeclared ack_scope is a full invalid_ack_scope fault: {bad_scope}")
    # invalid dom_surface
    bad_surface = validate_message(_valid_message(dom_surface="popover"))
    if bad_surface != {"err": {"code": "invalid_dom_surface", "message": "'popover' is not a declared DOM surface", "category": "client", "detail": "popover"}}:
        bad.append(f"an undeclared dom_surface is a full invalid_dom_surface fault: {bad_surface}")
    # invalid reply option propagates
    bad_reply = validate_message(_valid_message(reply_options=[{"option_id": "ok"}]))
    if bad_reply.get("err", {}).get("code") != "incomplete_reply_option":
        bad.append(f"an invalid reply option propagates incomplete_reply_option: {bad_reply}")
    # optional preferred channel, valid and invalid
    with_channel = _valid_message(channel="email")
    if validate_message(with_channel) != {"ok": with_channel}:
        bad.append(f"a declared preferred channel passes: {validate_message(with_channel)}")
    bad_channel = validate_message(_valid_message(channel="carrier_pigeon"))
    if bad_channel != {"err": {"code": "invalid_channel", "message": "'carrier_pigeon' is not a declared channel", "category": "client", "detail": "carrier_pigeon"}}:
        bad.append(f"an undeclared channel is a full invalid_channel fault: {bad_channel}")
    return bad


def _valid_channel_config(**overrides):
    config = {"channel": "dom"}
    config.update(overrides)
    return config


def _law_validate_channel_config():
    bad = []
    ok_c = _valid_channel_config()
    if validate_channel_config(ok_c) != {"ok": ok_c}:
        bad.append(f"a channel config with a declared channel passes: {validate_channel_config(ok_c)}")
    with_recipient = _valid_channel_config(channel="email", recipient_spec={"type": "role", "id": "admin"})
    if validate_channel_config(with_recipient) != {"ok": with_recipient}:
        bad.append(f"a valid recipient_spec passes: {validate_channel_config(with_recipient)}")
    miss = validate_channel_config({})
    if miss != {"err": {"code": "incomplete_channel_config", "message": "a channel config is missing required fields: ['channel']", "category": "client", "detail": ["channel"]}}:
        bad.append(f"a channel config missing channel is a full incomplete_channel_config fault: {miss}")
    bad_channel = validate_channel_config({"channel": "pigeon"})
    if bad_channel != {"err": {"code": "invalid_channel", "message": "'pigeon' is not a declared channel", "category": "client", "detail": "pigeon"}}:
        bad.append(f"an undeclared channel is a full invalid_channel fault: {bad_channel}")
    bad_recipient = validate_channel_config(_valid_channel_config(recipient_spec={"type": "ghost"}))
    if bad_recipient.get("err", {}).get("code") != "invalid_actor_type":
        bad.append(f"an invalid recipient_spec propagates invalid_actor_type: {bad_recipient}")
    return bad


def _valid_escalation(**overrides):
    rule = {"ttl_seconds": 86400, "escalate_to": {"type": "role", "id": "admin"}}
    rule.update(overrides)
    return rule


def _law_validate_escalation_rule():
    bad = []
    ok_e = _valid_escalation()
    if validate_escalation_rule(ok_e) != {"ok": ok_e}:
        bad.append(f"a complete escalation rule passes: {validate_escalation_rule(ok_e)}")
    with_channel = _valid_escalation(escalate_channel="email")
    if validate_escalation_rule(with_channel) != {"ok": with_channel}:
        bad.append(f"a valid escalate_channel passes: {validate_escalation_rule(with_channel)}")
    no_ttl = validate_escalation_rule({"escalate_to": {"type": "role", "id": "admin"}})
    if no_ttl != {"err": {"code": "incomplete_escalation", "message": "an escalation rule is missing required fields: ['ttl_seconds']", "category": "client", "detail": ["ttl_seconds"]}}:
        bad.append(f"an escalation rule missing ttl_seconds is a full incomplete_escalation fault: {no_ttl}")
    no_target = validate_escalation_rule({"ttl_seconds": 10})
    if no_target != {"err": {"code": "incomplete_escalation", "message": "an escalation rule is missing required fields: ['escalate_to']", "category": "client", "detail": ["escalate_to"]}}:
        bad.append(f"an escalation rule missing escalate_to is a full incomplete_escalation fault: {no_target}")
    bad_target = validate_escalation_rule(_valid_escalation(escalate_to={"type": "ghost"}))
    if bad_target.get("err", {}).get("code") != "invalid_actor_type":
        bad.append(f"an invalid escalate_to propagates invalid_actor_type: {bad_target}")
    bad_channel = validate_escalation_rule(_valid_escalation(escalate_channel="pigeon"))
    if bad_channel != {"err": {"code": "invalid_channel", "message": "'pigeon' is not a declared channel", "category": "client", "detail": "pigeon"}}:
        bad.append(f"an undeclared escalate_channel is a full invalid_channel fault: {bad_channel}")
    return bad


def _valid_route(**overrides):
    route = {"route_id": "r1", "message_type": "order.placed", "channels": [{"channel": "dom"}], "priority": 1}
    route.update(overrides)
    return route


def _law_validate_alert_route():
    bad = []
    ok_r = _valid_route()
    if validate_alert_route(ok_r) != {"ok": ok_r}:
        bad.append(f"a complete route passes: {validate_alert_route(ok_r)}")
    rich = _valid_route(sender_type="framework", escalation={"ttl_seconds": 10, "escalate_to": {"type": "role", "id": "admin"}})
    if validate_alert_route(rich) != {"ok": rich}:
        bad.append(f"a valid sender_type and escalation pass: {validate_alert_route(rich)}")
    miss = validate_alert_route({})
    if miss != {"err": {"code": "incomplete_route", "message": "an alert route is missing required fields: ['route_id', 'message_type', 'channels', 'priority']", "category": "client", "detail": ["route_id", "message_type", "channels", "priority"]}}:
        bad.append(f"a route missing required fields is a full incomplete_route fault: {miss}")
    bad_sender = validate_alert_route(_valid_route(sender_type="ghost"))
    if bad_sender != {"err": {"code": "invalid_actor_type", "message": "'ghost' is not a declared actor type", "category": "client", "detail": "ghost"}}:
        bad.append(f"an undeclared sender_type is a full invalid_actor_type fault: {bad_sender}")
    bad_channel = validate_alert_route(_valid_route(channels=[{"channel": "pigeon"}]))
    if bad_channel.get("err", {}).get("code") != "invalid_channel":
        bad.append(f"an invalid channel config propagates invalid_channel: {bad_channel}")
    bad_escalation = validate_alert_route(_valid_route(escalation={"ttl_seconds": 10}))
    if bad_escalation.get("err", {}).get("code") != "incomplete_escalation":
        bad.append(f"an invalid escalation propagates incomplete_escalation: {bad_escalation}")
    return bad


import asyncio


class _Runtime:
    """A stand-in supervisor runtime (sections 6.1-6.2): canned now and delivery outcome, a recorded
    pending queue, and captured inserts, emits, and marks so the boundary laws can assert what the
    supervisor did through it. Conformance code is not linted, so a class here is fine; the supervisor
    source stays classless, and its I/O reaches the world only through this injected object."""

    def __init__(self, now=1000, deliver_ok=True, pending=None):
        self._now = now
        self._deliver_ok = deliver_ok
        self._pending = pending if pending is not None else []
        self.inserted = []
        self.emitted = []
        self.marked = []

    def now(self):
        return self._now

    async def insert(self, delivery):
        self.inserted.append(delivery)
        return {"ok": delivery}

    async def emit(self, event_type, aggregate_id, payload):
        self.emitted.append((event_type, aggregate_id, payload))
        return {"ok": {"event_id": "e1"}}

    async def pending(self):
        return self._pending

    async def deliver(self, delivery):
        return {"ok": delivery} if self._deliver_ok else {"err": {"code": "channel_down"}}

    async def mark(self, delivery, status):
        self.marked.append((delivery["message_id"], status))
        return {"ok": None}


def _law_message_type_matches():
    bad = []
    if message_type_matches("system.maintenance_notice", "system.maintenance_notice") is not True:
        bad.append("an exact pattern matches its message type")
    if message_type_matches("order.placed", "order.shipped") is not False:
        bad.append("a non-matching exact pattern does not match")
    if message_type_matches("order", "order.placed") is not False:
        bad.append("a non-wildcard pattern requires an exact match, not a prefix")
    if message_type_matches("system.*", "system.maintenance_notice") is not True:
        bad.append("a wildcard pattern matches any type in its namespace")
    if message_type_matches("system.*", "auth.login") is not False:
        bad.append("a wildcard pattern does not match another namespace")
    if message_type_matches("system.*", "system") is not False:
        bad.append("a wildcard 'system.*' does not match the bare 'system' (the dot is required)")
    return bad


def _law_matching_routes():
    bad = []
    message = {"message_type": "system.maintenance_notice", "sender": {"type": "framework"}}
    r_wild = {"route_id": "r_wild", "message_type": "system.*", "priority": 2}
    r_exact = {"route_id": "r_exact", "message_type": "system.maintenance_notice", "priority": 1}
    r_other = {"route_id": "r_other", "message_type": "order.placed", "priority": 1}
    r_sender = {"route_id": "r_sender", "message_type": "system.*", "sender_type": "auth", "priority": 3}
    ids = [r["route_id"] for r in matching_routes([r_wild, r_exact, r_other, r_sender], message)]
    if ids != ["r_exact", "r_wild"]:
        bad.append(f"matching_routes keeps matches, priority ascending, dropping other types and non-matching senders: {ids}")
    sender_msg = {"message_type": "system.x", "sender": {"type": "auth"}}
    if [r["route_id"] for r in matching_routes([r_sender], sender_msg)] != ["r_sender"]:
        bad.append("a route with a sender_type matches when the sender type equals it")
    return bad


def _law_delivery_plan():
    bad = []
    message = {"message_id": "m1", "recipient": {"type": "user", "id": "u1"}}
    routes = [
        {"route_id": "r1", "channels": [{"channel": "dom"}, {"channel": "email", "delay_seconds": 300, "recipient_spec": {"type": "role", "id": "admin"}}]},
    ]
    plan = delivery_plan(message, routes, 1000)
    if plan != [
        {"message_id": "m1", "route_id": "r1", "channel": "dom", "recipient": {"type": "user", "id": "u1"}, "deliver_at": 1000, "status": "pending"},
        {"message_id": "m1", "route_id": "r1", "channel": "email", "recipient": {"type": "role", "id": "admin"}, "deliver_at": 1300, "status": "pending"},
    ]:
        bad.append(f"delivery_plan builds one pending record per channel, resolving recipient and deliver_at (now + delay): {plan}")
    return bad


def _law_supervise():
    bad = []
    message = {"message_id": "m1", "message_type": "order.placed", "sender": {"type": "framework"}, "recipient": {"type": "user", "id": "u1"}}
    route = {"route_id": "r1", "message_type": "order.placed", "channels": [{"channel": "dom"}], "priority": 1}
    rt = _Runtime(now=1000)
    result = asyncio.run(supervise(message, [route], rt))
    if result != {"ok": {"delivered": 1}}:
        bad.append(f"supervise reports the number of deliveries created: {result}")
    if [d["channel"] for d in rt.inserted] != ["dom"]:
        bad.append(f"supervise inserts a delivery record per channel: {rt.inserted}")
    if rt.emitted != [("alert.sent", "m1", message)]:
        bad.append(f"supervise emits alert.sent with the message payload: {rt.emitted}")
    rt2 = _Runtime()
    empty = asyncio.run(supervise(message, [], rt2))
    if empty != {"ok": {"delivered": 0}}:
        bad.append(f"supervise with no matching route delivers nothing: {empty}")
    if rt2.inserted != []:
        bad.append(f"supervise with no matching route inserts nothing: {rt2.inserted}")
    if rt2.emitted != [("alert.no_route", "m1", {"message_type": "order.placed"})]:
        bad.append(f"supervise with no matching route emits an alert.no_route warning: {rt2.emitted}")
    return bad


def _law_execute_deliveries():
    bad = []
    d1 = {"message_id": "m1", "channel": "dom"}
    d2 = {"message_id": "m2", "channel": "email"}
    rt = _Runtime(deliver_ok=True, pending=[d1, d2])
    result = asyncio.run(execute_deliveries(rt))
    if result != {"ok": {"executed": 2}}:
        bad.append(f"execute_deliveries reports how many pending records it processed: {result}")
    if rt.marked != [("m1", "delivered"), ("m2", "delivered")]:
        bad.append(f"a successful delivery is marked delivered: {rt.marked}")
    if rt.emitted != [("alert.delivered", "m1", d1), ("alert.delivered", "m2", d2)]:
        bad.append(f"a successful delivery emits alert.delivered: {rt.emitted}")
    rt2 = _Runtime(deliver_ok=False, pending=[d1])
    asyncio.run(execute_deliveries(rt2))
    if rt2.marked != [("m1", "failed")]:
        bad.append(f"a failed delivery is marked failed: {rt2.marked}")
    if rt2.emitted != [("alert.delivery_failed", "m1", d1)]:
        bad.append(f"a failed delivery emits alert.delivery_failed: {rt2.emitted}")
    if asyncio.run(execute_deliveries(_Runtime(pending=[]))) != {"ok": {"executed": 0}}:
        bad.append("execute_deliveries with nothing pending processes nothing")
    return bad


def _law_lifecycle_machine():
    bad = []
    if alert_lifecycle["states"] != frozenset(
        {"created", "delivered", "read", "acknowledged", "actioned", "escalated", "expired", "failed"}
    ):
        bad.append(f"alert_lifecycle has the eight declared states: {alert_lifecycle['states']}")
    if alert_lifecycle["events"] != frozenset({"deliver", "read", "acknowledge", "action", "escalate", "expire", "fail"}):
        bad.append(f"alert_lifecycle has the seven declared events: {alert_lifecycle['events']}")
    if alert_lifecycle["initial"] != "created":
        bad.append(f"alert_lifecycle starts at created: {alert_lifecycle['initial']}")
    if sorted(alert_lifecycle["terminal"]) != ["acknowledged", "actioned", "expired", "failed"]:
        bad.append(f"alert_lifecycle terminal states are the four end states: {alert_lifecycle['terminal']}")
    expected = {
        ("created", "deliver"): "delivered",
        ("created", "fail"): "failed",
        ("created", "expire"): "expired",
        ("delivered", "read"): "read",
        ("delivered", "acknowledge"): "acknowledged",
        ("delivered", "action"): "actioned",
        ("delivered", "escalate"): "escalated",
        ("delivered", "expire"): "expired",
        ("read", "acknowledge"): "acknowledged",
        ("read", "action"): "actioned",
        ("read", "escalate"): "escalated",
        ("read", "expire"): "expired",
        ("escalated", "acknowledge"): "acknowledged",
        ("escalated", "action"): "actioned",
        ("escalated", "expire"): "expired",
    }
    if alert_lifecycle["transitions"] != expected:
        bad.append(f"alert_lifecycle transition table drifted from section 7: {alert_lifecycle['transitions']}")
    return bad


def _law_lifecycle_events():
    bad = []
    if LIFECYCLE_EVENTS != {
        "deliver": "alert.delivered",
        "read": "alert.read",
        "acknowledge": "alert.acknowledged",
        "action": "alert.actioned",
        "escalate": "alert.escalated",
        "expire": "alert.expired",
        "fail": "alert.failed",
    }:
        bad.append(f"LIFECYCLE_EVENTS maps each lifecycle event to its honest-observe event type: {LIFECYCLE_EVENTS}")
    if set(LIFECYCLE_EVENTS) != alert_lifecycle["events"]:
        bad.append(f"LIFECYCLE_EVENTS covers exactly the lifecycle events: {set(LIFECYCLE_EVENTS)}")
    return bad


def _law_advance():
    bad = []
    if advance("created", "deliver") != {"ok": {"state": "delivered", "event": "alert.delivered"}}:
        bad.append(f"advance applies the transition and returns the observe event: {advance('created', 'deliver')}")
    if advance("delivered", "acknowledge") != {"ok": {"state": "acknowledged", "event": "alert.acknowledged"}}:
        bad.append(f"advance delivered/acknowledge -> acknowledged and alert.acknowledged: {advance('delivered', 'acknowledge')}")
    if advance("escalated", "expire") != {"ok": {"state": "expired", "event": "alert.expired"}}:
        bad.append(f"advance escalated/expire -> expired and alert.expired: {advance('escalated', 'expire')}")
    unknown = advance("created", "teleport")
    if unknown.get("err", {}).get("code") != "invalid_event":
        bad.append(f"an undeclared event is invalid_event: {unknown}")
    no_trans = advance("created", "read")
    if no_trans.get("err", {}).get("code") != "no_transition":
        bad.append(f"an event with no transition from the current state is no_transition: {no_trans}")
    terminal = advance("acknowledged", "read")
    if terminal.get("err", {}).get("code") != "no_transition":
        bad.append(f"a terminal state has no outgoing transition: {terminal}")
    return bad


_LAWS = {
    "exports": _law_exports,
    "vocabularies": _law_vocabularies,
    "lifecycle_machine": _law_lifecycle_machine,
    "lifecycle_events": _law_lifecycle_events,
    "advance": _law_advance,
    "recipient_matches": _law_recipient_matches,
    "terminated_ttl": _law_terminated_ttl,
    "terminated_acknowledged": _law_terminated_acknowledged,
    "terminated_event": _law_terminated_event,
    "terminated_never": _law_terminated_never,
    "mailbox": _law_mailbox,
    "validate_actor_ref": _law_validate_actor_ref,
    "validate_termination": _law_validate_termination,
    "validate_reply_option": _law_validate_reply_option,
    "validate_message": _law_validate_message,
    "validate_channel_config": _law_validate_channel_config,
    "validate_escalation_rule": _law_validate_escalation_rule,
    "validate_alert_route": _law_validate_alert_route,
    "message_type_matches": _law_message_type_matches,
    "matching_routes": _law_matching_routes,
    "delivery_plan": _law_delivery_plan,
    "supervise": _law_supervise,
    "execute_deliveries": _law_execute_deliveries,
}


def run():
    violations = {name: law() for name, law in _LAWS.items()}
    failed = {name: msgs for name, msgs in violations.items() if msgs}
    passed = len(_LAWS) - len(failed)
    for name, msgs in failed.items():
        print(f"FAIL HA-law [{name}]: {msgs}")
    print(f"HA laws: {passed} passed, {len(failed)} failed, {len(_LAWS)} total")
    return 0 if not failed else 1

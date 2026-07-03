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
    REPLY_STYLES,
    TERMINATION_CONDITIONS,
    is_terminated,
    mailbox,
    recipient_matches,
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


_LAWS = {
    "exports": _law_exports,
    "vocabularies": _law_vocabularies,
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
}


def run():
    violations = {name: law() for name, law in _LAWS.items()}
    failed = {name: msgs for name, msgs in violations.items() if msgs}
    passed = len(_LAWS) - len(failed)
    for name, msgs in failed.items():
        print(f"FAIL HA-law [{name}]: {msgs}")
    print(f"HA laws: {passed} passed, {len(failed)} failed, {len(_LAWS)} total")
    return 0 if not failed else 1

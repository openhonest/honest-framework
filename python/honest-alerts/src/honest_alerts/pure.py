"""The pure substrate: the constructors, the supervisor, the lifecycle transition and the mailbox
projection. Data in, data out, no world. Every column-0 function here is a declared .hd function;
helpers are lambdas or nested functions (the honest-observe precedent). The source carries no `if`
statement, ternary, or comprehension filter (HC-P001): a branch is a boolean key through _pick, and a
table read is the honest absent-tolerant _get, so a miss is a declared bounded case (P16), never a
value filed under a hit (HC-P019) and never a bare KeyError (HC-P020)."""

import re
import uuid
from calendar import monthrange
from datetime import date
from functools import reduce

from honest_alerts._util import _get, _pick
from honest_alerts.faults import alerts_fault


NOTHING = None


# --- build_registered_type -------------------------------------------------------------------------

# inherits: hd=python/honest-alerts/honest-alerts.hd::_is_dotted -> feature=specs/features/honest-alerts.feature::_is_dotted accepts only dotted names with nonempty components -> test=python/honest-alerts/conformance/laws_is_dotted.py::probe_is_dotted
# hd: _is_dotted
def _is_dotted(message_type):
    """Recognize two or more nonempty components separated by literal dots."""
    match message_type:
        case str():
            components = message_type.split(".")
            return len(components) >= 2 and all(components)
        case _:
            return False

# The two non-fault re-registration decisions, keyed on whether a stored record exists and, when it
# does, whether the arriving whole declaration equals it. Each arm is a thunk taking the arriving
# record and the stored one; the table closes the decision over its boolean key (P01, P16).
_REGISTER_DECISION = {
    "first": lambda arriving, stored: {"action": "write", "registered_type": arriving},
    "identical": lambda arriving, stored: {"action": "noop", "registered_type": stored},
}


# inherits: hd=python/honest-alerts/honest-alerts.hd::build_registered_type -> feature=specs/features/honest-alerts.feature::build_registered_type -> test=python/honest-alerts/conformance/laws_build_registered_type.py::probe_build_registered_type
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_registered_type -> feature=specs/features/honest-alerts.feature::build_registered_type rejects malformed registration with a corrective message -> test=python/honest-alerts/conformance/laws_build_registered_type_malformed_reason.py::probe_build_registered_type_malformed_reason
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_registered_type -> feature=specs/features/honest-alerts.feature::build_registered_type explains a conflicting registration and its remedies -> test=python/honest-alerts/conformance/laws_build_registered_type_conflict_reason.py::probe_build_registered_type_conflict_reason
# hd: build_registered_type
def build_registered_type(message_type, message_versions, existing):
    """Assemble and validate one registration, apply the re-registration rule against what is stored,
    and return the decision or a Fault (section 3b.1, 3b.3). Shape validation is a fault as data: an
    empty message_versions set or a malformed (non-dot-namespaced or empty) message_type returns a
    client Fault before any comparison. On a valid shape it assembles the arriving RegisteredType
    (exactly two fields) and decides against existing: existing NOTHING -> write the arriving record;
    existing a stored record byte-identical to the arriving whole declaration -> noop carrying the
    stored record; existing a stored record that differs in any way -> a client Fault code
    refused_registration whose detail names the existing declaration against the arriving one. Pure:
    parts and the existing record in, a decision or a fault out, no world."""
    bad_shape = (not message_versions) or (not _is_dotted(message_type))

    def _shape_fault():
        return alerts_fault(
            code="invalid_registration",
            message=(
                "a registration needs a message_type with at least two nonempty namespace components and a non-empty version set; "
                "pass a message_type like 'approval.requested' and at least one version string"
            ),
            category="client",
            detail={"message_type": message_type, "message_versions": message_versions},
        )

    def _refuse(arriving):
        return alerts_fault(
            code="refused_registration",
            message=(
                "this message_type is already registered with a different declaration; change the "
                "arriving declaration to match the stored one, or remove the existing registration first"
            ),
            category="client",
            detail={"existing": existing, "arriving": arriving},
        )

    def _decide():
        arriving = {"message_type": message_type, "message_versions": message_versions}
        first = existing is NOTHING
        identical = (not first) and existing == arriving
        key = _pick(first, lambda: "first", lambda: "identical")
        # The decision table is read by _get with the refuse-thunk as the no-match value, so a
        # differing re-registration (neither first nor identical) lands on the refusal, never a miss.
        decide = _get(_REGISTER_DECISION, _pick(first or identical, lambda: key, lambda: "_refused"),
                      lambda arriving, stored: _refuse(arriving))
        return decide(arriving, existing)

    return _pick(bad_shape, _shape_fault, _decide)


# --- build_message ---------------------------------------------------------------------------------

# The SendOpts keys build_message copies onto the Message (section 8.1). Named once so the one place
# the controlled-field boundary is decided is the one place these keys are written.
_OPT_FIELDS = (
    "message_version",
    "subject_label_id",
    "body_label_id",
    "channel",
    "dom_surface",
    "dom_target",
    "reply_options",
    "termination",
    "ack_scope",
)

# Each condition admits only the fields that participate in it. An unknown condition reads as invalid.
_TERMINATION_OK = {
    "ttl": lambda spec: (
        _get(spec, "ttl_seconds", NOTHING) is not NOTHING
        and _get(spec, "event_type", NOTHING) is NOTHING
        and _get(spec, "event_filter", NOTHING) is NOTHING
    ),
    "event": lambda spec: (
        _get(spec, "ttl_seconds", NOTHING) is NOTHING
        and _get(spec, "event_type", NOTHING) is not NOTHING
    ),
    "acknowledged": lambda spec: all(
        _get(spec, field, NOTHING) is NOTHING for field in ("ttl_seconds", "event_type", "event_filter")
    ),
    "never": lambda spec: all(
        _get(spec, field, NOTHING) is NOTHING for field in ("ttl_seconds", "event_type", "event_filter")
    ),
}

_TERMINATION_CORRECTIONS = {
    "ttl": (
        "the termination fields do not match the ttl condition; "
        "supply ttl_seconds and clear event_type and event_filter to NOTHING"
    ),
    "event": (
        "the termination fields do not match the event condition; "
        "supply event_type, leave ttl_seconds as NOTHING, and optionally specify event_filter"
    ),
    "acknowledged": (
        "the termination fields do not match the acknowledged condition; "
        "clear ttl_seconds, event_type and event_filter to NOTHING"
    ),
    "never": (
        "the termination fields do not match the never condition; "
        "clear ttl_seconds, event_type and event_filter to NOTHING"
    ),
}

# inherits: hd=python/honest-alerts/honest-alerts.hd::build_message -> feature=specs/features/honest-alerts.feature::build_message -> test=python/honest-alerts/conformance/laws_build_message.py::probe_build_message
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_message -> feature=specs/features/honest-alerts.feature::build_message rejects an irrelevant ttl for never termination -> test=python/honest-alerts/conformance/laws_build_message_irrelevant_ttl.py::probe_build_message_irrelevant_ttl
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_message -> feature=specs/features/honest-alerts.feature::build_message rejects fields outside the chosen termination condition -> test=python/honest-alerts/conformance/laws_build_message_termination_invalid_fields.py::probe_build_message_termination_invalid_fields
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_message -> feature=specs/features/honest-alerts.feature::build_message accepts each well-formed termination condition -> test=python/honest-alerts/conformance/laws_build_message_termination_valid.py::probe_build_message_termination_valid
# hd: build_message
def build_message(message_type, recipient, payload, opts, sender, message_id, sent_at, reply_required, registered):
    """Assemble one immutable Message from its already-computed parts and validate it, returning the
    Message or a Fault (section 3.1, 8.1, 3b.2). The impure parts (message_id, sent_at), the sender
    and reply_required are passed in, so this is a pure constructor. registered is the RegisteredType
    read for this message_type, or NOTHING when it was never registered. It reads the controlled
    fields out of opts and places each into the Message. Validation is a fault as data, each failure
    returning the section 6b code: registered NOTHING -> unregistered_message_type; no message_version
    carried -> missing_message_version; a message_version outside registered.message_versions ->
    message_version_not_registered; a termination whose fields do not match its condition ->
    invalid_termination (all client). It never raises and never substitutes a default message_version;
    the registered record is the only authority for which versions exist."""
    message_version = _get(opts, "message_version", NOTHING)
    termination = _get(opts, "termination", NOTHING)
    condition = _pick(termination is NOTHING, lambda: NOTHING, lambda: _get(termination, "condition", NOTHING))

    unregistered = registered is NOTHING
    missing_version = (not unregistered) and (message_version is NOTHING)
    out_of_set = (not unregistered) and (not missing_version) and (
        message_version not in _get(registered, "message_versions", [])
    )
    # A termination is bad when it is absent or when its condition's well-formedness predicate fails;
    # an unknown condition reads out of _TERMINATION_OK as a never-well-formed predicate via _get.
    termination_ok = _get(_TERMINATION_OK, condition, lambda spec: False)
    bad_termination = (
        (not unregistered) and (not missing_version) and (not out_of_set) and (
            (termination is NOTHING) or (not termination_ok(termination))
        )
    )

    def _fault(code, message):
        return alerts_fault(
            code=code,
            message=message,
            category="client",
            detail={"message_type": message_type, "message_version": message_version},
        )

    def _assemble():
        message = {"message_id": message_id, "message_type": message_type, "sender": sender,
                   "recipient": recipient, "payload": payload, "reply_required": reply_required,
                   "resume_token": NOTHING, "sent_at": sent_at}
        placed = reduce(lambda acc, field: {**acc, field: _get(opts, field, NOTHING)}, _OPT_FIELDS, message)
        return placed

    # The validation decision as a closed, ordered table: the first true guard names the fault, and
    # the all-false row builds the Message. next() over the guard pairs picks the first true arm.
    guards = (
        (unregistered, lambda: _fault(
            "unregistered_message_type",
            "this message_type was never registered; register it with register_message_type before sending",
        )),
        (missing_version, lambda: _fault(
            "missing_message_version",
            "the message carries no message_version; pass a message_version registered for this message_type",
        )),
        (out_of_set, lambda: _fault(
            "message_version_not_registered",
            "message_version is outside the registered closed set for this message_type; register the version or send a registered one",
        )),
        (bad_termination, lambda: _fault(
            "invalid_termination",
            _get(
                _TERMINATION_CORRECTIONS,
                condition,
                "the termination condition is missing or unsupported; choose a supported TerminationSpec: ttl, event, acknowledged or never",
            ),
        )),
    )
    chosen = next(map(lambda pair: pair[1], filter(lambda pair: pair[0], guards)), _assemble)
    return chosen()


# --- supervise -------------------------------------------------------------------------------------

# A route matches a message type exactly, or by a trailing-wildcard prefix (order.* matches
# order.placed). A lambda over the route's declared message_type and the message's type.
_type_matches = lambda route_type, message_type: _pick(
    route_type.endswith(".*"),
    lambda: message_type.startswith(route_type[:-1]),
    lambda: route_type == message_type,
)

# A route's sender_type gate: NOTHING matches any sender, else it must equal the message sender's type.
_sender_matches = lambda route_sender_type, sender_type: _pick(
    route_sender_type is NOTHING,
    lambda: True,
    lambda: route_sender_type == sender_type,
)

# A route is kept when its type and sender both match the message. A lambda over the route and the
# two message facts, so the supervisor's filter is a predicate, not an if.
_route_kept = lambda route, message_type, sender_type: (
    _type_matches(route["message_type"], message_type) and _sender_matches(route["sender_type"], sender_type)
)

# One ChannelConfig under one route becomes one pending Delivery. The recipient is the config's
# recipient_spec when set, else the message recipient. An absent delay delivers at sent_at.
_delivery_of = lambda message, route, config: {
    "message_id": message["message_id"],
    "route_id": route["route_id"],
    "channel": config["channel"],
    "recipient": _get(config, "recipient_spec", NOTHING) or message["recipient"],
    "deliver_at": message["sent_at"] + (_get(config, "delay_seconds", NOTHING) or 0),
    "status": "pending",
}

# One route expands to its channels' Deliveries, in channel order. A lambda over the message and route.
_route_deliveries = lambda message, route: [_delivery_of(message, route, config) for config in route["channels"]]


# inherits: hd=python/honest-alerts/honest-alerts.hd::supervise -> feature=specs/features/honest-alerts.feature::supervise -> test=python/honest-alerts/conformance/laws_supervise.py::probe_supervise
# inherits: hd=python/honest-alerts/honest-alerts.hd::supervise -> feature=specs/features/honest-alerts.feature::supervise delivers immediately for an absent channel delay -> test=python/honest-alerts/conformance/laws_supervise_absent_delay.py::probe_supervise_absent_delay
# hd: supervise
def supervise(message, routing_table):
    """The supervisor: the pure core that produces the delivery plan from a message and the routing
    table (section 6, 6.1), stateless with no memory between invocations. It keeps the routes whose
    message_type matches the message's type (trailing-wildcard included) and whose sender_type is
    NOTHING or equals the message sender's type, sorts the kept routes by priority ascending, and for
    each route, for each ChannelConfig, resolves the recipient (the config's recipient_spec if set,
    else the message recipient), computes deliver_at as sent_at plus the config's delay or immediately, and
    builds one pending Delivery. The Deliveries in route-and-channel order are the DeliveryPlan. In
    unit 1 the match is assumed non-empty. Pure: a message and a table in, a plan out, no world."""
    message_type = message["message_type"]
    sender_type = message["sender"]["type"]
    kept = filter(lambda route: _route_kept(route, message_type, sender_type), routing_table)
    ordered = sorted(kept, key=lambda route: route["priority"])
    deliveries = reduce(lambda acc, route: acc + _route_deliveries(message, route), ordered, [])
    return {"deliveries": deliveries}


# --- build_ack_event -------------------------------------------------------------------------------

# hd: build_ack_event
def build_ack_event(message_id, actor_ref, reply_payload, session, acknowledged_at):
    """Assemble the payload of the alert.acknowledged event from its parts (section 9.1, 10, 4.1).
    message_id is carried so the mailbox projection can match acks to their message; actor_ref is the
    acknowledging actor placed on the payload under `actor` (never actor_id); reply_payload is carried
    through; acknowledged_at, read at the boundary and passed in, is carried (this pure function never
    calls now); session is the acking DOM session placed on the payload under `session` (never
    session_id), NOTHING when the ack did not come in under a DOM session. It places no scope word on
    the payload: the only scope vocabulary is the message's own ack_scope. Pure: parts in, payload
    out, no world and no fault."""
    return {
        "message_id": message_id,
        "actor": actor_ref,
        "acknowledged_at": acknowledged_at,
        "reply_payload": reply_payload,
        "session": session,
    }


# --- advance ---------------------------------------------------------------------------------------

# The lifecycle transition table (section 7): (state, event) -> next state. A (state, event) pair the
# table does not carry is undeclared, including every event from a terminal state. Declared as data,
# so advance is a lookup, not an if ladder (P01, P16).
_TRANSITIONS = {
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


# hd: advance
def advance(state, event):
    """The message lifecycle state machine as a pure transition function (section 7). Given the current
    AlertState and an AlertEvent it returns the next AlertState when the pair names a declared
    transition, and a Fault via alerts_fault code invalid_transition (category server) when it does
    not: a (state, event) pair the transition table does not declare, including any event from a
    terminal state (acknowledged, actioned, expired, failed). Pure: a state and an event in, the next
    state or a fault out, no world; the lifecycle stays declared data. The table is read by _get with
    an invalid_transition fault as the no-match value, so an undeclared pair returns a self-describing
    server Fault rather than a bare KeyError (HC-P020)."""
    pair = (state, event)
    return _get(_TRANSITIONS, pair, alerts_fault(
        code="invalid_transition",
        message=(
            f"no lifecycle transition is declared for state {state!r} on event {event!r}; "
            f"a message in a terminal state accepts no event, and only declared (state, event) "
            f"pairs advance the lifecycle"
        ),
        category="server",
        detail={"state": state, "event": event},
    ))


# --- termination: scope_terminated dispatch and is_terminated --------------------------------------

# The acks slice reads payload.session (the acking DOM session) and payload.actor.id (the acking
# actor). Lambdas, not column-0 defs; _get reads the nested maps with an explicit absence.
_ack_session = lambda ack: _get(_get(ack, "payload", {}), "session", NOTHING)
_ack_actor_id = lambda ack: _get(_get(_get(ack, "payload", {}), "actor", {}), "id", NOTHING)


# hd: terminated_session
def terminated_session(acks, actor_ref, viewing_session):
    """The session-scoped row of the scope_terminated dispatch (section 4.1): terminated only when
    viewing_session is not NOTHING and some ack's acking session (payload.session) equals
    viewing_session. viewing_session of NOTHING is the waiter view and matches no session, so a
    session dismissal never ends a waiting send_and_wait. actor_ref is unused here, present only so
    every row shares one signature. Pure: an event slice and the viewer in, a boolean out."""
    return (viewing_session is not NOTHING) and any(_ack_session(ack) == viewing_session for ack in acks)


# hd: terminated_actor
def terminated_actor(acks, actor_ref, viewing_session):
    """The actor-scoped row of the scope_terminated dispatch (section 4.1): terminated when some ack's
    payload.actor.id equals actor_ref.id, that is, when the recipient actor acknowledged on any one of
    its sessions. viewing_session is ignored: an actor-scoped ack terminates for every viewer, the
    waiter included. Pure: an event slice and the actor in, a boolean out."""
    return any(_ack_actor_id(ack) == actor_ref["id"] for ack in acks)


# hd: terminated_broadcast
def terminated_broadcast(acks, actor_ref, viewing_session):
    """The broadcast-scoped row of the scope_terminated dispatch (section 4.1): terminated when the
    acks slice is non-empty, that is, when any recipient acknowledged. actor_ref and viewing_session
    are ignored: a broadcast-scoped ack by any one recipient terminates for every viewer, the waiter
    included. Pure: an event slice in, a boolean out."""
    return len(acks) > 0


# The scope_terminated dispatch: one handler per AckScope member. is_terminated selects a handler by
# the message's ack_scope through _get with a server-Fault no-match value, because ack_scope is a
# bounded AckScope fixed at build time, so a value the table does not carry is a program bug (section
# 4.1, 13.7).
_SCOPE_TERMINATED = {
    "session": terminated_session,
    "actor": terminated_actor,
    "broadcast": terminated_broadcast,
}

# An event terminates when its payload matches the optional event_filter: every filter key equals the
# event payload's value for that key. A lambda over the event payload and the filter.
_filter_matches = lambda event_payload, event_filter: all(
    _get(event_payload, key, NOTHING) == value for key, value in event_filter.items()
)

# One honest-observe event's type and timestamp, read with an explicit absence rather than a .get
# default (HC-P019). Lambdas.
_event_type = lambda event: _get(event, "event_type", NOTHING)
_event_timestamp = lambda event: _get(event, "timestamp", NOTHING)
_event_payload = lambda event: _get(event, "payload", {})


_OBSERVE_TIMESTAMP = re.compile(
    r"([0-9]{4})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):([0-5][0-9]):([0-5][0-9])\.([0-9]{6})Z"
)
_EPOCH_ORDINAL = date(1970, 1, 1).toordinal()


# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::event_at_or_after -> feature=specs/features/honest-alerts.feature::event_at_or_after compares canonical Observe timestamps at microsecond precision -> test=python/honest-alerts/conformance/laws_event_at_or_after_canonical.py::probe_event_at_or_after_canonical
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::event_at_or_after -> feature=specs/features/honest-alerts.feature::event_at_or_after accepts legacy integers and rejects unsupported timestamps -> test=python/honest-alerts/conformance/laws_event_at_or_after_legacy.py::probe_event_at_or_after_legacy
# hd: event_at_or_after
def event_at_or_after(timestamp, sent_at):
    """Compare an epoch-second integer or canonical UTC timestamp to sent_at."""
    match timestamp:
        case bool():
            return False
        case int():
            return timestamp >= sent_at
        case str():
            parsed = _OBSERVE_TIMESTAMP.fullmatch(timestamp)
        case _:
            return False

    match parsed:
        case None:
            return False
        case _:
            year, month, day, hour, minute, second, microsecond = map(int, parsed.groups())

    return _pick(
        year > 0 and day <= monthrange(year, month)[1],
        lambda: (
            ((date(year, month, day).toordinal() - _EPOCH_ORDINAL) * 86_400 + hour * 3600 + minute * 60 + second)
            * 1_000_000 + microsecond
        ) >= sent_at * 1_000_000,
        lambda: False,
    )


# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::uuid7_from_parts -> feature=specs/features/honest-alerts.feature::uuid7_from_parts preserves the timestamp and entropy fields in canonical text -> test=python/honest-alerts/conformance/laws_uuid7_from_parts.py::probe_uuid7_from_parts
# hd: uuid7_from_parts
def uuid7_from_parts(unix_ms, random_a, random_b):
    """Pack the supplied timestamp and entropy into a canonical UUID v7."""
    value = (unix_ms & 0xFFFFFFFFFFFF) << 80
    value |= (0x7 << 76) | ((random_a & 0x0FFF) << 64)
    value |= (0b10 << 62) | (random_b & 0x3FFFFFFFFFFFFFFF)
    return str(uuid.UUID(int=value))


# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::is_terminated -> feature=specs/features/honest-alerts.feature::is_terminated skips a malformed timestamp and matches a later Observe event -> test=python/honest-alerts/conformance/laws_is_terminated_observe_timestamp.py::probe_is_terminated_observe_timestamp
# hd: is_terminated
def is_terminated(msg, actor_ref, at_time, events, viewing_session):
    """Decide whether one message has terminated for the viewer the read is taken for at at_time, the
    predicate mailbox folds with (section 4.1). It reads msg.termination and branches on its condition:
    ttl -> terminated when at_time is past sent_at + ttl_seconds; event -> terminated when an event of
    the spec's event_type at or after sent_at matches the optional event_filter; never -> never
    terminated; acknowledged -> it selects the alert.acknowledged slice for this message (every event
    whose payload.message_id equals the message's id) and dispatches on the message's ack_scope through
    the scope_terminated table (session/actor/broadcast) plus a no-match row. The no-match row is
    reached only if ack_scope is a value the table does not carry, a program bug, so is_terminated
    returns a server Fault via alerts_fault (code unknown_ack_scope) rather than a silent False, and
    that Fault is the table's no-match row. It consults no lifecycle state machine. Pure: a message, an
    event slice and the viewer in, a boolean or a Fault out, no world. The Fault travels by return."""
    termination = msg["termination"]
    condition = termination["condition"]
    sent_at = msg["sent_at"]

    def _ttl():
        return at_time > sent_at + termination["ttl_seconds"]

    def _event():
        event_type = termination["event_type"]
        event_filter = _get(termination, "event_filter", NOTHING)
        matching = filter(
            lambda event: _event_type(event) == event_type and event_at_or_after(_event_timestamp(event), sent_at),
            events,
        )
        return any(
            (event_filter is NOTHING) or _filter_matches(_event_payload(event), event_filter)
            for event in matching
        )

    def _never():
        return False

    def _acknowledged():
        acks = list(filter(
            lambda event: _event_type(event) == "alert.acknowledged"
            and _get(_event_payload(event), "message_id", NOTHING) == msg["message_id"],
            events,
        ))
        ack_scope = msg["ack_scope"]
        # The scope table is read by _get with a server-Fault no-match value; a bounded ack_scope the
        # table does not carry is a program bug, surfaced as a Fault, never a silent False.
        handler = _get(_SCOPE_TERMINATED, ack_scope, "_no_match")
        return _pick(
            handler == "_no_match",
            lambda: alerts_fault(
                code="unknown_ack_scope",
                message=(
                    f"ack_scope {ack_scope!r} matched no scope_terminated branch; accepted scopes are "
                    f"{sorted(_SCOPE_TERMINATED)}. ack_scope is fixed at message build time, so this is a program bug"
                ),
                category="server",
                detail={"accepted": sorted(_SCOPE_TERMINATED), "arrived": ack_scope},
            ),
            lambda: handler(acks, actor_ref, viewing_session),
        )

    conditions = {"ttl": _ttl, "event": _event, "never": _never, "acknowledged": _acknowledged}
    # The condition table is read by _get with a server-Fault no-match value; a bounded
    # TerminationCondition the table does not carry is a program bug, surfaced as a Fault.
    branch = _get(conditions, condition, "_no_match")
    return _pick(
        branch == "_no_match",
        lambda: alerts_fault(
            code="unknown_termination_condition",
            message=(
                f"termination condition {condition!r} matched no branch; accepted conditions are "
                f"{sorted(conditions)}. the condition is a bounded TerminationCondition fixed at build time"
            ),
            category="server",
            detail={"accepted": sorted(conditions), "arrived": condition},
        ),
        lambda: branch(),
    )


# --- mailbox ---------------------------------------------------------------------------------------

# An alert.sent event's recipient matches the actor the read is for when type and id agree. A lambda
# over the message's recipient and the reading actor.
_recipient_matches = lambda recipient, actor_ref: (
    _get(recipient, "type", NOTHING) == _get(actor_ref, "type", NOTHING)
    and _get(recipient, "id", NOTHING) == _get(actor_ref, "id", NOTHING)
)

# One alert.sent event is addressed to this actor and in time when its type is alert.sent, its
# recipient matches, and its sent_at is at or before at_time. A lambda over the event, actor and time.
_addressed_in_time = lambda event, actor_ref, at_time: (
    _event_type(event) == "alert.sent"
    and _recipient_matches(_event_payload(event)["recipient"], actor_ref)
    and _event_payload(event)["sent_at"] <= at_time
)

# The is_err tag recognizer: a message's termination verdict is a Fault when it carries is_err true.
_is_err = lambda value: isinstance(value, dict) and value.get("is_err") is True


# hd: mailbox
def mailbox(actor_ref, at_time, events, viewing_session):
    """An actor's mailbox as a pure projection over the events handed to it: which messages addressed
    to this actor have not yet terminated at at_time, for the viewer the read is taken for (section
    4.1). The caller selects the event set through an honest-observe projection and passes it as
    events; mailbox folds over exactly those and reads nothing else. viewing_session is passed straight
    through to is_terminated unchanged and no session is read off actor_ref. It keeps the alert.sent
    events whose recipient matches actor_ref and whose sent_at is at or before at_time, invokes
    is_terminated for each to drop the terminated ones, and returns the pending Messages ordered by
    sent_at ascending. is_terminated can return a server Fault on its dispatch no-match row; that Fault
    travels by return, so mailbox returns list<Message> | Fault and surfaces it. Pure: a fold over the
    given events, no world."""
    sent = list(map(_event_payload, filter(lambda event: _addressed_in_time(event, actor_ref, at_time), events)))
    ordered = sorted(sent, key=lambda message: message["sent_at"])
    # Pair each message with its termination verdict, then fold: a Fault verdict surfaces by return,
    # a False keeps the message, a True drops it. The fold's accumulator is either the running list of
    # pending messages or the first Fault encountered; _pick decides each step without an if.
    verdicts = [(message, is_terminated(message, actor_ref, at_time, events, viewing_session)) for message in ordered]

    def _fold(acc, pair):
        message, verdict = pair
        return _pick(
            _is_err(acc),
            lambda: acc,  # a Fault already surfaced; carry it to the end
            lambda: _pick(
                _is_err(verdict),
                lambda: verdict,  # this verdict is the surfaced Fault
                lambda: _pick(verdict, lambda: acc, lambda: acc + [message]),
            ),
        )

    return reduce(_fold, verdicts, [])

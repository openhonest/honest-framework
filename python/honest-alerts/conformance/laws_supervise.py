# scenario: supervise
# inherits: hd=python/honest-alerts/honest-alerts.hd::supervise -> feature=specs/features/honest-alerts.feature::supervise
"""Red test fragment for the honest-alerts `supervise` scenario (one scenario only).

supervise is the pure supervisor core (honest-alerts.hd, section 6/6.1): it takes a Message
and the routing table and produces a DeliveryPlan, stateless, writing nothing. The scenario
(specs/features/honest-alerts.feature) fixes:

  - it keeps the routes whose message_type matches the message's type (including a trailing
    wildcard) and whose sender_type is NOTHING or equals the message sender's type, and sorts
    the kept routes by priority ascending;
  - for each route, for each ChannelConfig, it resolves the recipient (the config's
    recipient_spec if set, else the message recipient), computes deliver_at as the message
    sent_at plus the config's delay_seconds, and builds one pending Delivery; the Deliveries in
    route-and-channel order are the DeliveryPlan;
  - in unit 1 the match is assumed non-empty, so the DeliveryPlan is the non-empty result;
  - it returns DeliveryPlan alone (no Fault arm in unit 1: the empty-match alert.no_route is a
    later-unit concern), a plan out, no world.

Honest form: cases are data, one pure probe feeds them to the real supervise, faults are
returned as a list of strings. Records (Message, AlertRoute, ChannelConfig, Delivery,
DeliveryPlan, ActorRef) are plain dicts, the representation the module's own conformance uses.

Run directly:
  cd python && uv run --package honest-alerts \
    python honest-alerts/conformance/laws_supervise.py
"""

from honest_alerts import supervise


def _message(**overrides):
    """A Message as a flat dict; overrides adjust one field per case."""
    message = {
        "message_id": "m1",
        "message_type": "order.placed",
        "message_version": "1",
        "sender": {"type": "framework", "id": None, "tenant_id": None},
        "recipient": {"type": "user", "id": "u1", "tenant_id": None},
        "subject_label_id": "alerts.order_placed",
        "body_label_id": None,
        "channel": None,
        "dom_surface": None,
        "dom_target": None,
        "reply_options": None,
        "resume_token": None,
        "payload": {},
        "reply_required": False,
        "termination": {"condition": "ttl", "ttl_seconds": 10, "event_type": None, "event_filter": None},
        "ack_scope": "actor",
        "sent_at": 1000,
    }
    message.update(overrides)
    return message


# --- the message and routing tables each case supervises -----------------------------------

# A message of type order.placed from a framework sender, recipient user u1, sent at 1000.
_MSG = _message()

# One matching route, one dom channel with no recipient_spec and no delay. The plan must carry
# one pending Delivery to the message's own recipient, deliver_at == sent_at (1000 + 0).
_ONE_ROUTE = [
    {
        "route_id": "r1",
        "message_type": "order.placed",
        "sender_type": None,
        "channels": [{"channel": "dom", "recipient_spec": None, "template_id": None, "delay_seconds": 0}],
        "escalation": None,
        "priority": 1,
    },
]

# Two matching routes out of priority order, plus one non-matching type and one non-matching
# sender_type that must both be dropped. The kept routes sort priority ascending (r_exact=1 then
# r_wild=2), and within each route its channels keep order. r_wild's email channel overrides the
# recipient with recipient_spec and delays 300s (deliver_at 1000+300).
_MULTI_ROUTE = [
    {
        "route_id": "r_wild",
        "message_type": "order.*",
        "sender_type": None,
        "channels": [
            {"channel": "email", "recipient_spec": {"type": "role", "id": "admin", "tenant_id": None},
             "template_id": None, "delay_seconds": 300},
        ],
        "escalation": None,
        "priority": 2,
    },
    {
        "route_id": "r_exact",
        "message_type": "order.placed",
        "sender_type": "framework",
        "channels": [
            {"channel": "dom", "recipient_spec": None, "template_id": None, "delay_seconds": 0},
            {"channel": "sms", "recipient_spec": None, "template_id": None, "delay_seconds": 60},
        ],
        "escalation": None,
        "priority": 1,
    },
    {
        "route_id": "r_other_wild",
        "message_type": "ordering.*",
        "sender_type": None,
        "channels": [{"channel": "dom", "recipient_spec": None, "template_id": None, "delay_seconds": 0}],
        "escalation": None,
        "priority": 0,
    },
    {
        "route_id": "r_exact_near_miss",
        "message_type": "order.placer",
        "sender_type": None,
        "channels": [{"channel": "dom", "recipient_spec": None, "template_id": None, "delay_seconds": 0}],
        "escalation": None,
        "priority": 0,
    },
    {
        "route_id": "r_other_type",
        "message_type": "auth.login",
        "sender_type": None,
        "channels": [{"channel": "dom", "recipient_spec": None, "template_id": None, "delay_seconds": 0}],
        "escalation": None,
        "priority": 0,
    },
    {
        "route_id": "r_other_sender",
        "message_type": "order.placed",
        "sender_type": "auth",
        "channels": [{"channel": "dom", "recipient_spec": None, "template_id": None, "delay_seconds": 0}],
        "escalation": None,
        "priority": 0,
    },
]


def _delivery(route_id, channel, recipient, deliver_at):
    """One pending Delivery, the record supervise builds per channel."""
    return {
        "message_id": "m1",
        "route_id": route_id,
        "channel": channel,
        "recipient": recipient,
        "deliver_at": deliver_at,
        "status": "pending",
    }


_USER_U1 = {"type": "user", "id": "u1", "tenant_id": None}
_ROLE_ADMIN = {"type": "role", "id": "admin", "tenant_id": None}


_CASES = [
    # One matching route, one channel: one pending Delivery to the message recipient, no delay.
    {
        "given": {"message": _MSG, "routing_table": _ONE_ROUTE},
        "expect": {
            "deliveries": [
                _delivery("r1", "dom", _USER_U1, 1000),
            ],
        },
    },
    # Two matching routes sorted priority ascending; non-matching type and sender dropped;
    # channel order preserved; recipient_spec and delay resolved.
    {
        "given": {"message": _MSG, "routing_table": _MULTI_ROUTE},
        "expect": {
            "deliveries": [
                _delivery("r_exact", "dom", _USER_U1, 1000),   # priority 1, first channel, no delay
                _delivery("r_exact", "sms", _USER_U1, 1060),   # priority 1, second channel, +60
                _delivery("r_wild", "email", _ROLE_ADMIN, 1300),  # priority 2, recipient_spec, +300
            ],
        },
    },
    # order.* includes the dot: it does not match the separate orderly namespace.
    {
        "given": {
            "message": _message(message_type="orderly.placed"),
            "routing_table": [
                _MULTI_ROUTE[0],
                {**_ONE_ROUTE[0], "message_type": "orderly.placed"},
            ],
        },
        "expect": {"deliveries": [_delivery("r1", "dom", _USER_U1, 1000)]},
    },
]


def probe_supervise():
    """supervise keeps and sorts the matching routes and builds one pending Delivery per channel,
    resolving recipient and deliver_at, returning the non-empty DeliveryPlan (route-and-channel
    order)."""
    bad = []
    for case in _CASES:
        got = supervise(**case["given"])
        if got != case["expect"]:
            bad.append(
                f"supervise(message={case['given']['message']['message_id']}, "
                f"{len(case['given']['routing_table'])} routes) -> {got}, expected {case['expect']}"
            )
    return bad


def run():
    bad = probe_supervise()
    for line in bad:
        print("FAIL:", line)
    if not bad:
        print("laws_supervise: ok")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(run())

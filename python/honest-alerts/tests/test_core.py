from honest_alerts import (
    apply_escalation,
    build_message,
    is_terminated,
    mailbox,
    match_routes,
    supervise,
    transition_lifecycle,
)


def _admin():
    return {"kind": "admin", "id": "admin-1", "tenant_id": "t1"}


def _user():
    return {"kind": "user", "id": "u1", "tenant_id": "t1"}


def _chain_sender():
    return {"kind": "chain", "id": "c1", "tenant_id": "t1"}


def _routing_table():
    return [
        {
            "route_id": "r1",
            "message_type": "deploy.failed",
            "sender_type": "chain",
            "channels": [
                {"channel": "dom", "recipient_spec": _admin(),
                 "template_id": "", "delay_seconds": 0},
                {"channel": "email", "recipient_spec": _admin(),
                 "template_id": "", "delay_seconds": 60},
            ],
            "escalation": None,
            "priority": 10,
        },
        {
            "route_id": "r2",
            "message_type": "anything",
            "sender_type": "",
            "channels": [
                {"channel": "dom", "recipient_spec": _admin(),
                 "template_id": "", "delay_seconds": 0},
            ],
            "escalation": None,
            "priority": 1,
        },
    ]


def test_build_message_populates_fields():
    m = build_message("x", _admin(), _user(), {"k": "v"})
    assert m["message_type"] == "x"
    assert m["payload"] == {"k": "v"}
    assert m["resume_token"]


def test_match_routes_filters_by_type():
    m = build_message("deploy.failed", _chain_sender(), _admin(), {})
    matches = match_routes(m, _routing_table())
    assert len(matches) == 1
    assert matches[0]["route_id"] == "r1"


def test_match_routes_wildcard_sender():
    m = build_message("anything", _user(), _admin(), {})
    matches = match_routes(m, _routing_table())
    assert any(r["route_id"] == "r2" for r in matches)


def test_supervise_produces_plans_per_channel():
    m = build_message("deploy.failed", _chain_sender(), _admin(), {})
    plans = supervise(m, _routing_table())
    assert len(plans) == 2
    channels = {p["channel"] for p in plans}
    assert channels == {"dom", "email"}


def test_apply_escalation_builds_new_message():
    m = build_message("invoice.overdue", _user(), _user(), {})
    rule = {
        "ttl_seconds": 86400,
        "escalate_to": _admin(),
        "escalate_channel": "email",
        "escalation_message_type": "invoice.overdue.escalated",
    }
    e = apply_escalation(m, rule)
    assert e["message_type"] == "invoice.overdue.escalated"
    assert e["recipient"]["id"] == "admin-1"


def test_mailbox_projects_for_actor():
    m1 = build_message("x", _chain_sender(), _user(), {})
    m2 = build_message("y", _chain_sender(), _admin(), {})
    events = [
        {"event_type": "alert.sent", "payload": {"message_id": m1["message_id"], "message": m1}},
        {"event_type": "alert.sent", "payload": {"message_id": m2["message_id"], "message": m2}},
    ]
    inbox = mailbox(_user(), at_time=0, events=events)
    assert len(inbox) == 1
    assert inbox[0]["message_id"] == m1["message_id"]


def test_mailbox_excludes_terminated():
    m1 = build_message("x", _chain_sender(), _user(), {})
    events = [
        {"event_type": "alert.sent",       "payload": {"message_id": m1["message_id"], "message": m1}},
        {"event_type": "alert.acknowledged", "payload": {"message_id": m1["message_id"]}},
    ]
    inbox = mailbox(_user(), at_time=0, events=events)
    assert inbox == []


def test_is_terminated_sees_acknowledged():
    m = build_message("x", _chain_sender(), _user(), {})
    events = [{"event_type": "alert.acknowledged", "payload": {"message_id": m["message_id"]}}]
    assert is_terminated(m, _user(), 0, events)


def test_transition_lifecycle_known():
    assert transition_lifecycle("created", "deliver") == "delivered"
    assert transition_lifecycle("delivered", "read") == "read"
    assert transition_lifecycle("read", "acknowledge") == "acknowledged"


def test_transition_lifecycle_unknown():
    assert transition_lifecycle("acknowledged", "deliver") == ""

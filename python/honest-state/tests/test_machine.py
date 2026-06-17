from honest_state import (
    advance,
    is_terminal,
    lookup_transition,
    manifest,
    state_machine,
    transition,
    validate_event,
    validate_state,
)


def _order_machine():
    return state_machine(
        name="order",
        states=["pending", "paid", "shipped", "cancelled"],
        events=["pay", "ship", "cancel", "refund"],
        transitions={
            ("pending", "pay"):     "paid",
            ("pending", "cancel"):  "cancelled",
            ("paid",    "ship"):    "shipped",
            ("paid",    "cancel"):  "cancelled",
            ("shipped", "refund"):  "cancelled",
        },
        initial="pending",
        terminal=["cancelled"],
    )


def test_validate_state_known():
    m = _order_machine()
    assert validate_state(m, "paid")
    assert not validate_state(m, "unknown")


def test_validate_event():
    m = _order_machine()
    assert validate_event(m, "pay")
    assert not validate_event(m, "fly")


def test_is_terminal():
    m = _order_machine()
    assert is_terminal(m, "cancelled")
    assert not is_terminal(m, "pending")


def test_lookup_transition():
    m = _order_machine()
    assert lookup_transition(m, "pending", "pay") == "paid"
    assert lookup_transition(m, "pending", "ship") is None


def test_transition_happy_path():
    m = _order_machine()
    r = transition(m, "pending", "pay")
    assert r["ok_state"] == "paid"
    assert r["err_code"] == ""


def test_transition_from_terminal():
    m = _order_machine()
    r = transition(m, "cancelled", "pay")
    assert r["err_code"] == "terminal_state"


def test_transition_unknown_state():
    m = _order_machine()
    r = transition(m, "unknown", "pay")
    assert r["err_code"] == "invalid_state"


def test_transition_unknown_event():
    m = _order_machine()
    r = transition(m, "pending", "fly")
    assert r["err_code"] == "invalid_event"


def test_transition_undefined():
    m = _order_machine()
    r = transition(m, "pending", "ship")
    assert r["err_code"] == "no_transition"


def test_advance_is_alias():
    m = _order_machine()
    assert advance(m, "pending", "pay")["ok_state"] == "paid"


def test_manifest_builds_entries():
    m = manifest({
        "email": {"selector": "#email", "read": "value", "write": "value"},
        "check": {"selector": "#c", "read": "checked", "write": "checked"},
    })
    assert m["entries"]["email"]["selector"] == "#email"
    assert m["entries"]["check"]["read"] == "checked"

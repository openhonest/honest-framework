"""Tests for bindings + manifest emission."""
from honest_type import binding, emit_manifest, resolve_bindings
from honest_type.types import Ticket


def _tickets():
    return [
        Ticket(type="email", value="a@b.co", slot=""),
        Ticket(type="int",   value="42",     slot=""),
        Ticket(type="other", value="?",      slot=""),
    ]


def test_resolve_bindings_fills_slots():
    b = binding({"email": "user_email", "int": "user_age"})
    out = resolve_bindings(_tickets(), b)
    slots = [t["slot"] for t in out]
    assert slots == ["user_email", "user_age", ""]


def test_resolve_bindings_preserves_value():
    b = binding({"email": "user_email"})
    out = resolve_bindings(_tickets(), b)
    assert out[0]["value"] == "a@b.co"
    assert out[0]["type"] == "email"


def test_emit_manifest_groups_by_slot():
    b = binding({"email": "user_email", "int": "user_age"})
    tickets = resolve_bindings(_tickets(), b)
    m = emit_manifest(tickets)
    assert m["slots"] == {"user_email": "a@b.co", "user_age": "42"}
    # Unbound ticket kept in tickets list, but not in slots.
    assert len(m["tickets"]) == 3


def test_emit_manifest_later_slot_wins():
    ts = [
        Ticket(type="a", value="first",  slot="x"),
        Ticket(type="b", value="second", slot="x"),
    ]
    m = emit_manifest(ts)
    assert m["slots"]["x"] == "second"

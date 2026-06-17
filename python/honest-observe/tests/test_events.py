"""Tests for event envelope + projections + translators."""
import pytest

from honest_observe import (
    advance_hlc,
    build_envelope,
    emit,
    fold,
    project,
    recognize_stripe_payment,
    reject_event,
    reset_log,
    resolve_identity,
    translate_stripe_payment,
)
from honest_observe.types import HLC


def setup_function():
    reset_log()


def test_build_envelope_populates_all_fields():
    ev = build_envelope(
        event_type="order.paid",
        aggregate_type="order",
        aggregate_id="ord-42",
        payload={"amount": 99},
        context={"meta": {"source": "test"}},
    )
    assert ev["event_type"] == "order.paid"
    assert ev["aggregate_id"] == "ord-42"
    assert ev["payload"] == {"amount": 99}
    assert ev["meta"]["source"] == "test"
    assert ev["sequence"] >= 1


def test_emit_returns_result_with_id():
    r = emit("x", "agg", "id", {}, None)
    assert r["event_id"]
    assert r["err_code"] == ""


def test_project_folds_events():
    count_fold = lambda s, e: {**s, "state_blob": {**s["state_blob"], "n": s["state_blob"].get("n", 0) + 1}}
    initial = {"projection_id": "p", "snapshot_at": "", "state_blob": {}}
    evs = [
        build_envelope("x", "a", "1", {}, {}),
        build_envelope("x", "a", "1", {}, {}),
        build_envelope("x", "a", "1", {}, {}),
    ]
    final = project(evs, count_fold, initial)
    assert final["state_blob"]["n"] == 3


def test_default_fold_is_identity():
    initial = {"projection_id": "p", "snapshot_at": "", "state_blob": {}}
    ev = build_envelope("x", "a", "1", {}, {})
    result = fold(initial, ev)
    assert result is initial


def test_recognize_stripe_payment():
    assert recognize_stripe_payment({"type": "payment_intent.succeeded"}) is True
    assert recognize_stripe_payment({"type": "something_else"}) is False


def test_translate_stripe_payment_produces_order_paid():
    raw = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_123", "amount": 9900, "currency": "usd"}},
    }
    ev = translate_stripe_payment(raw)
    assert ev["event_type"] == "order.paid"
    assert ev["aggregate_id"] == "pi_123"
    assert ev["payload"]["amount"] == 9900


def test_reject_event_captures_reason():
    rej = reject_event("unrecognized_shape", {"type": "mystery"})
    assert rej["reason_code"] == "unrecognized_shape"
    assert rej["raw_event"]["type"] == "mystery"


def test_resolve_identity_lookup():
    bindings = {"stripe:pi_123": "user_alice"}
    assert resolve_identity("pi_123", "stripe", bindings) == "user_alice"


def test_resolve_identity_missing_raises():
    with pytest.raises(KeyError, match="identity_unknown"):
        resolve_identity("pi_unknown", "stripe", {})


def test_advance_hlc_picks_max_physical():
    local = HLC(physical=1000, logical=0, source="s")
    incoming = HLC(physical=2000, logical=5, source="s")
    merged = advance_hlc(local, incoming)
    assert merged["physical"] >= 2000

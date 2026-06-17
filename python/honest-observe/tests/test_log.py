"""Tests for the append-only log boundary."""
from honest_observe import (
    append_event,
    build_envelope,
    emit,
    read_event_log,
    read_rejections,
    reject_event,
    reset_log,
    run_projection,
)


def setup_function():
    reset_log()


def test_append_and_read():
    ev = build_envelope("order.paid", "order", "ord-1", {}, {})
    append_event(ev)
    events = read_event_log("", "")
    assert len(events) == 1
    assert events[0]["event_type"] == "order.paid"


def test_read_filters_by_type():
    emit("order.paid",     "order", "a", {}, None)
    emit("order.shipped",  "order", "a", {}, None)
    paid = read_event_log("", "", filter_types=["order.paid"])
    assert len(paid) == 1


def test_rejection_appending():
    from honest_observe import append_rejection
    append_rejection(reject_event("unrecognized_shape", {"x": 1}))
    assert len(read_rejections()) == 1


def test_run_projection_folds_and_snapshots():
    emit("order.paid", "order", "a", {"amount": 10}, None)
    emit("order.paid", "order", "b", {"amount": 20}, None)
    emit("order.paid", "order", "c", {"amount": 30}, None)

    def sum_amount(state, event):
        n = state["state_blob"].get("total", 0) + event["payload"]["amount"]
        return {**state, "state_blob": {"total": n}}

    proj = {
        "projection_id": "revenue",
        "event_types": ["order.paid"],
        "fold_fn": sum_amount,
        "initial_state": {"projection_id": "revenue", "snapshot_at": "", "state_blob": {}},
        "snapshot_interval": 0,
    }
    snap = run_projection(proj, "", "")
    assert snap["state_blob"]["total"] == 60

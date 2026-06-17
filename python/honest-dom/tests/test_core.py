from honest_dom import (
    build_envelope,
    build_manifest,
    merge_state,
    scope_manifest,
    strip_values_for_production,
)


def test_build_manifest_defaults():
    m = build_manifest({"email": {"selector": "#email"}})
    assert m["entries"]["email"]["read"] == "value"
    assert m["entries"]["email"]["watch"] == "input"


def test_build_manifest_overrides():
    m = build_manifest({
        "c": {"selector": "#c", "read": "checked", "write": "checked", "watch": "change"}
    })
    assert m["entries"]["c"]["read"] == "checked"


def test_merge_state_combines():
    a = {"values": {"x": 1, "y": 2}}
    b = {"values": {"y": 99, "z": 3}}
    merged = merge_state(a, b)
    assert merged["values"] == {"x": 1, "y": 99, "z": 3}


def test_scope_manifest_intersects():
    root = build_manifest({"a": {"selector": "#a"}, "b": {"selector": "#b"}})
    sub = build_manifest({"b": {"selector": "#b"}, "c": {"selector": "#c"}})
    out = scope_manifest(root, sub)
    assert set(out["entries"]) == {"b"}


def test_build_envelope_fields():
    e = build_envelope("hf.dom.changed", {"k": "v"}, "req-1", "sess-1")
    assert e["event_type"] == "hf.dom.changed"
    assert e["request_id"] == "req-1"
    assert e["session_id"] == "sess-1"
    assert e["payload"] == {"k": "v"}
    assert e["event_id"]


def test_strip_values_removes_payload_content():
    e = build_envelope("x", {"secret": "hunter2", "n": 42}, "r", "s")
    safe = strip_values_for_production(e)
    assert safe["payload"]["secret"] != "hunter2"
    assert "<str>" in safe["payload"]["secret"]
    assert "<int>" in safe["payload"]["n"]

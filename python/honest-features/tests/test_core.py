import time

import pytest

from honest_features import (
    assign_variant,
    build_signature,
    feature_state,
    feature_state_for_request,
    flag_vocabulary,
    init_state,
    select_handler,
    toggle_flag,
    update_state,
    validate_flag,
    validate_state_value,
    verify_signature,
)


def _vocab():
    return flag_vocabulary({
        "new_dashboard": {"states": ["on", "off"], "default_state": "off"},
        "theme":         {"states": ["light", "dark"], "default_state": "light"},
    })


def test_init_state_from_defaults():
    s = init_state(_vocab())
    assert s == {"new_dashboard": "off", "theme": "light"}


def test_validate_flag():
    v = _vocab()
    assert validate_flag("new_dashboard", v)
    assert not validate_flag("no_such_flag", v)


def test_validate_state_value():
    v = _vocab()
    assert validate_state_value("theme", "dark", v)
    assert not validate_state_value("theme", "rainbow", v)


def test_build_and_verify_signature():
    secret = b"supersecret"
    ts = int(time.time())
    sig = build_signature(secret, "new_dashboard", "on", ts)
    assert verify_signature(secret, "new_dashboard", "on", ts, sig)


def test_verify_signature_rejects_replay():
    secret = b"s"
    old_ts = int(time.time()) - 10_000
    sig = build_signature(secret, "f", "on", old_ts)
    assert not verify_signature(secret, "f", "on", old_ts, sig, replay_window_seconds=60)


def test_update_state_returns_new_dict():
    s = init_state(_vocab())
    s2 = update_state(s, "new_dashboard", "on")
    assert s["new_dashboard"] == "off"  # original untouched
    assert s2["new_dashboard"] == "on"


def test_feature_state_lookup():
    assert feature_state("new_dashboard", {"new_dashboard": "on"}) == "on"
    assert feature_state("absent", {}) == ""


def test_feature_state_for_request_uses_ab_assignment():
    assert feature_state_for_request(
        "exp_x", {"exp_x": "b"}, {"exp_x": "a"}
    ) == "b"


def test_select_handler_dispatches():
    h = {"on": lambda: "ON", "off": lambda: "OFF"}
    assert select_handler("on", h)() == "ON"


def test_select_handler_missing_raises():
    with pytest.raises(KeyError):
        select_handler("maybe", {})


def test_assign_variant_is_deterministic():
    v = flag_vocabulary({"exp": {"states": ["a", "b", "control"], "default_state": "control"}})
    first = assign_variant("exp", "user-42", v)
    second = assign_variant("exp", "user-42", v)
    assert first == second
    assert first in {"a", "b", "control"}


def test_toggle_happy_path():
    v = _vocab()
    current = init_state(v)
    secret = b"s"
    ts = int(time.time())
    sig = build_signature(secret, "new_dashboard", "on", ts)
    r = toggle_flag(
        {"flag": "new_dashboard", "state_value": "on", "timestamp": ts,
         "signature": sig, "requesting_ip": "127.0.0.1"},
        v, secret, current,
    )
    assert r["err_code"] == ""
    assert r["state_value"] == "on"
    assert r["previous"] == "off"


def test_toggle_unknown_flag():
    v = _vocab()
    r = toggle_flag(
        {"flag": "nope", "state_value": "x", "timestamp": 0,
         "signature": "", "requesting_ip": ""},
        v, b"s", {},
    )
    assert r["err_code"] == "unknown_flag"


def test_toggle_bad_state():
    v = _vocab()
    r = toggle_flag(
        {"flag": "theme", "state_value": "rainbow", "timestamp": 0,
         "signature": "", "requesting_ip": ""},
        v, b"s", {},
    )
    assert r["err_code"] == "invalid_state"


def test_toggle_bad_signature():
    v = _vocab()
    ts = int(time.time())
    r = toggle_flag(
        {"flag": "new_dashboard", "state_value": "on", "timestamp": ts,
         "signature": "not-a-real-sig", "requesting_ip": ""},
        v, b"s", init_state(v),
    )
    assert r["err_code"] == "bad_signature"

"""honest-features conformance laws: the vocabulary checks, the threaded state value, the toggle
conditions and change, the HMAC signature, and the honest-observe events.

The portable surface is value cases in suite.json (checked by value-check.py). These laws pin the same
functions for the per-module gate and drive 100% coverage: every branch of the vocabulary and toggle
checks, both ends of the replay window, and the signature round trip — which value cases cannot carry
because the secret is bytes. Pure assertions: data in, data out.
"""

from honest_features import (
    apply_toggle,
    build_signature,
    changed_event,
    evaluated_event,
    feature_state,
    initial_state,
    validate_toggle,
    validate_vocabulary,
    verify_signature,
)

_FEATURES = {
    "new_checkout": {"states": ["on", "off"], "initial_value": "off"},
    "pricing": {"states": ["a", "b", "control"], "initial_value": "control"},
}
_SECRET = b"shared-secret"


def _law_exports():
    import honest_features

    bad = []
    expected = [
        "validate_vocabulary",
        "initial_state",
        "feature_state",
        "validate_toggle",
        "apply_toggle",
        "build_signature",
        "verify_signature",
        "changed_event",
        "evaluated_event",
    ]
    if sorted(getattr(honest_features, "__all__", [])) != sorted(expected):
        bad.append(f"__all__ should be exactly the public surface: {getattr(honest_features, '__all__', None)}")
    missing = [name for name in expected if not hasattr(honest_features, name)]
    if missing:
        bad.append(f"__all__ names not importable: {missing}")
    return bad


def _law_validate_vocabulary():
    bad = []
    if validate_vocabulary(_FEATURES) != {"ok": _FEATURES}:
        bad.append(f"a valid vocabulary should pass: {validate_vocabulary(_FEATURES)}")
    too_few = validate_vocabulary({"f": {"states": ["on"], "initial_value": "on"}})
    if too_few.get("err", {}).get("code") != "invalid_vocabulary" or too_few["err"]["detail"] != ["f"]:
        bad.append(f"a flag with fewer than two states is invalid: {too_few}")
    if too_few.get("err", {}).get("message") != "flags violate the vocabulary rules: ['f']":
        bad.append(f"invalid_vocabulary message wrong: {too_few}")
    bad_initial = validate_vocabulary({"f": {"states": ["on", "off"], "initial_value": "x"}})
    if bad_initial.get("err", {}).get("code") != "invalid_vocabulary" or bad_initial["err"]["detail"] != ["f"]:
        bad.append(f"an initial_value outside the states is invalid: {bad_initial}")
    if bad_initial.get("err", {}).get("category") != "client":
        bad.append(f"an invalid vocabulary is a client fault: {bad_initial}")
    return bad


def _law_initial_state():
    bad = []
    if initial_state(_FEATURES) != {"new_checkout": "off", "pricing": "control"}:
        bad.append(f"initial_state should be each flag at its initial_value: {initial_state(_FEATURES)}")
    return bad


def _law_feature_state():
    bad = []
    if feature_state({"new_checkout": "on"}, "new_checkout") != "on":
        bad.append(f"feature_state should read the flag from the state value: {feature_state({'new_checkout': 'on'}, 'new_checkout')}")
    return bad


def _law_validate_toggle():
    bad = []
    if validate_toggle(_FEATURES, "new_checkout", "on") != {"ok": {"flag": "new_checkout", "state": "on"}}:
        bad.append(f"a declared flag and state should pass: {validate_toggle(_FEATURES, 'new_checkout', 'on')}")
    unknown = validate_toggle(_FEATURES, "ghost", "on")
    if unknown.get("err", {}).get("code") != "unknown_flag" or unknown["err"]["detail"] != "ghost":
        bad.append(f"an undeclared flag is unknown_flag: {unknown}")
    if unknown.get("err", {}).get("message") != "'ghost' is not a declared flag":
        bad.append(f"unknown_flag message wrong: {unknown}")
    if unknown.get("err", {}).get("category") != "client":
        bad.append(f"unknown_flag is a client fault: {unknown}")
    invalid = validate_toggle(_FEATURES, "new_checkout", "maybe")
    if invalid.get("err", {}).get("code") != "invalid_state" or invalid["err"]["detail"] != "maybe":
        bad.append(f"an undeclared state is invalid_state: {invalid}")
    if invalid.get("err", {}).get("message") != "'maybe' is not a state of 'new_checkout'":
        bad.append(f"invalid_state message wrong: {invalid}")
    if invalid.get("err", {}).get("category") != "client":
        bad.append(f"invalid_state is a client fault: {invalid}")
    return bad


def _law_apply_toggle():
    bad = []
    result = apply_toggle({"new_checkout": "off", "pricing": "control"}, "new_checkout", "on")
    if result != {"previous": "off", "state": {"new_checkout": "on", "pricing": "control"}}:
        bad.append(f"apply_toggle should return previous and a new state value: {result}")
    return bad


def _law_build_signature():
    bad = []
    import hashlib
    import hmac

    expected = hmac.new(_SECRET, b"new_checkout:on:1710000000", hashlib.sha256).hexdigest()
    if build_signature(_SECRET, "new_checkout", "on", 1710000000) != expected:
        bad.append("build_signature should be HMAC-SHA256 over '{flag}:{state}:{timestamp}'")
    return bad


def _law_verify_signature():
    bad = []
    sig = build_signature(_SECRET, "new_checkout", "on", 1710000000)
    if verify_signature(_SECRET, "new_checkout", "on", 1710000000, sig, now=1710000030) is not True:
        bad.append("a matching signature within the window verifies")
    if verify_signature(_SECRET, "new_checkout", "on", 1710000000, sig, now=1710000200) is not False:
        bad.append("a signature outside the replay window is rejected")
    if verify_signature(_SECRET, "new_checkout", "on", 1710000000, "deadbeef", now=1710000030) is not False:
        bad.append("a non-matching signature is rejected")
    # Boundaries of the default 60-second window: exactly 60 is still inside; 61 is the first reject.
    if verify_signature(_SECRET, "new_checkout", "on", 1710000000, sig, now=1710000060) is not True:
        bad.append("a signature exactly at the window edge (60s) still verifies")
    if verify_signature(_SECRET, "new_checkout", "on", 1710000000, sig, now=1710000061) is not False:
        bad.append("a signature one second past the window (61s) is rejected")
    return bad


def _law_changed_event():
    bad = []
    event = changed_event("new_checkout", "off", "on", 1710000000, "10.0.0.1")
    if event != {
        "event_type": "hf.features.changed",
        "flag": "new_checkout",
        "previous": "off",
        "state": "on",
        "timestamp": 1710000000,
        "requesting_ip": "10.0.0.1",
    }:
        bad.append(f"changed_event payload drifted: {event}")
    return bad


def _law_evaluated_event():
    bad = []
    event = evaluated_event("new_checkout", "on", "req_abc123")
    if event != {"event_type": "hf.features.evaluated", "flag": "new_checkout", "state": "on", "request_id": "req_abc123"}:
        bad.append(f"evaluated_event payload drifted: {event}")
    return bad


_LAWS = {
    "exports": _law_exports,
    "validate_vocabulary": _law_validate_vocabulary,
    "initial_state": _law_initial_state,
    "feature_state": _law_feature_state,
    "validate_toggle": _law_validate_toggle,
    "apply_toggle": _law_apply_toggle,
    "build_signature": _law_build_signature,
    "verify_signature": _law_verify_signature,
    "changed_event": _law_changed_event,
    "evaluated_event": _law_evaluated_event,
}


def run():
    violations = {name: law() for name, law in _LAWS.items()}
    failed = {name: msgs for name, msgs in violations.items() if msgs}
    passed = len(_LAWS) - len(failed)
    for name, msgs in failed.items():
        print(f"FAIL HF-law [{name}]: {msgs}")
    print(f"HF laws: {passed} passed, {len(failed)} failed, {len(_LAWS)} total")
    return 0 if not failed else 1

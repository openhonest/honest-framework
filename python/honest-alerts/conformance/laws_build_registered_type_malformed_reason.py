# scenario: build_registered_type rejects malformed registration with a corrective message
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_registered_type -> feature=specs/features/honest-alerts.feature::build_registered_type rejects malformed registration with a corrective message
"""Invalid registration shape reports its problem and both input requirements."""

from honest_alerts import build_registered_type

_TYPE = "approval.requested"
_CASES = [
    ("", ["v1"], None),
    ("approval", ["v1"], None),
    (".", ["v1"], None),
    (".requested", ["v1"], None),
    ("approval.", ["v1"], None),
    ("approval..requested", ["v1"], None),
    (_TYPE, [], {"message_type": _TYPE, "message_versions": ["v1"]}),
]


def probe_build_registered_type_malformed_reason():
    failures = []
    for message_type, versions, existing in _CASES:
        result = build_registered_type(message_type, versions, existing)
        message = result.get("message", "").casefold()
        reason, _, action = message.partition(";")
        if not action:
            reason = action = message
        explains_shape = "namespace" in reason and "version" in reason
        suggests_input = any(word in action for word in ("pass", "supply", "provide", "use"))
        suggests_namespace = "namespace" in action or _TYPE in action
        suggests_version = "version" in action and ("at least one" in action or "non-empty" in action)
        expected_detail = {"message_type": message_type, "message_versions": versions}
        if result.get("detail") != expected_detail:
            failures.append(f"invalid_registration detail must carry {expected_detail!r}, got {result.get('detail')!r}")
        if (result.get("is_err"), result.get("code"), result.get("category")) != (True, "invalid_registration", "client") or not (
            explains_shape and suggests_input and suggests_namespace and suggests_version
        ):
            failures.append(f"expected a malformed registration fault for {message_type!r} with {versions!r}, got {result!r}")
    return failures

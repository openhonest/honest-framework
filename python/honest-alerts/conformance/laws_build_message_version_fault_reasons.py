# scenario: build_message explains registration and version faults
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_message -> feature=specs/features/honest-alerts.feature::build_message explains registration and version faults
"""Version failures state the problem and the next action."""

from honest_alerts import build_message
from laws_build_message import _REGISTERED, _TERMINATION_OK, _given

_CASES = [
    ("v1", None, "unregistered_message_type", ("never registered", "unregistered"), ("register ", "call register_message_type")),
    (None, _REGISTERED, "missing_message_version", ("no message_version", "missing"), ("pass", "supply", "provide")),
    ("v9", _REGISTERED, "message_version_not_registered", ("outside", "not registered"), ("send ", "use ", "register ")),
]


def probe_build_message_version_fault_reasons():
    failures = []
    for version, registered, code, reasons, actions in _CASES:
        given = _given(version, registered, _TERMINATION_OK)
        result = build_message(**given)
        detail = result.get("detail")
        expected_detail = {"message_type": given["message_type"]}
        if code != "unregistered_message_type":
            expected_detail["message_version"] = version
        observed_detail = {key: detail[key] for key in expected_detail if key in detail} if isinstance(detail, dict) else detail
        if observed_detail != expected_detail:
            failures.append(f"expected {code} to carry {expected_detail!r} in detail, got {detail!r}")
        fault = (result.get("is_err"), result.get("code"), result.get("category"))
        reason, _, action = result.get("message", "").casefold().partition(";")
        if not action:
            reason = action = reason
        corrective = any(phrase in action for phrase in actions) and "register" in action
        if fault != (True, code, "client") or not any(phrase in reason for phrase in reasons) or not corrective:
            failures.append(f"expected {code} with its reason and corrective action, got {result!r}")
    return failures

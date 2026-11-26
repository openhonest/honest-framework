# scenario: is_terminated reports an unknown termination condition as a server fault
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::is_terminated -> feature=specs/features/honest-alerts.feature::is_terminated reports an unknown termination condition as a server fault
"""An unmatched condition in a received domain record is a program fault."""

from honest_alerts import is_terminated

from laws_is_terminated import _RECIP, _describes_no_match, _message, _termination

_UNKNOWN_CONDITION = "whenever"
_ACCEPTED = ["acknowledged", "event", "never", "ttl"]


def probe_is_terminated_unknown_condition():
    message = _message("m_unknown_condition", _RECIP, 1000, _termination(_UNKNOWN_CONDITION, None, None, None), "actor")
    result = is_terminated(message, _RECIP, 2000, [], None)
    if not isinstance(result, dict) or "ok" in result or "err" in result:
        return [f"expected a bare unknown_termination_condition server Fault, got {result!r}"]
    failures = []
    fault = (result.get("is_err"), result.get("code"), result.get("category"))
    if fault != (True, "unknown_termination_condition", "server"):
        failures.append(f"expected an unknown_termination_condition server Fault, got {result!r}")
    detail = result.get("detail")
    accepted = detail.get("accepted") if isinstance(detail, dict) else None
    if not isinstance(accepted, (list, tuple, set)) or sorted(accepted) != _ACCEPTED:
        failures.append(f"expected declared conditions {_ACCEPTED!r} in detail.accepted, got {detail!r}")
    if not isinstance(detail, dict) or detail.get("arrived") != _UNKNOWN_CONDITION:
        failures.append(f"expected {_UNKNOWN_CONDITION!r} in detail.arrived, got {detail!r}")
    message_text = result.get("message")
    if not _describes_no_match(message_text, _UNKNOWN_CONDITION, _ACCEPTED):
        failures.append(
            f"unknown_termination_condition must explain the unmatched value and name every accepted condition: {message_text!r}"
        )
    return failures

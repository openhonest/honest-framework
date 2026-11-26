# scenario: build_registered_type explains a conflicting registration and its remedies
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_registered_type -> feature=specs/features/honest-alerts.feature::build_registered_type explains a conflicting registration and its remedies
"""A refused re-registration identifies both records and gives both remedies."""

from honest_alerts import build_registered_type

_STORED = {"message_type": "approval.requested", "message_versions": ["v1", "v2"]}
_ARRIVING = {"message_type": "approval.requested", "message_versions": ["v3"]}


def probe_build_registered_type_conflict_reason():
    result = build_registered_type(_ARRIVING["message_type"], _ARRIVING["message_versions"], _STORED)
    fault = (result.get("is_err"), result.get("code"), result.get("category"))
    detail = result.get("detail")
    details_complete = detail == {"existing": _STORED, "arriving": _ARRIVING}
    message = result.get("message", "").casefold()
    conflict = "register" in message and ("different" in message or "conflict" in message)
    match_existing = "match" in message and ("stored" in message or "existing" in message)
    remove_existing = any(word in message for word in ("remove", "delete")) and (
        "existing" in message or "stored" in message
    )
    if fault != (True, "refused_registration", "client") or not (
        details_complete and conflict and match_existing and remove_existing
    ):
        return [f"expected a refusal identifying both registrations and both remedies, got {result!r}"]
    return []

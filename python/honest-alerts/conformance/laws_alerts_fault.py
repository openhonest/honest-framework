# scenario: alerts_fault
"""Red test for the alerts_fault scenario of honest-alerts (specs/features/honest-alerts.feature).

Scenario clause under test: alerts_fault "builds one honest-alerts Fault record from its parts,
the single place honest-alerts assembles a fault ... code is the specific reason; message is the
human sentence naming what went wrong and what to do instead; category is who is responsible, a
FaultCategory member client or server, never free text; detail is the structured context a test
reads without parsing the message ... it sets the reserved is_err tag true and returns the Fault,
carried by the return as a bare union arm and recognized by is_fault, never raised and never
wrapped in an ok/err envelope ... it is pure, reading no world."

The function is pure: data in, data out. The honest way to test it is to call the real function
and compare its whole returned record to a literal Fault written out in the case data. The
honest-alerts Fault schema (honest-alerts.hd type Fault, honest-type's canonical fault field for
field) is exactly six fields: is_err (always true), code, message, category, results, detail.
alerts_fault takes no results parameter, and the .hd says "results is [] except where a function
accumulates many results"; alerts_fault accumulates none, so results is [] explicitly.

Signature (explorer module_ir, role fn, raises []):
    alerts_fault(code: str, message: str, category: FaultCategory, detail: dict<str, any>) -> Fault

No oracle recomputed from the function under test: every expected record is a literal, so a stub
such as `return {}` (or `return []`, or `return None`) fails every behavioural case below.
"""

from honest_alerts import alerts_fault


def _is_fault(value):
    """True when value carries the reserved is_err tag set true (honest-alerts.hd type Fault; the
    tag honest-type's is_fault reads to tell the fault arm from the value arm). Read directly off
    the returned record; nothing recomputed from alerts_fault, so this is not a circular oracle."""
    if isinstance(value, dict):
        return value.get("is_err") is True
    return getattr(value, "is_err", None) is True


# Each row states the full input and the exact Fault record the output must equal. One client case
# and one server case pin the category as carried data (never free text, never defaulted), using
# codes from the section 6b table named in the scenario: message_version_not_registered (client),
# append_failed (server). The third row pins the empty-detail boundary: detail {} is carried
# through unchanged and results is [] explicitly, not defaulted. Every expected record is a
# literal, non-trivial value written out here, so an empty implementation fails each one.
_CASES = [
    {
        "name": "client-fault-message_version_not_registered",
        "given": {
            "code": "message_version_not_registered",
            "message": "message_version is outside the registered closed set for this message_type; register the version or send a registered one.",
            "category": "client",
            "detail": {"message_type": "approval.requested", "message_version": "v9"},
        },
        "expect": {
            "is_err": True,
            "code": "message_version_not_registered",
            "message": "message_version is outside the registered closed set for this message_type; register the version or send a registered one.",
            "category": "client",
            "results": [],
            "detail": {"message_type": "approval.requested", "message_version": "v9"},
        },
    },
    {
        "name": "server-fault-append_failed",
        "given": {
            "code": "append_failed",
            "message": "The alert.sent append to the event log failed; the send was rolled back.",
            "category": "server",
            "detail": {"message_id": "m-1"},
        },
        "expect": {
            "is_err": True,
            "code": "append_failed",
            "message": "The alert.sent append to the event log failed; the send was rolled back.",
            "category": "server",
            "results": [],
            "detail": {"message_id": "m-1"},
        },
    },
    {
        "name": "empty-detail-carried-not-defaulted",
        "given": {
            "code": "approval_timeout",
            "message": "The send_and_wait reply window closed with no reply.",
            "category": "server",
            "detail": {},
        },
        "expect": {
            "is_err": True,
            "code": "approval_timeout",
            "message": "The send_and_wait reply window closed with no reply.",
            "category": "server",
            "results": [],
            "detail": {},
        },
    },
]


def probe_alerts_fault():
    """alerts_fault builds one Fault record from its parts: the reserved is_err tag set true, and
    code, message, category and detail carried through unchanged, results [], recognized by
    is_fault, returned never raised."""
    bad = []
    for case in _CASES:
        try:
            got = alerts_fault(**case["given"])
        except Exception as exc:  # it is pure and never raises; a raise is itself a contract fault
            bad.append(
                f"alerts_fault({case['name']}) raised {type(exc).__name__}: {exc}; "
                f"it must return a Fault, never raise"
            )
            continue
        if not _is_fault(got):
            bad.append(
                f"alerts_fault({case['name']}) -> {got!r}; expected a Fault arm with is_err true "
                f"(the reserved tag is_fault recognizes)"
            )
        if got != case["expect"]:
            bad.append(
                f"alerts_fault({case['name']}) -> {got!r}, expected {case['expect']!r}"
            )
    return bad


if __name__ == "__main__":
    failures = probe_alerts_fault()
    for line in failures:
        print(line)
    raise SystemExit(1 if failures else 0)

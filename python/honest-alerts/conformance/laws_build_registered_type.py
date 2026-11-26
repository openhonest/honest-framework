# scenario: build_registered_type
# inherits: hd=python/honest-alerts/honest-alerts.hd::build_registered_type -> feature=specs/features/honest-alerts.feature::build_registered_type
"""Red test fragment for the build_registered_type scenario (honest-alerts, section 3b.1/3b.3, 6b).

Honest, data-driven, pure. Cases are rows: each row an input and the output it must
produce. One pure probe feeds each row to the real build_registered_type (imported and
called, no mock, no patched boundary) and returns a list of failure strings, empty when
the case holds. No classes, no hidden state; records are plain dicts built field by field.

build_registered_type(message_type: str, message_versions: list<str>, existing: RegisteredType | NOTHING)
  -> RegisterDecision | Fault     (pure, no conn, never raises)

What the scenario (feature lines 70-78) fixes:
  - existing is NOTHING (the type was never registered)
        -> RegisterDecision {action: "write", registered_type: the arriving record}.
  - existing is a stored record and the arriving WHOLE declaration (message_type and its
    message_versions set taken whole) is byte-identical to it
        -> RegisterDecision {action: "noop", registered_type: the stored record}.
  - existing is a stored record and the arriving declaration differs in any way
        -> client Fault, code "refused_registration" (section 6b), whose detail names the
           existing declaration against the arriving one (both message_type values and both
           message_versions sets).
  - empty message_versions set  -> client Fault, before any re-registration comparison.
  - malformed (non-dot-namespaced or empty) message_type -> client Fault, before any comparison.

NOTHING, the module-owned absence for "never registered", is written out explicitly as None
below; the declaration types `existing` as `RegisteredType | NOTHING` and this scenario's
absence case is its own explicit row, never left to a default.

A RegisterDecision is a plain record {action, registered_type}; a RegisteredType is
{message_type, message_versions}; a Fault is the honest-type fault dict carrying is_err=True,
a code, a category and a detail, recognised by the reserved is_err tag (honest-type §13.2).

One builder, table-driven. A RegisteredType and a RegisterDecision are both two-field
records differing only in their field names; rather than two shape-identical builders, a
single `_record(shape, a, b)` reads the field-name pair for the named shape from `_SHAPES`
and pastes the two values in. The shape table carries the words; the function carries none.
"""

from honest_alerts import build_registered_type

# NOTHING written out as the explicit absence literal this scenario names (constraint: no default).
NOTHING = None

# Each shape is a two-field record; the row carries the field names the one builder pastes in.
_SHAPES = {
    "registered_type": ("message_type", "message_versions"),
    "decision": ("action", "registered_type"),
}


def _record(shape, first, second):
    """Build the named two-field record. Every field explicit, no default kwargs, no class.

    The field names live in `_SHAPES`, not in branches here, so there is one builder over a
    table instead of two shape-identical ones.
    """
    field_a, field_b = _SHAPES[shape]
    return {field_a: first, field_b: second}


def _is_fault(value):
    """The fault arm of the bare union, recognised by the reserved is_err tag (honest-type §13.2)."""
    return isinstance(value, dict) and value.get("is_err") is True


# Each row is one input and the RegisterDecision it must produce. The behaviour is in the data.
# Both rows pin a concrete, non-trivial literal output the scenario fixes -- a stub returning
# {} or a Fault fails both, so the probe is not vacuous.
_DECISION_CASES = [
    {
        "name": "first registration (existing NOTHING) -> write arriving record",
        "given": {
            "message_type": "approval.requested",
            "message_versions": ["v1", "v2"],
            "existing": NOTHING,
        },
        "expect": _record(
            "decision",
            "write",
            _record("registered_type", "approval.requested", ["v1", "v2"]),
        ),
    },
    {
        "name": "byte-identical re-registration -> noop stored record",
        "given": {
            "message_type": "approval.requested",
            "message_versions": ["v1", "v2"],
            "existing": _record("registered_type", "approval.requested", ["v1", "v2"]),
        },
        "expect": _record(
            "decision",
            "noop",
            _record("registered_type", "approval.requested", ["v1", "v2"]),
        ),
    },
]

# Fault rows. The differing-re-registration row pins the spec-fixed code "refused_registration"
# (section 6b) and the detail naming both declarations. The empty-set and malformed rows pin the
# arm (a client Fault) and the client category, which the scenario fixes; the scenario does not
# name their codes, so no code is asserted for them (recorded as a gap).
_FAULT_CASES = [
    {
        "name": "empty message_versions -> client Fault before any comparison",
        "given": {
            "message_type": "approval.requested",
            "message_versions": [],
            "existing": NOTHING,
        },
        "expect_code": None,  # scenario fixes the arm + category only, not the code
    },
    {
        "name": "malformed (non-dot-namespaced) message_type -> client Fault",
        "given": {
            "message_type": "approvalrequested",
            "message_versions": ["v1"],
            "existing": NOTHING,
        },
        "expect_code": None,
    },
    {
        "name": "malformed (empty) message_type -> client Fault",
        "given": {
            "message_type": "",
            "message_versions": ["v1"],
            "existing": NOTHING,
        },
        "expect_code": None,
    },
    {
        "name": "differing re-registration -> refused_registration client Fault naming existing vs arriving",
        "given": {
            "message_type": "approval.requested",
            "message_versions": ["v1", "v3"],
            "existing": _record("registered_type", "approval.requested", ["v1", "v2"]),
        },
        "expect_code": "refused_registration",  # spec section 6b, fixed
        # the detail must name both declarations so the caller sees what differs
        "detail_records": [
            _record("registered_type", "approval.requested", ["v1", "v2"]),
            _record("registered_type", "approval.requested", ["v1", "v3"]),
        ],
    },
]


def probe_build_registered_type():
    """build_registered_type returns a write RegisterDecision for a first registration, a noop
    RegisterDecision for a byte-identical re-registration, and a client Fault for a refused
    (differing, code refused_registration, detail naming existing vs arriving), empty or
    malformed declaration -- pure, no world, never raising."""
    bad = []

    for case in _DECISION_CASES:
        got = build_registered_type(**case["given"])
        if _is_fault(got):
            bad.append(f"{case['name']}: expected RegisterDecision, got Fault {got!r}")
            continue
        if got != case["expect"]:
            bad.append(
                f"{case['name']}: build_registered_type({case['given']!r}) -> {got!r}, "
                f"expected {case['expect']!r}"
            )

    for case in _FAULT_CASES:
        got = build_registered_type(**case["given"])
        if not _is_fault(got):
            bad.append(f"{case['name']}: expected a client Fault, got {got!r}")
            continue
        if got.get("category") != "client":
            bad.append(
                f"{case['name']}: fault category -> {got.get('category')!r}, expected 'client'"
            )
        expect_code = case.get("expect_code")
        if expect_code is not None and got.get("code") != expect_code:
            bad.append(
                f"{case['name']}: fault code -> {got.get('code')!r}, expected {expect_code!r}"
            )
        if "detail_records" in case:
            detail = got.get("detail")
            if not isinstance(detail, dict) or any(
                declaration not in detail.values() for declaration in case["detail_records"]
            ):
                bad.append(f"{case['name']}: expected both complete registration records, got {detail!r}")
            message = got.get("message", "")
            if "match the stored" not in message and "remove the existing" not in message:
                bad.append(f"{case['name']}: fault message does not give the declared correction: {message!r}")
            repeated = build_registered_type(**case["given"])
            if repeated != got:
                bad.append(f"{case['name']}: repeating the same refusal changed the response to {repeated!r}")

    return bad


if __name__ == "__main__":
    import sys

    failures = probe_build_registered_type()
    if failures:
        for line in failures:
            print("FAIL:", line)
        sys.exit(1)
    print("ok: build_registered_type probe passed")

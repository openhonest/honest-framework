# scenario: advance
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::advance -> feature=specs/features/honest-alerts.feature::advance
"""Red test for the advance scenario of honest-alerts (specs/features/honest-alerts.feature).

Scenario clause under test:
  "it is the pure message-lifecycle transition function: given the current AlertState and an
   AlertEvent it returns the next AlertState when the pair names a declared transition ... the
   declared transitions are exactly: created deliver->delivered, created fail->failed, created
   expire->expired; delivered read->read, delivered acknowledge->acknowledged, delivered
   action->actioned, delivered escalate->escalated, delivered expire->expired; read
   acknowledge->acknowledged, read action->actioned, read escalate->escalated, read
   expire->expired; escalated acknowledge->acknowledged, escalated action->actioned, escalated
   expire->expired. acknowledged, actioned, expired and failed are terminal: any event from them
   is undeclared. An event undeclared from the given state returns a Fault via alerts_fault with
   category server. It is pure, a state and an event in and the next state or a fault out, reached
   by import, consulting no exposed object."

The .hd signature is advance : (state: AlertState, event: AlertEvent) -> AlertState | Fault, a
BARE union: on a declared transition it returns the next AlertState value directly (the string
member of alert_states, e.g. "delivered"), not an ok/err envelope; on an undeclared (state, event)
pair it returns a Fault whose reserved is_err tag is true, whose category is the FaultCategory
member "server", and whose code is "invalid_transition" (the section 6b server code the .hd names
for advance's undeclared-transition fault, honest-alerts.hd alerts_fault note line).

AlertState and AlertEvent are closed vocabularies whose members are the string values recorded in
the alert_states / alert_events sets (honest-alerts.hd). The probe states each (state, event) pair
and the exact next-state literal it must produce, taken straight from the scenario's declared-
transition list, and pins the fault code and category for the undeclared pairs -- no value is
recomputed from advance itself, so this is not a circular oracle.
"""

from honest_alerts import advance


def _call(state, event):
    """Call the real advance once. Returns ('value', v) with what it returned, or ('raised', e) if
    it raised. Under the scenario advance is pure -- a state and an event in, the next state or a
    fault out -- so a raise is itself a failure of the contract and is recorded, never swallowed."""
    try:
        return ("value", advance(state, event))
    except Exception as exc:  # advance must not raise; it returns the next state or a Fault
        return ("raised", exc)


def _is_fault(value):
    """True when value is the honest-alerts Fault arm: a record carrying the reserved is_err tag set
    true (honest-alerts.hd type Fault). Read directly off the returned value; nothing is recomputed
    from advance, so this is not a circular oracle."""
    if isinstance(value, dict):
        return value.get("is_err") is True
    return getattr(value, "is_err", None) is True


def _field(value, name):
    """Read a named field off a Fault record (dict or object), or None if absent."""
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


# Every declared transition from the scenario, each pinning the exact next AlertState literal.
_DECLARED = [
    {"given": {"state": "created", "event": "deliver"}, "expect": "delivered"},
    {"given": {"state": "created", "event": "fail"}, "expect": "failed"},
    {"given": {"state": "created", "event": "expire"}, "expect": "expired"},
    {"given": {"state": "delivered", "event": "read"}, "expect": "read"},
    {"given": {"state": "delivered", "event": "acknowledge"}, "expect": "acknowledged"},
    {"given": {"state": "delivered", "event": "action"}, "expect": "actioned"},
    {"given": {"state": "delivered", "event": "escalate"}, "expect": "escalated"},
    {"given": {"state": "delivered", "event": "expire"}, "expect": "expired"},
    {"given": {"state": "read", "event": "acknowledge"}, "expect": "acknowledged"},
    {"given": {"state": "read", "event": "action"}, "expect": "actioned"},
    {"given": {"state": "read", "event": "escalate"}, "expect": "escalated"},
    {"given": {"state": "read", "event": "expire"}, "expect": "expired"},
    {"given": {"state": "escalated", "event": "acknowledge"}, "expect": "acknowledged"},
    {"given": {"state": "escalated", "event": "action"}, "expect": "actioned"},
    {"given": {"state": "escalated", "event": "expire"}, "expect": "expired"},
]

# Undeclared (state, event) pairs: every event from a terminal state, plus events not declared from
# a non-terminal state. Each must return a Fault with code "invalid_transition" and category
# "server", never a next state. These are the explicit "undeclared returns a Fault" cases the
# scenario names -- the absence/boundary rows.
_UNDECLARED = [
    # terminal states: any event from them is undeclared
    {"given": {"state": "acknowledged", "event": "deliver"}},
    {"given": {"state": "acknowledged", "event": "acknowledge"}},
    {"given": {"state": "actioned", "event": "acknowledge"}},
    {"given": {"state": "expired", "event": "read"}},
    {"given": {"state": "failed", "event": "deliver"}},
    # non-terminal states, events not in their declared set
    {"given": {"state": "created", "event": "read"}},          # created has no read transition
    {"given": {"state": "created", "event": "acknowledge"}},   # created has no acknowledge
    {"given": {"state": "delivered", "event": "fail"}},        # fail is only from created
    {"given": {"state": "read", "event": "deliver"}},          # cannot re-deliver a read message
    {"given": {"state": "escalated", "event": "read"}},        # read is not declared from escalated
]

# The exact fault shape an undeclared transition must produce (honest-alerts.hd section 6b).
_UNDECLARED_CODE = "invalid_transition"
_UNDECLARED_CATEGORY = "server"


def probe_advance():
    """advance returns, as a bare union arm, the exact next AlertState for each declared (state,
    event) transition, and a Fault with code 'invalid_transition' and category 'server' (is_err
    true) for every undeclared pair including any event from a terminal state -- a state and an
    event in, the next state or a fault out."""
    bad = []

    for case in _DECLARED:
        given = case["given"]
        kind, got = _call(given["state"], given["event"])
        if kind == "raised":
            bad.append(
                f"advance({given['state']!r}, {given['event']!r}) raised "
                f"{type(got).__name__}: {got}; a declared transition must return the next "
                f"AlertState {case['expect']!r}, never raise"
            )
            continue
        if got != case["expect"]:
            bad.append(
                f"advance({given['state']!r}, {given['event']!r}) -> {got!r}, "
                f"expected the next AlertState {case['expect']!r} as a bare union arm"
            )

    for case in _UNDECLARED:
        given = case["given"]
        kind, got = _call(given["state"], given["event"])
        if kind == "raised":
            bad.append(
                f"advance({given['state']!r}, {given['event']!r}) raised "
                f"{type(got).__name__}: {got}; an undeclared transition must return a Fault "
                f"(code {_UNDECLARED_CODE!r}, category {_UNDECLARED_CATEGORY!r}), never raise"
            )
            continue
        if not _is_fault(got):
            bad.append(
                f"advance({given['state']!r}, {given['event']!r}) -> {got!r}, "
                f"expected a Fault (is_err true) for an undeclared transition"
            )
            continue
        code = _field(got, "code")
        if code != _UNDECLARED_CODE:
            bad.append(
                f"advance({given['state']!r}, {given['event']!r}) returned a Fault with "
                f"code {code!r}, expected {_UNDECLARED_CODE!r}"
            )
        cat = _field(got, "category")
        if cat != _UNDECLARED_CATEGORY:
            bad.append(
                f"advance({given['state']!r}, {given['event']!r}) returned a Fault with "
                f"category {cat!r}, expected FaultCategory {_UNDECLARED_CATEGORY!r}"
            )

    return bad


if __name__ == "__main__":
    failures = probe_advance()
    for line in failures:
        print(line)
    raise SystemExit(1 if failures else 0)

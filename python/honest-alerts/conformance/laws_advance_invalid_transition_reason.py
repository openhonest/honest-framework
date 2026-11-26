# scenario: advance explains an undeclared lifecycle transition
# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::advance -> feature=specs/features/honest-alerts.feature::advance explains an undeclared lifecycle transition
"""Undeclared transitions name the attempted state and event and explain the lifecycle rule."""

from honest_alerts import advance

_CASES = [("acknowledged", "acknowledge"), ("created", "read")]


def probe_advance_invalid_transition_reason():
    failures = []
    for state, event in _CASES:
        result = advance(state, event)
        fault = (result.get("is_err"), result.get("code"), result.get("category"))
        expected_detail = {"state": state, "event": event}
        if result.get("detail") != expected_detail:
            failures.append(f"expected invalid_transition detail {expected_detail!r}, got {result.get('detail')!r}")
        message = result.get("message", "").casefold()
        words = message.replace("'", " ").replace('"', " ").replace(",", " ").split()
        names_pair = state in words and event in words
        declared_only = all(word in message for word in ("only", "declared", "advance"))
        terminal = "terminal" in message and ("no event" in message or "cannot" in message)
        if fault != (True, "invalid_transition", "server") or not (names_pair and declared_only and terminal):
            failures.append(f"expected a lifecycle fault explaining {state!r} with {event!r}, got {result!r}")
    return failures

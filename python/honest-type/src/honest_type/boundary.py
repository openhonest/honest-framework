"""Fault and rejection semantics at the boundary (section 13).

This module IS the boundary (section 13.4): the one place that catches the host handler's
exception and turns faults into output. Catching belongs at the boundary (Typed Exceptions
at the Boundary), so the one catch carries an inline `# honest: ignore HC-P002` on its try,
naming why. Everything it routes with is a table lookup, never a branch: `fault_to_output`
maps fault codes to output functions, and category picks the default.
"""

from honest_type._util import _choose, _pick, _read_or
from honest_type.types import fault, is_fault

# Rejection policy (section 11.5): the single point where "proceed with a manifest that
# has rejections?" is decided. A reason not listed blocks by default — an unknown rejection
# is never silently passed.
DEFAULT_REJECTION_POLICY = {
    "unrecognized": "fault",
    "missing_required": "fault",
    "duplicate_slot": "fault",
    "empty_token": "warn",
    "null_token": "warn",
}

# Rejection reason -> fault category (section 11.3 registry). Most rejections are bad
# input (client), but unbound_type and reserved_word signal a misconfiguration, so at the
# boundary they surface as server faults, not client ones. A reason not listed is client.
_REJECTION_CATEGORY = {
    "unbound_type": "server",
    "reserved_word": "server",
}


def catch_at_boundary(handler, fault_to_output, success_output, server_default, client_default):
    """Wrap a handler (section 13.4): on a value, render success; on a Fault, render via the
    fault_to_output table, falling back to the category default; on an unhandled exception,
    render a server fault. The wrapper holds no conditional logic beyond the Fault recognizer —
    routing is a lookup."""

    def wrapped(value):
        try:  # honest: ignore HC-P002: the boundary catches the host handler's throw and renders it as a server default (section 13.4)
            result = handler(value)
        except Exception as exc:
            return server_default(fault("unhandled_exception", str(exc), "server", [], {}))
        return _pick(
            is_fault(result),
            lambda: _read_or(
                fault_to_output,
                result["code"],
                _read_or({"server": server_default, "client": client_default}, result["category"], server_default),
            )(result),
            lambda: success_output(result),
        )

    return wrapped


def check_rejections(manifest, policy=None) -> dict:
    """Screen a manifest's rejections before the chain runs (section 13.5), returning a bare
    manifest or a bare Fault. Any rejection the policy marks "fault" (or does not list) blocks,
    yielding a client fault; otherwise the manifest is returned clean, with `_rejections` stripped —
    inside the chain there are no rejections."""
    rules = _choose(policy is not None, policy, DEFAULT_REJECTION_POLICY)
    rejections = _read_or(manifest, "_rejections", [])
    blocking = list(filter(lambda r: _read_or(rules, r["reason"], "fault") == "fault", rejections))
    clean = dict(filter(lambda slot_value: slot_value[0] != "_rejections", manifest.items()))
    return _pick(
        bool(blocking),
        lambda: fault(
            blocking[0]["reason"],
            "Input rejected at the boundary",
            _read_or(_REJECTION_CATEGORY, blocking[0]["reason"], "client"),
            [],
            {"rejections": blocking},
        ),
        lambda: clean,
    )

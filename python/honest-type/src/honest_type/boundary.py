"""Fault and rejection semantics at the boundary (section 11).

This module IS the boundary (section 11.4): the one place that catches exceptions and
turns faults into output. Catching belongs at the boundary (Typed Exceptions at the
Boundary), so HC-P002 is disabled file-wide here — the same declaration the cli boundary
makes. Everything it routes with is a table lookup, never a branch: `fault_to_output`
maps fault codes to output functions, and category picks the default.
"""

# honest: disable HC-P002: the boundary turns a rejected input into a fault value, which is what a boundary is for

from honest_type.types import err, fault, ok

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
    """Wrap a handler (section 11.4): on ok, render success; on a fault, render via the
    fault_to_output table, falling back to the category default; on an unhandled exception,
    render a server fault. The wrapper holds no conditional logic beyond ok/err detection —
    routing is a lookup."""

    def wrapped(value):
        try:
            result = handler(value)
        except Exception as exc:
            return server_default(fault("unhandled_exception", str(exc), "server"))
        if "err" in result:
            failure = result["err"]
            category_default = {"server": server_default, "client": client_default}.get(
                failure["category"], server_default
            )
            return fault_to_output.get(failure["code"], category_default)(failure)
        return success_output(result["ok"])

    return wrapped


def check_rejections(manifest, policy=None) -> dict:
    """Convert manifest rejections to a Result before the chain runs (section 11.5). Any
    rejection the policy marks "fault" (or does not list) blocks, yielding a client fault;
    otherwise the manifest is returned clean, with `_rejections` stripped — inside the chain
    there are no rejections."""
    rules = policy if policy is not None else DEFAULT_REJECTION_POLICY
    rejections = manifest.get("_rejections", [])
    blocking = [r for r in rejections if rules.get(r["reason"], "fault") == "fault"]
    clean = {slot: value for slot, value in manifest.items() if slot != "_rejections"}
    if blocking:
        reason = blocking[0]["reason"]
        return err(
            fault(
                reason,
                "Input rejected at the boundary",
                _REJECTION_CATEGORY.get(reason, "client"),
                {"rejections": blocking},
            )
        )
    return ok(clean)

"""The boundary (spec §11.4, §11.5).

The boundary is the only place faults become output. The pattern is identical
in every context (HTTP, CLI, queue, ETL): a lookup table maps fault code ->
output function. honest-type ships the generic, pure pattern; spokes supply
the context-specific output functions and tables.

Rejections live inside the manifest (`_rejections`); `apply_rejection_policy`
is the one place that decides whether to proceed or convert them to a fault.
"""
from __future__ import annotations

from typing import Callable

from honest_type.result import err, fault, is_err, ok


def catch_at_boundary(
    handler: Callable,
    fault_to_output: dict,
    success_output: Callable,
    server_default: Callable,
    client_default: Callable,
) -> Callable:
    """Wrap a handler so its Result becomes context output. Unhandled
    exceptions become a server `unhandled_exception` fault (spec §11.4)."""
    def wrapped(input):
        try:
            result = handler(input)
            if is_err(result):
                f = result["err"]
                default = server_default if f["category"] == "server" else client_default
                output = fault_to_output.get(f["code"], default)
                return output(f)
            return success_output(result["ok"])
        except Exception as exc:
            return server_default(fault(
                "unhandled_exception",
                str(exc),
                category="server",
            ))
    return wrapped


# Default rejection policy (spec §11.5): which reasons stop, which warn.
DEFAULT_REJECTION_POLICY: dict[str, str] = {
    "unrecognized":     "fault",
    "missing_required": "fault",
    "duplicate_slot":   "fault",
    "unbound_type":     "fault",
    "reserved_word":    "fault",
    "empty_token":      "warn",
    "null_token":       "warn",
}


def apply_rejection_policy(manifest: dict, policy: dict | None = None) -> dict:
    """Inspect `_rejections` and decide proceed-or-fault (spec §11.5). Returns
    a Result: err(validation fault) if any rejection's policy is "fault", else
    ok(manifest). The clean manifest entering a chain has no rejections."""
    if policy is None:
        policy = DEFAULT_REJECTION_POLICY
    rejections = manifest.get("_rejections", [])
    blocking = [r for r in rejections if policy.get(r["reason"], "fault") == "fault"]
    if blocking:
        first = blocking[0]
        return err(fault(
            first["reason"],
            f"input rejected: {first['reason']}",
            category="client",
            detail={"rejections": blocking},
        ))
    return ok(manifest)

"""The taxonomy of state kinds (section 1.2), as data.

There is no "the state": every piece of state belongs to exactly one kind, and every kind names exactly
one mutator and the store it lives in. honest-state ships that taxonomy as data — the canonical kind ->
(store, mutator) mapping — and a lookup. The mechanics of each kind live in its home module (honest-DOM,
honest-type, honest-alerts, honest-persist); honest-state only states which mutator owns which kind. Pure.
"""

from honest_type import err, fault, ok

# Section 1.2 — the nine kinds of state, each with its store and its single mutator. This is the
# normative taxonomy; the acceptance test for a row is "can you name exactly one mutator?".
_STATE_KINDS = (
    {"kind": "user", "lives_in": "manifest-declared regions of the DOM", "mutator": "the user"},
    {"kind": "server", "lives_in": "non-declared regions of the DOM", "mutator": "the alert source (honest-alerts)"},
    {"kind": "session", "lives_in": "a shared store (scale-out)", "mutator": "the auth provider"},
    {"kind": "domain", "lives_in": "the database", "mutator": "an ordinary honest-persist boundary write"},
    {"kind": "cache", "lives_in": "at an I/O boundary", "mutator": "refresh-from-source"},
    {"kind": "transient", "lives_in": "the chain manifest, in-memory", "mutator": "a link's return value"},
    {"kind": "static_config", "lives_in": "process memory, frozen at startup", "mutator": "startup"},
    {"kind": "dynamic_config", "lives_in": "an external flag store", "mutator": "the flag service"},
    {"kind": "contended", "lives_in": "behind a queue", "mutator": "the queue's single consumer"},
)


def state_kinds():
    """The taxonomy of state kinds (section 1.2): each kind with its store and single mutator. Pure."""
    return [dict(row) for row in _STATE_KINDS]


def mutator_of(kind):
    """The single mutator that owns a state kind (section 1.2): ok(mutator) for a known kind, else
    err(unknown_state_kind). Pure."""
    for row in _STATE_KINDS:
        if row["kind"] == kind:
            return ok(row["mutator"])
    return err(fault("unknown_state_kind", f"'{kind}' is not a declared kind of state", "client", detail=kind))


def dom_region_kind(declared, server_driven):
    """Decompose a DOM region under the single-mutator law (section 1.3). The DOM is not one store; each
    part of it is either declared state with exactly one mutator, or a pure projection of state. A
    manifest-declared region is user state, whose single mutator is the user — a server round-trip (HTMX
    swap) and an in-browser change are two mechanisms of that one mutator, not two mutators, so declared
    wins even when the server also touches the page. A non-declared, server/SSE-driven region is server
    state, whose mutator is the alert source — a legitimate second mutator of the DOM because it is
    honest and disjoint, never touching a manifest slot. Anything else is a side effect: a projection of
    the two above with no mutator of its own, re-derived and never written. Returns the kind and its
    mutator (None for a projection). Pure."""
    if declared:
        return {"kind": "user", "mutator": "the user"}
    if server_driven:
        return {"kind": "server", "mutator": "the alert source (honest-alerts)"}
    return {"kind": "side_effect", "mutator": None}

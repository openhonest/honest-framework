"""The taxonomy of state kinds and the mutator lookup (honest-state-architecture.md §1.2).

The ten kinds of state are a fixed, closed set. Each row carries the spec's three columns: the kind
word, where that kind lives (store), and the one piece of code allowed to change it (mutator). The
acceptance test of §1.2 — every kind names exactly one mutator — is true by construction here: every
row carries one mutator string.
"""

from typing import TypedDict


class StateKind(TypedDict):
    """One row of the §1.2 taxonomy: the kind word, its home store, and its single mutator."""

    kind: str
    store: str
    mutator: str


def state_kinds() -> list[StateKind]:
    """Return the whole §1.2 taxonomy as data: one row per state kind, ten rows, each naming its
    kind, its home store and its single mutator. Takes no argument and reads nothing — the taxonomy
    is a fixed table of literals."""
    return [
        {"kind": "individual_user",   "store": "manifest-declared regions of the DOM",                                         "mutator": "the user (any user-initiated action)"},
        {"kind": "server_sse",        "store": "non-declared regions of the DOM (alerts/notifications)",                       "mutator": "the server / alert source (honest-alerts)"},
        {"kind": "shared_session",    "store": "a shared store (scale-out)",                                                   "mutator": "the auth provider"},
        {"kind": "persisted_domain",  "store": "the database",                                                                "mutator": "an ordinary boundary write (honest-persist insert/update/delete at the I/O boundary)"},
        {"kind": "cache",             "store": "at / preferably across an I/O boundary",                                       "mutator": "refresh-from-source (only write)"},
        {"kind": "transient_request", "store": "the chain (the manifest), in-memory",                                         "mutator": "a link's return value (functional threading)"},
        {"kind": "static_config",     "store": "process memory, frozen at startup",                                           "mutator": "startup (then read-only)"},
        {"kind": "dynamic_config",    "store": "an external flag store",                                                      "mutator": "the flag service (app only reads)"},
        {"kind": "contended_writes",  "store": "on the other side of a queue",                                                "mutator": "the queue's single consumer"},
        {"kind": "composed_value",    "store": "held by the orchestrator in memory, persisted when it must survive a restart", "mutator": "the orchestrator (it applies each pure function's return)"},
    ]


def mutator_of(kind: str) -> str:
    """Map a state-kind name to the one mutator allowed to change that kind of state (§1.2). kind is
    one of the ten StateKindName words, so the lookup resolves to exactly one row — no miss, no fault.
    Reads the taxonomy through state_kinds rather than keeping a second copy of it; the lookup is a
    dict built from the rows, not an if/elif ladder."""
    return {row["kind"]: row["mutator"] for row in state_kinds()}[kind]

"""The DOM decomposition (honest-state-architecture.md §1.3).

Every part of the DOM is exactly one of three sources, and each source maps to one classification. The
mapping is table data, not control flow: the three handlers are named and counted, and classify_dom_region
dispatches a region's source through the table. source is one of the three RegionSource words, so the
lookup resolves to exactly one handler — no miss, no fault.
"""


def user_state_region() -> str:
    """The dom_region_dispatch handler for a manifest-declared region: the fixed classification
    'user_state' (§1.3), whose single mutator is the user."""
    return "user_state"


def server_state_region() -> str:
    """The dom_region_dispatch handler for a server/SSE-driven region: the fixed classification
    'server_state' (§1.3), whose single mutator is the server / alert source, a legitimate second
    mutator of the DOM (honest and disjoint)."""
    return "server_state"


def side_effect_region() -> str:
    """The dom_region_dispatch handler for any other region: the fixed classification 'side_effect'
    (§1.3), a derived projection of user state and server state with no mutator of its own,
    re-derived and never written."""
    return "side_effect"


dom_region_dispatch = {
    "manifest_declared": user_state_region,
    "server_driven": server_state_region,
    "other": side_effect_region,
}


def classify_dom_region(source: str) -> str:
    """Classify a region of the DOM by its source into exactly one of three kinds (§1.3), dispatching
    the source word through dom_region_dispatch. source is one of the three RegionSource words, so the
    lookup resolves to exactly one classification — no miss, no fault. The classification is table-driven,
    not an if/elif ladder: the source-to-classification mapping is built from the dispatch table and read
    by key, the same closed-table pattern mutator_of uses over the taxonomy rows (§1.2, §1.3)."""
    return {key: handler() for key, handler in dom_region_dispatch.items()}[source]

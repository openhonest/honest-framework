"""honest-observe - event-sourced observability.

One append-only event log; projections are pure folds over it. This release (increment 1): the
pure foundation — the event envelope (section 2) and projections (section 6). The emit boundary
(section 3) and its log storage are a later increment.
"""

from honest_observe.events import Event, build_event, extract_auth, extract_meta
from honest_observe.projections import apply_projection, matches

__all__ = [
    "Event",
    "build_event",
    "extract_auth",
    "extract_meta",
    "apply_projection",
    "matches",
]

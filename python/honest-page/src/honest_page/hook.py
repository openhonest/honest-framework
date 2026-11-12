"""The SSE extension hook (honest-page-architecture.md §4.5): a custom module registers its own source
against one declared surface.

The three notification surfaces are honest-alerts targets by default, but the page does not reserve the
stream for honest-alerts alone. A module names a surface, the event type it emits, and the source.
attach_stream is the door; attach resolves the surface against the surface registry through surface_slot
and hands the resolved slot to register_source, the one HTTP write — it commits the source onto the
stream's source table. honest-page names no custom module: the registering module names this door in its
own declaration, so the page contract stays fixed as modules are added.
"""

from honest_type import link

# The surface registry (§2.1): each required surface and the slot its registered source's markup lands
# in. The order and membership mirror the PageSurfaces block in honest-page.hd.
_SURFACE_SLOTS = {
    "honest-alerts-banners": "div",
    "honest-header": "header",
    "honest-alerts-toasts": "div",
    "honest-main": "main",
    "honest-footer": "footer",
    "honest-alerts-modal": "div",
}

# The stream's source table: the custom sources registered against a slot. register_source is its one
# mutator, so a registration is a single, auditable write to what the HTTP alert stream serves.
_REGISTERED_SOURCES = []


def surface_slot(surface_id):
    """Resolve a surface id against the surface registry (§2.1): the slot that surface's markup lands
    in, or nothing when the id is not a declared surface. Pure."""
    if surface_id in _SURFACE_SLOTS:
        return _SURFACE_SLOTS[surface_id]
    return None


@link(boundary=True)
def register_source(slot, event_type, source):
    """Register a source on the stream (§4.5): commit it against its slot on the alert stream's source
    table. The one HTTP write of the hook; returns the registration it committed."""
    registration = {"slot": slot, "event_type": event_type, "source": source}
    _REGISTERED_SOURCES.append(registration)
    return registration


def attach(surface_id, event_type, source):
    """Resolve the surface and register the source (§4.5): hand the surface id to surface_slot, then the
    resolved slot, event type, and source to register_source."""
    slot = surface_slot(surface_id)
    return register_source(slot, event_type, source)


@link(boundary=True)
def attach_stream(surface_id, event_type, source):
    """The hook door (§4.5): a module registers its own SSE source against one declared surface. Hands
    off to attach, which resolves the surface and registers the source without honest-page naming that
    module."""
    return attach(surface_id, event_type, source)

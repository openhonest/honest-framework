"""Hybrid Logical Clocks (section 8c.2): a causal total order across sources that share no clock.

`timestamp` plus `sequence` (section 2.1) totally orders events within one aggregate on one clock. But
external sources run their own clocks, and network delay, clock skew, and retries mean a plain
wall-clock sort is not a causal order. An HLC — a physical time, an always-increasing logical counter
for same-instant events, and a source tiebreaker — gives a total order that respects causality without
synchronized clocks. It rides in `meta.source_hlc`; projections that need causal order sort by it.

The three operations here are pure: the physical clock is read at the ingest boundary and passed in as
`physical_now`, never read from inside. `hlc_send` advances the clock on a local event, `hlc_receive`
merges an incoming clock into the local one, and `hlc_compare` is the total order — physical, then
logical, then source. The receiver always keeps its own source identifier.
"""


def hlc_send(local: dict, physical_now: int) -> dict:
    """Advance an HLC for a locally originated event (section 8c.2): take the later of the local
    physical time and the wall clock; when the wall clock advanced, reset the logical counter, otherwise
    increment it so same-physical-time events still order. Pure."""
    new_physical = max(local["physical"], physical_now)
    new_logical = 0 if new_physical > local["physical"] else local["logical"] + 1
    return {"physical": new_physical, "logical": new_logical, "source": local["source"]}


def hlc_receive(local: dict, incoming: dict, physical_now: int) -> dict:
    """Merge an incoming HLC into the local one on receipt (section 8c.2): the new physical time is the
    max of local, incoming, and the wall clock, and the logical counter follows whichever the max came
    from — both (max logical + 1), local alone (local + 1), incoming alone (incoming + 1), or the wall
    clock (reset to 0). The receiver keeps its own source. Pure."""
    new_physical = max(local["physical"], incoming["physical"], physical_now)
    if new_physical == local["physical"] and new_physical == incoming["physical"]:
        new_logical = max(local["logical"], incoming["logical"]) + 1
    elif new_physical == local["physical"]:
        new_logical = local["logical"] + 1
    elif new_physical == incoming["physical"]:
        new_logical = incoming["logical"] + 1
    else:
        new_logical = 0
    return {"physical": new_physical, "logical": new_logical, "source": local["source"]}


def hlc_compare(a: dict, b: dict) -> int:
    """The total order on HLCs (section 8c.2): compare by physical time, then the logical counter, then
    the source identifier. Returns -1 if a precedes b, 1 if a follows b, 0 if identical. Pure."""
    for field in ("physical", "logical", "source"):
        if a[field] < b[field]:
            return -1
        if a[field] > b[field]:
            return 1
    return 0

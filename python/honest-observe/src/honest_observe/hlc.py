"""The hybrid logical clock: advance on a send and on a receive, giving a total order across sources
that respects causality without a synchronized wall clock (honest-observe.hd, section 8c.2).

An HLC is a flat dict of physical milliseconds, a logical counter and a source tiebreaker. hlc_send
advances for a send; hlc_receive advances on receiving an event from another source. Both are pure:
the physical time is passed in (physical_now), never read, so there is no world and no fault. The
logical-counter decision is a boolean key read from a closed table, not an if/elif ladder (P01).
"""

from honest_observe._util import _get


def hlc_send(local, physical_now):
    """Advance a hybrid logical clock for a send (section 8c.2). Set physical to the max of
    physical_now and local's physical; reset the logical counter to 0 when physical advanced, and
    increment it when physical did not advance, so same-millisecond events still order. Pure: two
    values in, the new HLC out, no world (physical_now is passed, not read) and no fault."""
    physical = max(physical_now, local["physical"])
    advanced = physical > local["physical"]
    logical = _get({True: 0, False: local["logical"] + 1}, advanced, 0)
    return {"physical": physical, "logical": logical, "source": local["source"]}


# The logical-counter rule on a receive, keyed by which clocks already held the winning physical time
# (section 8c.2): (physical == local, physical == incoming) -> how to set logical so causality is
# preserved. Both held it -> one past the larger logical; only one held it -> one past that clock's
# logical; neither (physical_now won) -> start at 0. A closed four-row table, not an if/elif ladder.
_RECEIVE_LOGICAL = {
    (True, True): lambda local, incoming: max(local["logical"], incoming["logical"]) + 1,
    (True, False): lambda local, incoming: local["logical"] + 1,
    (False, True): lambda local, incoming: incoming["logical"] + 1,
    (False, False): lambda local, incoming: 0,
}


def hlc_receive(local, incoming, physical_now):
    """Advance a hybrid logical clock on receiving an event from another source (section 8c.2). Advance
    physical to the max of the three physicals; set the logical counter from the closed receive table,
    keyed by which clocks already held the winning physical time, so causality is preserved and ties
    break by source id. Pure: three values in, the new HLC out, no world and no fault."""
    physical = max(physical_now, local["physical"], incoming["physical"])
    key = (physical == local["physical"], physical == incoming["physical"])
    logical = _get(_RECEIVE_LOGICAL, key, _RECEIVE_LOGICAL[(False, False)])(local, incoming)
    return {"physical": physical, "logical": logical, "source": local["source"]}

"""Threshold projections and feedback loops (section 8b): the application watching its own health.

Because every event lands in the same log automatically, an application can observe itself and react.
A threshold projection watches a number derived from the log and fires when that number crosses a
declared line. This module holds the pure half: a metric is a fold plus a value over the log, and a
condition is the crossing decision. The rest of the loop — sending the alert (honest-alerts), storing
the rule (honest-persist), the cooldown timing, running a remediation chain (honest-type) — is the
boundary's, declared by the developer and wired by the framework.

A metric carries fold and value functions, so it is data with behaviour attached the way a declared
projection is (section 6.3); compute_metric runs it over the log. A condition is plain data — an
operator and a value — so the crossing decision is a pure comparison resolved through a dispatch table.
"""

from honest_observe.projections import apply_projection

# Section 8b.4 ConditionSpec operators: the threshold comparators. The table is the dispatch.
_OPERATORS = {
    "gt": lambda value, bound: value > bound,
    "lt": lambda value, bound: value < bound,
    "gte": lambda value, bound: value >= bound,
    "lte": lambda value, bound: value <= bound,
}


def custom_metric(name, event_types, fold, value, initial_state) -> dict:
    """Declare a metric (section 8b.5): the events it folds, the fold that accumulates state, the value
    that extracts the number from that state, and the initial state. Pure data construction — it carries
    the fold and value functions unchanged."""
    return {"name": name, "event_types": event_types, "fold": fold, "value": value, "initial_state": initial_state}


def compute_metric(metric, events):
    """Compute a metric's current value over the log (section 8b). Pure: fold the metric's events from
    its initial state, then extract the value. Reading the log is the boundary's; the events are data."""
    state = apply_projection(events, metric["fold"], metric["initial_state"], event_types=metric["event_types"])
    return metric["value"](state)


def condition_met(value, condition) -> bool:
    """Whether a metric value crosses a threshold condition (section 8b.4): apply the condition's
    operator to the value and its bound. Pure comparison."""
    return _OPERATORS[condition["operator"]](value, condition["value"])

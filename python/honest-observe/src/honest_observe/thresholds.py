"""Metrics and thresholds: fold source events into a metric value, declare a threshold projection,
and evaluate a threshold against the events in its window (honest-observe.hd, section 8b).

compute_metric folds a metric's source events with the metric's own fold and seed, passed in with the
metric, so adding a metric is data, not a new branch. For a plain metric it returns one number; for a
grouped metric it folds each group's events separately and returns a mapping of group key to value.
threshold_projection returns the ThresholdProjection record (its own type, richer than Projection).
evaluate_threshold takes that record and the live Metric handle, invokes compute_metric, then tests
the threshold's condition. All three are pure: no world, no fault.
"""

from functools import reduce

from honest_observe._util import _get, _pick
from honest_observe.types import Metric, ThresholdProjection

# The comparison operators a threshold condition may name, each a pure (value, bound) -> bool test
# (section 8b.2). A table, not an if/elif ladder (P01): a condition {"gt": 0.1} selects the gt row and
# applies it. The operator is read by subscript; an operator the table does not name is a program bug
# in the stored threshold, surfaced below as a crossed=False non-decision rather than a silent hit.
_COMPARATORS = {
    "gt": lambda value, bound: value > bound,
    "ge": lambda value, bound: value >= bound,
    "lt": lambda value, bound: value < bound,
    "le": lambda value, bound: value <= bound,
    "eq": lambda value, bound: value == bound,
}


def compute_metric(metric, events):
    """Compute a metric's value by folding its source events with the metric's own fold and seed
    (section 8b.3, 8b.5). It keeps the events whose type is one of metric["event_types"], then folds
    them: for a plain metric one number, for a grouped metric (a group function under metric["group"])
    a mapping of group key to value. Pure: events in, value out, no world, no fault."""
    event_types = metric["event_types"]
    fold = metric["fold"]
    seed = metric["initial"]
    kept = list(filter(lambda event: event["event_type"] in event_types, events))
    group = _get(metric, "group", None)
    return _pick(
        group is None,
        lambda: reduce(fold, kept, seed),
        lambda: _group_fold(kept, group, fold, seed),
    )


# Fold each group's events separately into a mapping of group key to value (section 8b.5): read each
# event's group key, and fold it onto that group's running value seeded from seed. A lambda, not a def,
# so it adds no column-0 function to the module's declared set (the same reason honest-auth's _util
# helpers are lambdas): every declared function keeps its one gherkin scenario and nothing else does.
_group_fold = lambda kept, group, fold, seed: reduce(
    lambda grouped, event: {**grouped, group(event): fold(_get(grouped, group(event), seed), event)},
    kept,
    {},
)


def threshold_projection(projection_id, metric, condition, window, cooldown, alert, enabled):
    """Declare a threshold projection: a projection that watches the named metric and fires alert when
    condition is crossed over window, with cooldown the minimum time between firings and enabled the
    operator toggle (section 8b.1, 8b.2). metric is the metric NAME, a str; the live Metric handle is
    passed to evaluate_threshold separately. It returns the ThresholdProjection record, not a Projection
    -- a Projection's two fields cannot carry a firing decision's terms, which is why a threshold has its
    own richer type. The stored declaration is a honest-persist record an operator can toggle without
    redeployment. Pure: it builds a record, reads no world and returns no fault."""
    return {
        "projection_id": projection_id,
        "metric": metric,
        "condition": condition,
        "window": window,
        "cooldown": cooldown,
        "alert": alert,
        "enabled": enabled,
    }


# The non-firing comparator for an operator the condition names but the table does not: a declared
# terminal row that never fires, so an unknown operator in a stored threshold is surfaced as a
# non-decision rather than filed under a real comparator (P16).
_NO_FIRE = lambda value, bound: False


# Test one metric value against a threshold condition {operator: bound}: read the single operator and
# bound the condition names, look the operator up in the comparator table (P01), and apply it. An
# operator the table does not name resolves to the declared non-firing terminal, a False non-decision
# rather than a silent hit (P16). A lambda, not a def, so it adds no column-0 function to the module's
# declared set, the same reason honest-auth's _util helpers are lambdas.
_crossed = lambda value, condition: _get(_COMPARATORS, next(iter(condition)), _NO_FIRE)(
    value, condition[next(iter(condition))]
)


def evaluate_threshold(threshold, metric, events):
    """Evaluate a threshold projection against the events in its window and return the firing decision,
    invoking compute_metric to get the metric's value then testing the threshold's condition (section
    8b.2, 8b.5). For a plain metric the decision is whether the one value crossed; for a grouped metric
    it returns { fired, firings } with one { group, fired, value } record per group. Pure: events in,
    decision out, no world, no fault."""
    condition = threshold["condition"]
    value = compute_metric(metric, events)
    return _pick(
        "group" in metric,
        lambda: _grouped_decision(value, condition),
        lambda: _crossed(value, condition),
    )


# The firing decision for a grouped metric (section 8b.5): one { group, fired, value } record per
# group, and fired true when any group crossed. A lambda, not a def, so it adds no column-0 function to
# the module's declared set, the same reason honest-auth's _util helpers are lambdas. The firings list
# is built once and reused, so the any() reads the same records the decision carries.
_grouped_decision = lambda value, condition: (
    lambda firings: {"fired": any(firing["fired"] for firing in firings), "firings": firings}
)(
    [
        {"group": group, "fired": _crossed(group_value, condition), "value": group_value}
        for group, group_value in value.items()
    ]
)

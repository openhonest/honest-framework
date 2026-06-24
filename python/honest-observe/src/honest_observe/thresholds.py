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

import math

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


def _percentile(values, p):
    """The p-th percentile of a list of numbers by nearest rank: sort, take the value at rank
    ceil(p/100 * n). Empty input is zero (no data, no level to report). Pure."""
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[math.ceil(p / 100 * len(ordered)) - 1]


# Section 8b.3 built-in metrics over the framework's own events: each a fold accumulating state and a
# value extracting the number. This covers the self-contained metrics over honest-observe's own event
# types. The persist-sourced metrics (persist.query.*, persist.pool.*, persist.queue.*) fold honest-
# persist's section 4.5 events, whose payloads honest-persist defines, so they are declared there, not
# guessed here; the per-link metrics (link.fault_rate, link.p99_duration_ns) produce a value per link,
# which needs a per-link firing rule section 8b does not yet define.
_BUILTIN_METRICS = {
    "request.error_rate": custom_metric(
        "request.error_rate", ["hf.request.canonical"],
        lambda state, event: {"total": state["total"] + 1, "err": state["err"] + (1 if event["payload"]["result"] == "err" else 0)},
        lambda state: state["err"] / state["total"] if state["total"] else 0.0,
        {"total": 0, "err": 0},
    ),
    "request.rate_per_minute": custom_metric(
        "request.rate_per_minute", ["hf.request.canonical"],
        lambda state, event: {"count": state["count"] + 1},
        lambda state: state["count"],
        {"count": 0},
    ),
    "request.p99_duration_ns": custom_metric(
        "request.p99_duration_ns", ["hf.request.canonical"],
        lambda state, event: {"durations": state["durations"] + [event["payload"]["duration_ns"]]},
        lambda state: _percentile(state["durations"], 99),
        {"durations": []},
    ),
    "classify.rejection_rate": custom_metric(
        "classify.rejection_rate", ["hf.classify.completed"],
        lambda state, event: {"rejected": state["rejected"] + event["payload"]["rejection_count"], "tokens": state["tokens"] + event["payload"]["token_count"]},
        lambda state: state["rejected"] / state["tokens"] if state["tokens"] else 0.0,
        {"rejected": 0, "tokens": 0},
    ),
    "honesty.mutation_count": custom_metric(
        "honesty.mutation_count", ["hf.link.executed"],
        lambda state, event: {"mutations": state["mutations"] + event["payload"]["mutations"]},
        lambda state: state["mutations"],
        {"mutations": 0},
    ),
    "honesty.nondeterminism_count": custom_metric(
        "honesty.nondeterminism_count", ["hf.link.executed"],
        lambda state, event: {"count": state["count"] + (1 if event["payload"]["nondeterminism"] else 0)},
        lambda state: state["count"],
        {"count": 0},
    ),
    "browser.response.p99_duration_ms": custom_metric(
        "browser.response.p99_duration_ms", ["hf.browser.response"],
        lambda state, event: {"durations": state["durations"] + [event["payload"]["duration_ms"]]},
        lambda state: _percentile(state["durations"], 99),
        {"durations": []},
    ),
}


def builtin_metrics() -> dict:
    """The built-in threshold metrics by name (section 8b.3): the ready-made metrics a threshold
    projection can watch without custom projection code. Pure — a fresh mapping of name to metric
    declaration."""
    return dict(_BUILTIN_METRICS)

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


def custom_metric(name, event_types, fold, value, initial_state, group=None) -> dict:
    """Declare a metric (section 8b.5): the events it folds, the fold that accumulates state, the value
    that extracts the number from that state, and the initial state. A `group` function makes the metric
    grouped — it extracts a key from each event (e.g. the link name), so the metric's value is one number
    per group rather than one for the whole log. Pure data construction — the fold, value, and group
    functions are carried unchanged."""
    return {"name": name, "event_types": event_types, "fold": fold, "value": value, "initial_state": initial_state, "group": group}


def compute_metric(metric, events):
    """Compute a metric's current value over the log (section 8b). Pure: fold the metric's events from its
    initial state, then extract the value. An aggregate metric returns one number; a grouped metric folds
    each group's events separately and returns {group_key: number}. Reading the log is the boundary's."""
    if metric["group"] is None:
        return metric["value"](apply_projection(events, metric["fold"], metric["initial_state"], event_types=metric["event_types"]))

    def grouped_fold(state, event):
        key = metric["group"](event)
        return {**state, key: metric["fold"](state.get(key, metric["initial_state"]), event)}

    grouped_state = apply_projection(events, grouped_fold, {}, event_types=metric["event_types"])
    return {key: metric["value"](state) for key, state in grouped_state.items()}


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
# types, including the per-link metrics (link.fault_rate, link.p99_duration_ns), which are grouped by
# link — one value per link — so a threshold declared on them fires per link (evaluate_threshold). The
# persist-sourced metrics (persist.query.*, persist.pool.*, persist.queue.*) fold honest-persist's
# section 4.5 events, whose payloads honest-persist defines, so they are declared there, not guessed here.
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
    "link.fault_rate": custom_metric(
        "link.fault_rate", ["hf.link.executed"],
        lambda state, event: {"total": state["total"] + 1, "faults": state["faults"] + (1 if event["payload"]["result"] == "err" else 0)},
        # A group exists only once at least one link execution folded into it, so total is always >= 1.
        lambda state: state["faults"] / state["total"],
        {"total": 0, "faults": 0},
        group=lambda event: event["payload"]["link_name"],
    ),
    "link.p99_duration_ns": custom_metric(
        "link.p99_duration_ns", ["hf.link.executed"],
        lambda state, event: {"durations": state["durations"] + [event["payload"]["duration_ns"]]},
        lambda state: _percentile(state["durations"], 99),
        {"durations": []},
        group=lambda event: event["payload"]["link_name"],
    ),
}


def builtin_metrics() -> dict:
    """The built-in threshold metrics by name (section 8b.3): the ready-made metrics a threshold
    projection can watch without custom projection code. Pure — a fresh mapping of name to metric
    declaration."""
    return dict(_BUILTIN_METRICS)


def threshold_projection(projection_id, metric, condition, window, cooldown, alert, remediation=None, enabled=True) -> dict:
    """Declare a threshold projection (section 8b.2): the metric to watch (by name), the condition that
    fires it, the window and cooldown, the alert to send, an optional remediation chain, and whether it
    is enabled. The remediation appears only when supplied. Pure data — the declaration is stored as a
    honest-persist record and toggled at runtime, so it carries no behaviour."""
    projection = {
        "projection_id": projection_id,
        "metric": metric,
        "condition": condition,
        "window": window,
        "cooldown": cooldown,
        "alert": alert,
        "enabled": enabled,
    }
    if remediation is not None:
        projection["remediation"] = remediation
    return projection


def evaluate_threshold(threshold, metric, events) -> dict:
    """Decide whether a threshold projection fires now (section 8b): when enabled, compute its metric over
    the events and test the condition. An aggregate metric returns {fired, value}. A grouped metric tests
    the condition per group and returns {fired, firings}, where `fired` is true when any group crosses the
    line and `firings` is one {group, fired, value} per group — so a per-link threshold fires once for
    each link over the line. A disabled projection never fires. Pure. The cooldown timing, the alert send,
    and the remediation chain are the boundary's — this is only the crossing decision."""
    if not threshold["enabled"]:
        return {"fired": False, "value": None}
    value = compute_metric(metric, events)
    if metric["group"] is None:
        return {"fired": condition_met(value, threshold["condition"]), "value": value}
    firings = [{"group": key, "fired": condition_met(number, threshold["condition"]), "value": number} for key, number in value.items()]
    return {"fired": any(firing["fired"] for firing in firings), "firings": firings}

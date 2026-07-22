"""The execution model (section 6): run a step, fold a scenario, combine into a feature report.

Running a step is match -> (on ok) invoke the handler -> classify the outcome (section 6.1). The
only place an exception legitimately arises is inside the developer's own handler, so run_step is
the single boundary that catches one and converts it to a StepFault immediately, via the section 7.1
exception-classification table. A scenario folds its steps over an empty immutable context, threading
a new context forward on each success and stopping at the first non-ok step (section 6.2). The clock
read for duration_ms is the one impure seam, isolated in _now_ms (section 6.2); everything else here
is pure.
"""

import time

from honest_gherkin.ir import step_fault
from honest_gherkin.registry import match_step

# A match fault is already data (no exception); map its code to the step status it reports (section 7.1).
_MATCH_FAULT_STATUS = {"step_unmatched": "unmatched", "ambiguous_step": "ambiguous"}

# The section 7.1 exception table, most-specific first. The catch-all (any other exception) is the
# fallthrough return below, so this table holds only the specific rows.
_EXCEPTION_TABLE = ((AssertionError, "failed", "assertion_failed"),)


def _now_ms():
    """Read the wall clock in milliseconds (section 6.2): the one impure seam in the run model.
    A spoke may stub it to return 0 for fully repeatable runs."""
    return time.perf_counter() * 1000.0  # honest: ignore HC-P004: the one sanctioned clock read, section 6.2


def _classify_exception(exc):
    """Classify a caught handler exception into (step_status, fault_code) via the section 7.1 table,
    most-specific first; any unlisted exception hits the catch-all errored / step_errored."""
    for exc_type, status, code in _EXCEPTION_TABLE:
        if isinstance(exc, exc_type):  # honest: ignore HC-P005: primitive type guard at the exception boundary, not domain dispatch
            return status, code
    return "errored", "step_errored"


def run_step(step, context, registry, scenario_name):
    """Run one step (section 6.1): match it, and on a match invoke the handler and classify the
    outcome. Returns {result: StepResult, context}; the context advances only on success. A handler
    that returns a falsey value is treated as returning the unchanged context."""
    matched = match_step(step, registry)
    if "err" in matched:
        code = matched["err"]["code"]
        fault = step_fault(code, matched["err"]["detail"], scenario_name=scenario_name, step_text=step["text"])
        return {"result": {"step": step, "status": _MATCH_FAULT_STATUS[code], "fault": fault}, "context": context}
    handler = matched["ok"]["pattern"]["handler"]
    captures = matched["ok"]["captures"]
    # honest: disable HC-P002: the step runner turns a raised exception into a reported fault value, which is what a boundary is for
    try:
        returned = handler(context, **captures)
    except Exception as exc:  # the single exception boundary (section 7.1); converted to data at once
        status, code = _classify_exception(exc)
        detail = str(exc) or type(exc).__name__  # honest: ignore HC-P005: the class name is the fault detail when the exception has no message, not dispatch
        fault = step_fault(code, detail, scenario_name=scenario_name, step_text=step["text"])
        return {"result": {"step": step, "status": status, "fault": fault}, "context": context}
    # honest: enable HC-P002
    return {"result": {"step": step, "status": "ok", "fault": None}, "context": returned or context}


def run_scenario(scenario, background, registry):
    """Run one scenario (section 6.2): fold the background steps then the scenario's own over an
    empty immutable context, stopping at the first non-ok step. The status is ok iff every executed
    step is ok, else err."""
    start = _now_ms()
    context = {}
    step_results = []
    status = "ok"
    for step in [*background, *scenario["steps"]]:
        outcome = run_step(step, context, registry, scenario["name"])
        step_results.append(outcome["result"])
        if outcome["result"]["status"] != "ok":
            status = "err"
            break
        context = outcome["context"]
    return {
        "name": scenario["name"],
        "status": status,
        "step_results": step_results,
        "duration_ms": round(_now_ms() - start),
    }


def fold_feature_report(feature, scenario_reports):
    """Combine scenario reports into a FeatureReport (section 6.3): a pure count of ok scenarios
    against the rest."""
    total_passed = sum(1 for report in scenario_reports if report["status"] == "ok")
    return {
        "feature_name": feature["name"],
        "source_path": feature["source_path"],
        "scenarios": scenario_reports,
        "total_passed": total_passed,
        "total_failed": len(scenario_reports) - total_passed,
    }

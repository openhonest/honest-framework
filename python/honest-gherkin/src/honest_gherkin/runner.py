"""Run a Scenario / Feature and produce a Report.

Pure over the input (Scenario, Registry). Impure at the boundary
(`run_feature_file` reads the .feature file).

Honest-code style: step handlers take a context dict and named args, return
a new context. `run_scenario` folds the steps over the initial context.
"""
from __future__ import annotations

import time
from pathlib import Path

from honest_gherkin.parser import parse_feature
from honest_gherkin.registry import (
    AmbiguousStepError,
    StepUnmatchedError,
    match_step,
)
from honest_gherkin.types import (
    FAULT_AMBIGUOUS_STEP,
    FAULT_ASSERTION_FAILED,
    FAULT_STEP_ERRORED,
    FAULT_STEP_UNMATCHED,
    Feature,
    FeatureReport,
    SCENARIO_STATUS_ERR,
    SCENARIO_STATUS_OK,
    STEP_STATUS_AMBIGUOUS,
    STEP_STATUS_ERRORED,
    STEP_STATUS_FAILED,
    STEP_STATUS_OK,
    STEP_STATUS_UNMATCHED,
    Scenario,
    ScenarioReport,
    Step,
    StepFault,
    StepRegistry,
    StepResult,
)


# --- Per-step execution ----------------------------------------------------


# Dispatch table: exception type → (step_status, fault_code, detail_fn).
_EXCEPTION_HANDLERS = [
    (StepUnmatchedError,
        STEP_STATUS_UNMATCHED, FAULT_STEP_UNMATCHED,
        lambda e: str(e)),
    (AmbiguousStepError,
        STEP_STATUS_AMBIGUOUS, FAULT_AMBIGUOUS_STEP,
        lambda e: str(e)),
    (AssertionError,
        STEP_STATUS_FAILED, FAULT_ASSERTION_FAILED,
        lambda e: str(e) or "assertion failed"),
    (Exception,
        STEP_STATUS_ERRORED, FAULT_STEP_ERRORED,
        lambda e: f"{type(e).__name__}: {e}"),
]


def _classify_exception(exc: Exception) -> tuple[str, str, str]:
    for exc_type, status, code, detail_fn in _EXCEPTION_HANDLERS:
        if isinstance(exc, exc_type):
            return status, code, detail_fn(exc)
    # Unreachable because Exception is in the table, but satisfy type checker.
    return STEP_STATUS_ERRORED, FAULT_STEP_ERRORED, str(exc)


def _run_step(
    step: Step,
    context: dict,
    registry: StepRegistry,
    scenario_name: str,
) -> tuple[StepResult, dict, bool]:
    """Execute one step. Returns (StepResult, new_context, should_continue).

    On failure, the scenario stops running — should_continue is False.
    """
    try:
        match = match_step(step, registry)
    except Exception as exc:
        status, code, detail = _classify_exception(exc)
        fault = StepFault(
            code=code, scenario_name=scenario_name,
            step_text=step["text"], detail=detail,
        )
        result = StepResult(step=step, status=status, fault=fault)
        return result, context, False

    handler = match["pattern"]["handler"]
    try:
        new_context = handler(context, **match["captures"]) or context
    except Exception as exc:
        status, code, detail = _classify_exception(exc)
        fault = StepFault(
            code=code, scenario_name=scenario_name,
            step_text=step["text"], detail=detail,
        )
        result = StepResult(step=step, status=status, fault=fault)
        return result, context, False

    result = StepResult(step=step, status=STEP_STATUS_OK, fault=None)
    return result, new_context, True


# --- Scenario orchestration ------------------------------------------------


def run_scenario(
    scenario: Scenario,
    background: list[Step],
    registry: StepRegistry,
) -> ScenarioReport:
    """Fold every step of the scenario (preceded by any background) over an
    empty context. Stop at the first failure.
    """
    t0 = time.monotonic()
    context: dict = {}
    step_results: list[StepResult] = []
    all_steps = list(background) + list(scenario["steps"])

    for step in all_steps:
        result, context, should_continue = _run_step(
            step, context, registry, scenario["name"],
        )
        step_results.append(result)
        if not should_continue:
            break

    duration_ms = int((time.monotonic() - t0) * 1000)
    ok = all(r["status"] == STEP_STATUS_OK for r in step_results)
    return ScenarioReport(
        name=scenario["name"],
        status=SCENARIO_STATUS_OK if ok else SCENARIO_STATUS_ERR,
        step_results=step_results,
        duration_ms=duration_ms,
    )


# --- Feature orchestration -------------------------------------------------


def fold_feature_report(
    feature: Feature,
    scenario_reports: list[ScenarioReport],
) -> FeatureReport:
    passed = sum(1 for r in scenario_reports if r["status"] == SCENARIO_STATUS_OK)
    failed = len(scenario_reports) - passed
    return FeatureReport(
        feature_name=feature["name"],
        source_path=feature["source_path"],
        scenarios=scenario_reports,
        total_passed=passed,
        total_failed=failed,
    )


def run_feature_file(path: str, registry: StepRegistry) -> FeatureReport:
    """I/O boundary. Read .feature, parse, run every scenario, fold report."""
    source = Path(path).read_text(encoding="utf-8")
    feature = parse_feature(source, source_path=path)
    reports = [
        run_scenario(s, feature["background_steps"], registry)
        for s in feature["scenarios"]
    ]
    return fold_feature_report(feature, reports)

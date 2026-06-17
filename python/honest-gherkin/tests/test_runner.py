"""Tests for the scenario / feature runner."""
import pytest

from honest_gherkin import (
    empty_registry,
    fold_feature_report,
    parse_feature,
    register_step,
    run_scenario,
)


def _given_number(ctx, n):
    return {**ctx, "n": n}


def _when_doubled(ctx):
    return {**ctx, "n": ctx["n"] * 2}


def _then_equals(ctx, expected):
    assert ctx["n"] == expected
    return ctx


def _make_registry():
    r = empty_registry()
    r = register_step(r, "given", r"the number {n:int}", _given_number)
    r = register_step(r, "when",  r"I double it", _when_doubled)
    r = register_step(r, "then",  r"the result is {expected:int}", _then_equals)
    return r


def test_happy_path_scenario():
    scenario = {
        "name": "double a number",
        "steps": [
            {"kind": "given", "text": "the number 3", "source_line": 1},
            {"kind": "when",  "text": "I double it",   "source_line": 2},
            {"kind": "then",  "text": "the result is 6", "source_line": 3},
        ],
        "tags": [],
        "source_line": 0,
    }
    report = run_scenario(scenario, background=[], registry=_make_registry())
    assert report["status"] == "ok"
    assert [r["status"] for r in report["step_results"]] == ["ok", "ok", "ok"]


def test_failing_assertion_stops_at_first_failure():
    scenario = {
        "name": "assertion fails",
        "steps": [
            {"kind": "given", "text": "the number 3", "source_line": 1},
            {"kind": "when",  "text": "I double it",   "source_line": 2},
            {"kind": "then",  "text": "the result is 999", "source_line": 3},
            # This extra step should never run — the preceding `then` fails.
            {"kind": "then",  "text": "the result is 6",   "source_line": 4},
        ],
        "tags": [],
        "source_line": 0,
    }
    report = run_scenario(scenario, background=[], registry=_make_registry())
    assert report["status"] == "err"
    statuses = [r["status"] for r in report["step_results"]]
    assert statuses == ["ok", "ok", "failed"]
    assert report["step_results"][2]["fault"]["code"] == "assertion_failed"


def test_unmatched_step_reports_step_unmatched_fault():
    scenario = {
        "name": "no handler",
        "steps": [
            {"kind": "given", "text": "something unregistered", "source_line": 1},
        ],
        "tags": [],
        "source_line": 0,
    }
    report = run_scenario(scenario, background=[], registry=empty_registry())
    assert report["status"] == "err"
    assert report["step_results"][0]["status"] == "unmatched"
    assert report["step_results"][0]["fault"]["code"] == "step_unmatched"


def test_fold_report_counts_pass_fail():
    feature = parse_feature(
        "Feature: counts\n"
        "Scenario: passes\n"
        "  Given the number 1\n"
        "Scenario: also passes\n"
        "  Given the number 2\n",
        "t.feature",
    )
    registry = _make_registry()
    reports = [
        run_scenario(s, feature["background_steps"], registry)
        for s in feature["scenarios"]
    ]
    fr = fold_feature_report(feature, reports)
    assert fr["total_passed"] == 2
    assert fr["total_failed"] == 0

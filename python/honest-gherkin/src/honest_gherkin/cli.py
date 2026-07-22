"""The I/O boundary (section 8): the only module that reads the filesystem or touches argv/stdout.

run_feature_file reads a .feature file, parses it, runs every scenario against a registry, and folds
the report; a parse failure is surfaced as a failing FeatureReport, never swallowed. The CLI discovers
.feature files under a path, threads the registry through each --steps module's register(registry),
runs them, and exits 0 iff nothing failed. Everything in sections 2-7 is pure; the impurity is here.

This module IS the boundary: it performs I/O by design, so HC-P004 (non-boundary I/O) and HC-P002
(catching at a non-boundary) are disabled for the whole file (section 8). Once honest-type ships the
@boundary decorator these functions will carry it instead.
"""

# honest: disable HC-P004: this module is the CLI boundary: it reads feature files and reports results to the terminal

import argparse
import importlib
import sys
from pathlib import Path

from honest_gherkin.parse import parse_feature
from honest_gherkin.registry import empty_registry
from honest_gherkin.run import fold_feature_report, run_scenario


def _parse_failure_report(path, fault):
    """Surface a parse failure as a failing FeatureReport (section 8): a single errored scenario
    carrying the bad_feature_syntax fault, so the failure is reported and never swallowed. Pure."""
    step = {"kind": "given", "resolved_kind": "given", "text": fault["detail"], "source_line": 0}
    scenario_report = {
        "name": "bad feature syntax",
        "status": "err",
        "step_results": [{"step": step, "status": "errored", "fault": fault}],
        "duration_ms": 0,
    }
    return {
        "feature_name": path,
        "source_path": path,
        "scenarios": [scenario_report],
        "total_passed": 0,
        "total_failed": 1,
    }


def run_feature_file(path, registry):
    """Run one .feature file (section 8): read, parse, run every scenario, fold the report. A parse
    error yields a failing report rather than raising. I/O."""
    source = Path(path).read_text(encoding="utf-8")
    parsed = parse_feature(source, path)
    if "err" in parsed:
        return _parse_failure_report(path, parsed["err"])
    feature = parsed["ok"]
    reports = [run_scenario(scenario, feature["background_steps"], registry) for scenario in feature["scenarios"]]
    return fold_feature_report(feature, reports)


def _discover_features(path):
    """Expand a path into the .feature files to run (section 8.1): a directory is searched
    recursively, a single file is taken as-is. I/O."""
    root = Path(path)
    return sorted(root.rglob("*.feature")) if root.is_dir() else [root]


def _load_steps(module_paths, registry):
    """Thread the registry through each --steps module's register(registry) builder (section 8.2),
    in order. Each module exports register only — no global, no decorator. I/O (imports modules)."""
    for dotted in module_paths:
        module = importlib.import_module(dotted)
        registry = module.register(registry)
    return registry


def main(argv=None):
    """The honest-gherkin CLI (section 8.1): run <path> [--steps ...]. Exit 0 iff nothing failed."""
    parser = argparse.ArgumentParser(prog="honest-gherkin")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="run a .feature file or a directory of them")
    run_parser.add_argument("path", help="a .feature file or a directory searched recursively")
    run_parser.add_argument("--steps", action="append", default=[], help="dotted step-module path (repeatable)")
    args = parser.parse_args(list(sys.argv[1:]) if argv is None else list(argv))

    registry = _load_steps(args.steps, empty_registry())
    reports = [run_feature_file(str(path), registry) for path in _discover_features(args.path)]
    for report in reports:
        print(f"{report['source_path']}: {report['total_passed']} passed, {report['total_failed']} failed")
    return 1 if sum(report["total_failed"] for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())

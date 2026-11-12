"""The I/O boundary (section 8): the only module that reads the filesystem or touches argv and stdout.

`main` is the command-line door: it hands the argument vector to `run_cli` and returns the exit
code. `run_cli` is the orchestrator the door hands to: it builds the registry from the `--steps`
modules, discovers the `.feature` files under the path, reads and runs each one, prints the reports,
and returns 0 iff nothing failed. `_discover_features`, `_load_steps` and `read_feature_source` are
the readers that touch the world; `print_report` is the stdout sink; the running itself is pure
(`run_feature` in run.py). Everything in sections 2-7, and the running, is pure, so the impurity is
confined here, to the door, the orchestrator, the three readers, and the sink.
"""

import argparse
import importlib
import sys
from pathlib import Path

from honest_gherkin.registry import empty_registry
from honest_gherkin.run import _now_ms, run_feature


def read_feature_source(path):
    """Read one .feature file's full text (section 8). I/O: the reader behind run_cli's per-file
    run. It only reads; parsing and running are pure and happen in run_feature."""
    return Path(path).read_text(encoding="utf-8")


def print_report(report):
    """Write one feature report's summary line to stdout (section 8.1). I/O: the sink the
    orchestrator hands each finished report to, so the orchestrator itself prints nothing."""
    print(f"{report['source_path']}: {report['total_passed']} passed, {report['total_failed']} failed")


def _discover_features(path):
    """Expand a path into the .feature files to run (section 8.1): a directory is searched
    recursively, a single file is taken as-is. I/O."""
    root = Path(path)
    return sorted(root.rglob("*.feature")) if root.is_dir() else [root]


def _load_steps(module_paths, registry):
    """Thread the registry through each --steps module's register(registry) builder (section 8.2),
    in order. Each module exports register only, with no global and no decorator. I/O (imports
    modules)."""
    for dotted in module_paths:
        module = importlib.import_module(dotted)
        registry = module.register(registry)
    return registry


def run_cli(argv):
    """The orchestrator the CLI door hands the argument vector to (section 8.1). It parses the
    arguments, builds the registry from the --steps modules with _load_steps, discovers the
    .feature files under the path with _discover_features, reads each one with read_feature_source
    and runs it with the pure run_feature, writes each report with print_report, and returns 0 iff
    total_failed is 0 across all features, else 1."""
    parser = argparse.ArgumentParser(prog="honest-gherkin")
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="run a .feature file or a directory of them")
    run_parser.add_argument("path", help="a .feature file or a directory searched recursively")
    run_parser.add_argument("--steps", action="append", default=[], help="dotted step-module path (repeatable)")
    args = parser.parse_args(list(argv))

    registry = _load_steps(args.steps, empty_registry())
    reports = [
        run_feature(read_feature_source(str(path)), str(path), registry, _now_ms)
        for path in _discover_features(args.path)
    ]
    for report in reports:
        print_report(report)
    return 1 if sum(report["total_failed"] for report in reports) else 0


def main(argv):
    """The command-line door (section 8.1). It carries only I/O: it hands the argument vector to
    run_cli and returns the exit code run_cli decides. The __main__ shim below reads sys.argv and
    turns the returned code into the process exit."""
    return run_cli(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""honest-gherkin CLI — the ONLY module with I/O. Everything else is pure.

    honest-gherkin run <feature-path> [--steps module.path]

Step modules are normal Python modules. They export a `register(registry)`
callable that returns an updated registry with their handlers added.
"""
from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from honest_gherkin import empty_registry, run_feature_file
from honest_gherkin.types import SCENARIO_STATUS_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="honest-gherkin")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run a .feature file or directory.")
    p_run.add_argument("path", type=Path, help="Path to .feature file or directory.")
    p_run.add_argument(
        "--steps",
        action="append",
        default=[],
        help="Dotted module path whose register(registry) returns new registry. "
             "May be repeated.",
    )

    args = parser.parse_args(argv)

    handler = _COMMANDS[args.command]
    return handler(args)


def _cmd_run(args: argparse.Namespace) -> int:
    registry = empty_registry()
    for mod_path in args.steps:
        module = importlib.import_module(mod_path)
        register = getattr(module, "register", None)
        if register is None:
            print(
                f"error: {mod_path} has no register(registry) function",
                file=sys.stderr,
            )
            return 2
        registry = register(registry)

    paths = _discover_features(args.path)
    total_fail = 0
    for p in paths:
        report = run_feature_file(str(p), registry)
        total_fail += report["total_failed"]
        print(_format_feature_report(report))
    return 0 if total_fail == 0 else 1


def _discover_features(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(path.rglob("*.feature"))


def _format_feature_report(report) -> str:
    lines = [
        f"\nFeature: {report['feature_name']}  ({report['source_path']})",
    ]
    for s in report["scenarios"]:
        mark = "✓" if s["status"] == SCENARIO_STATUS_OK else "✗"
        lines.append(f"  {mark} {s['name']}  ({s['duration_ms']}ms)")
        for r in s["step_results"]:
            sym = "·" if r["status"] == "ok" else "!"
            lines.append(f"      {sym} {r['step']['kind']} {r['step']['text']}")
            if r["fault"]:
                lines.append(f"          → {r['fault']['code']}: {r['fault']['detail']}")
    lines.append(
        f"  — {report['total_passed']} passed, {report['total_failed']} failed"
    )
    return "\n".join(lines)


_COMMANDS = {
    "run": _cmd_run,
}


if __name__ == "__main__":
    sys.exit(main())

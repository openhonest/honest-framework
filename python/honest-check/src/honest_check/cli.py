"""honest-check CLI (spec §2.1, §3.1, §6)."""
# honest: disable HC-P004
# The CLI is the I/O boundary: config reads, file reads, and stdout writes are
# intentional here.
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from honest_check.config import (
    DEFAULT_CONFIG,
    is_excluded,
    meets_severity,
    normalize_config,
)
from honest_check.diagnostics import aggregate_diagnostics
from honest_check.rules import check_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="honest-check")
    parser.add_argument("path", type=Path, help="File or directory to check.")
    parser.add_argument("--format", choices=("human", "json", "github", "junit"),
                        default="human")
    parser.add_argument("--severity", choices=("error", "warning", "info"),
                        default=None, help="Minimum severity to report.")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)

    config = _load_config(args.config, args.path)
    threshold = args.severity or config["severity"]

    paths = _collect(args.path, config["exclude"])
    reports = []
    for p in paths:
        report = check_source(p.read_text(encoding="utf-8"), str(p))
        reports.append((p, _apply_config(report, config["disable"], threshold)))
    return _EMITTERS[args.format](reports)


# --- config + discovery (I/O) ---------------------------------------------


def _load_config(explicit: Path | None, target: Path) -> dict:
    path = explicit
    if path is None:
        directory = target if target.is_dir() else target.parent
        for candidate in [directory, *directory.parents]:
            maybe = candidate / "honest-check.toml"
            if maybe.is_file():
                path = maybe
                break
    if path is None or not path.is_file():
        return dict(DEFAULT_CONFIG)
    with path.open("rb") as fh:
        return normalize_config(tomllib.load(fh))


def _collect(path: Path, exclude) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        p for p in path.rglob("*.py")
        if not p.name.startswith("_") and not is_excluded(str(p), exclude)
    )


def _apply_config(report, disable, threshold):
    kept = [
        d for d in report["diagnostics"]
        if d["rule_id"] not in disable and meets_severity(d["severity"], threshold)
    ]
    return aggregate_diagnostics(kept)


def _total_errors(reports) -> int:
    return sum(r["total_errors"] for _, r in reports)


# --- renderers (pure) -----------------------------------------------------


def render_human(reports) -> str:
    lines = []
    for _path, report in reports:
        for d in report["diagnostics"]:
            lines.append(f"{d['source_location']}: [{d['rule_id']}] {d['severity']} {d['message']}")
    total = _total_errors(reports)
    warns = sum(r["total_warnings"] for _, r in reports)
    lines.append(f"\nTotals: {total} error(s), {warns} warning(s) across {len(reports)} file(s).")
    return "\n".join(lines)


def render_json(reports) -> str:
    return json.dumps({"files": [{"path": str(p), "report": r} for p, r in reports]}, indent=2)


_GITHUB_LEVEL = {"error": "error", "warning": "warning", "info": "notice"}


def render_github(reports) -> str:
    lines = []
    for _path, report in reports:
        for d in report["diagnostics"]:
            level = _GITHUB_LEVEL.get(d["severity"], "notice")
            lines.append(
                f"::{level} file={d['file']},line={d['line']},col={d['col']},"
                f"title={d['rule_id']}::{d['message']}")
    return "\n".join(lines)


def render_junit(reports) -> str:
    suites = ['<testsuites name="honest-check">']
    for path, report in reports:
        failures = report["total_errors"]
        suites.append(f'  <testsuite name={quoteattr(str(path))} failures="{failures}">')
        for d in report["diagnostics"]:
            case = f'{d["rule_id"]}:{d["line"]}'
            suites.append(f'    <testcase name={quoteattr(case)} classname={quoteattr(str(path))}>')
            if d["severity"] == "error":
                suites.append(f'      <failure message={quoteattr(d["message"])}>'
                              f'{escape(d["source_location"])}</failure>')
            suites.append('    </testcase>')
        suites.append('  </testsuite>')
    suites.append('</testsuites>')
    return "\n".join(suites)


# --- emitters (I/O) -------------------------------------------------------


def _emit(renderer):
    def emit(reports) -> int:
        print(renderer(reports))
        return 0 if _total_errors(reports) == 0 else 1
    return emit


_EMITTERS = {
    "human":  _emit(render_human),
    "json":   _emit(render_json),
    "github": _emit(render_github),
    "junit":  _emit(render_junit),
}


if __name__ == "__main__":
    sys.exit(main())

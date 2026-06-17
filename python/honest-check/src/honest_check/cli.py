"""honest-check CLI."""
# honest: disable HC-P004
# The CLI is the I/O boundary: file reads and stdout writes are intentional here.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from honest_check.rules import check_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="honest-check")
    parser.add_argument("path", type=Path, help="File or directory to check.")
    parser.add_argument("--format", choices=("human", "json"), default="human")
    args = parser.parse_args(argv)

    paths = _collect(args.path)
    reports = [(p, check_source(p.read_text(), str(p))) for p in paths]
    return _EMITTERS[args.format](reports)


def _collect(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*.py") if not p.name.startswith("_"))


def _emit_human(reports) -> int:
    errs = 0
    for path, report in reports:
        for d in report["diagnostics"]:
            print(f"{d['source_location']}: [{d['rule_id']}] {d['severity']} {d['message']}")
            if d["severity"] == "error":
                errs += 1
    total = sum(r["total_errors"] for _, r in reports)
    warns = sum(r["total_warnings"] for _, r in reports)
    print(f"\nTotals: {total} error(s), {warns} warning(s) across {len(reports)} file(s).")
    return 0 if total == 0 else 1


def _emit_json(reports) -> int:
    payload = {
        "files": [
            {"path": str(p), "report": r}
            for p, r in reports
        ]
    }
    print(json.dumps(payload, indent=2))
    return 0 if sum(r["total_errors"] for _, r in reports) == 0 else 1


_EMITTERS = {
    "human": _emit_human,
    "json":  _emit_json,
}


if __name__ == "__main__":
    sys.exit(main())

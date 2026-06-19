"""CLI invocation surface (section 2.1) — the I/O boundary.

This is the only module that touches the filesystem, stdout/stderr, or argv. It
discovers files, calls the pure `check_source`, filters and renders via the pure
`formats` module, and maps results to the exit codes CI depends on:
0 = no errors, 1 = one or more errors, 2 = internal/usage failure.

This module IS the boundary (section 2.1): it performs I/O and catches exceptions
*by design* — catching belongs at the boundary (principle: Typed Exceptions at the
Boundary). Once honest-type ships the @boundary decorator these functions will carry
it; until then the boundary is declared here (section 7.2).
"""

# honest: disable HC-P004, HC-P002

import argparse
import sys
from pathlib import Path

from honest_check.diagnostics import Diagnostic
from honest_check.formats import (
    filter_by_rule,
    filter_by_severity,
    has_errors,
    render,
    supported_formats,
)
from honest_check.rules import check_source


def _discover_files(paths: list[str]) -> list[Path]:
    """Expand CLI paths into a sorted list of .py files (section 3.2)."""
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
        else:
            files.append(path)
    return files


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="honest-check",
        description="The pre-auto-generation honesty gate of the Honest Framework.",
    )
    parser.add_argument("paths", nargs="*", default=["."], help="files or directories to check")
    parser.add_argument("--format", choices=supported_formats(), default="human")
    parser.add_argument("--severity", choices=["error", "warning", "info"], default="warning")
    parser.add_argument("--rule", action="append", default=[], help="run only this rule (repeatable)")
    parser.add_argument("--no-rule", action="append", default=[], dest="no_rule", help="suppress this rule (repeatable)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run honest-check over the given paths; return the process exit code."""
    args = _parse_args(list(sys.argv[1:]) if argv is None else list(argv))

    diagnostics: list[Diagnostic] = []
    try:
        for file in _discover_files(args.paths):
            diagnostics.extend(check_source(file.read_text(encoding="utf-8"), str(file)))
    except OSError as exc:
        print(f"honest-check: cannot read source: {exc}", file=sys.stderr)
        return 2

    diagnostics = filter_by_rule(diagnostics, frozenset(args.rule), frozenset(args.no_rule))
    blocking = has_errors(diagnostics)
    shown = filter_by_severity(diagnostics, args.severity)

    rendered = render(shown, args.format)
    if rendered:
        print(rendered)
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())

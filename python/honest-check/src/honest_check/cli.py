"""CLI invocation surface (section 2.1) — the I/O boundary.

This is the only module that touches the filesystem or stdout. It discovers files,
calls the pure `check_source`, renders diagnostics, and maps results to the exit
codes CI depends on: 0 = no errors, 1 = one or more errors, 2 = internal failure.
All impurity lives here, at the edge; the analysis underneath is pure.
"""

# This module IS the I/O boundary (section 2.1): it reads files and writes stdout
# by design. Once honest-type ships the @boundary decorator these functions will
# carry it; until then the boundary is declared here. (section 7.2)
# honest: disable HC-P004

import sys
from pathlib import Path

from honest_check.diagnostics import Diagnostic
from honest_check.rules import check_source


def _format_human(d: Diagnostic) -> str:
    """One diagnostic in the human-readable CLI form (section 6.1)."""
    head = f"{d['path']}:{d['line']}:{d['col']}: {d['severity']} {d['rule']}"
    return f"{head}\n  {d['message']}"


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


def main(argv: list[str] | None = None) -> int:
    """Run honest-check over the given paths; return the process exit code."""
    args = list(sys.argv[1:]) if argv is None else list(argv)
    diagnostics: list[Diagnostic] = []
    for file in _discover_files(args):
        source = file.read_text(encoding="utf-8")
        diagnostics.extend(check_source(source, str(file)))

    errors = 0
    for d in diagnostics:
        print(_format_human(d))
        if d["severity"] == "error":
            errors += 1

    summary = f"Found {errors} error(s) in {len(diagnostics)} diagnostic(s)."
    print(summary)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

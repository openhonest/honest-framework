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
import tomllib
from pathlib import Path

from honest_check.config import (
    empty_config,
    is_excluded,
    normalize_config,
    resolve_paths,
    resolve_severity,
)
from honest_check.diagnostics import Diagnostic
from honest_check.formats import (
    filter_by_rule,
    filter_by_severity,
    has_errors,
    render,
    supported_formats,
)
from honest_check.rules import check_source


def _discover_files(paths: list[str], exclude: list[str]) -> list[Path]:
    """Expand paths into a sorted list of .py files, honoring exclude globs (section 3.2)."""
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        candidates = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        files.extend(c for c in candidates if not is_excluded(str(c), exclude))
    return files


def _find_config(explicit: str | None) -> Path | None:
    """The honest-check.toml to use: --config if given, else the nearest ancestor's."""
    if explicit:
        return Path(explicit)
    here = Path.cwd()
    for directory in [here, *here.parents]:
        candidate = directory / "honest-check.toml"
        if candidate.is_file():
            return candidate
    return None


def _load_config(path: Path | None) -> dict:
    """Read + normalize honest-check.toml (boundary I/O), or defaults if absent."""
    if path is None or not path.is_file():
        return empty_config()
    with path.open("rb") as handle:
        return normalize_config(tomllib.load(handle))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="honest-check",
        description="The pre-auto-generation honesty gate of the Honest Framework.",
    )
    parser.add_argument("paths", nargs="*", default=[], help="files or directories to check")
    parser.add_argument("--config", default=None, help="path to honest-check.toml")
    parser.add_argument("--format", choices=supported_formats(), default="human")
    parser.add_argument("--severity", choices=["error", "warning", "info"], default=None)
    parser.add_argument("--rule", action="append", default=[], help="run only this rule (repeatable)")
    parser.add_argument("--no-rule", action="append", default=[], dest="no_rule", help="suppress this rule (repeatable)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run honest-check over the given paths; return the process exit code."""
    args = _parse_args(list(sys.argv[1:]) if argv is None else list(argv))

    try:
        config = _load_config(_find_config(args.config))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"honest-check: cannot load config: {exc}", file=sys.stderr)
        return 2

    paths = resolve_paths(args.paths, config["paths"])
    severity = resolve_severity(args.severity, config["severity"])
    suppress = frozenset(args.no_rule) | frozenset(config["disable"])

    diagnostics: list[Diagnostic] = []
    try:
        for file in _discover_files(paths, config["exclude"]):
            diagnostics.extend(check_source(file.read_text(encoding="utf-8"), str(file)))
    except OSError as exc:
        print(f"honest-check: cannot read source: {exc}", file=sys.stderr)
        return 2

    diagnostics = filter_by_rule(diagnostics, frozenset(args.rule), suppress)
    blocking = has_errors(diagnostics)
    shown = filter_by_severity(diagnostics, severity)

    rendered = render(shown, args.format)
    if rendered:
        print(rendered)
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())

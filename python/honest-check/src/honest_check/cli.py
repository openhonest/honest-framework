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

# honest: disable HC-P004, HC-P002, HC-P010: this module is the CLI boundary: it reads files, writes to the terminal, and returns the process exit code

import argparse
import json
import sys
import tomllib
from pathlib import Path

from honest_check.adoption import apply_adoption, resolve_level, rule_report
from honest_check.config import (
    empty_config,
    is_excluded,
    normalize_config,
    resolve_paths,
    resolve_severity,
)
from honest_check.boundary import boundary_diagnostics, check_class_references, check_hc_references, check_hc_st002, check_hf_references, check_references, check_template_references, hc_vocabulary, hf_vocabulary
from honest_check.declgraph import extract_routes
from honest_check.diagnostics import Diagnostic
from honest_check.formats import (
    filter_by_rule,
    filter_by_severity,
    render_report,
    has_errors,
    render,
    supported_formats,
)
from honest_check.lsp import serve
from honest_check.rules import check_source, language_for_path
from honest_check.templates import js_class_references, js_module_bindings, scan_template, stylesheet_classes
from honest_parse import parse


def _discover_files(paths: list[str], exclude: list[str]) -> list[Path]:
    """Expand paths into a sorted list of .py files, honoring exclude globs (section 3.2)."""
    files: list[Path] = []
    for raw in paths:
        path = Path(raw)
        candidates = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        files.extend(c for c in candidates if not is_excluded(str(c), exclude))
    return files


def _discover_templates(templates_dir: str) -> list[Path]:
    """Expand the configured template directory into a sorted list of .html files (honest-page section
    10.1). Empty when no directory is configured or it does not exist, so HC002's boundary check runs
    only where an application declares its templates."""
    root = Path(templates_dir)
    return sorted(root.rglob("*.html")) if templates_dir and root.is_dir() else []


def _template_roots(templates_dir: str) -> list[Path]:
    """The template search roots HC-REF002 resolves include/extends targets against: the configured
    templates directory and its sibling `atoms/` and `molecules/` directories, which honest-components
    mounts on the template search path (honest-components section 3.1), when they exist. Empty when no
    templates directory is configured."""
    if not templates_dir:
        return []
    base = Path(templates_dir)
    return [d for d in (base, base.parent / "atoms", base.parent / "molecules") if d.is_dir()]


def _discover_css(css_dir: str) -> list[Path]:
    """Expand a directory into a sorted list of .css files — the component stylesheets HC-REF003 resolves
    class references against. Empty when the directory is empty or does not exist."""
    root = Path(css_dir)
    return sorted(root.rglob("*.css")) if css_dir and root.is_dir() else []


def _discover_js(js_dir: str) -> list[Path]:
    """Expand a directory into a sorted list of .js files — the client modules HC-REF003 reads for the
    classes they emit via classList/className. Empty when the directory is empty or does not exist."""
    root = Path(js_dir)
    return sorted(root.rglob("*.js")) if js_dir and root.is_dir() else []


def _load_manifest(manifest_path: str) -> dict | None:
    """honest-format's declared vocabulary manifest HC-REF004 resolves hf-* values against, read from the
    configured path (boundary I/O), or None when no manifest is configured or the file is absent — HC-REF004
    then does not run, exactly as HC002/HC-REF001 do not run without a templates directory."""
    path = Path(manifest_path)
    if not manifest_path or not path.is_file():
        return None
    with path.open("rb") as handle:
        return json.load(handle)


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
    parser.add_argument("--lsp", action="store_true", help="run as a Language Server over stdio")
    parser.add_argument("--config", default=None, help="path to honest-check.toml")
    parser.add_argument("--format", choices=supported_formats(), default="human")
    parser.add_argument("--severity", choices=["error", "warning", "info"], default=None)
    parser.add_argument("--rule", action="append", default=[], help="run only this rule (repeatable)")
    parser.add_argument("--no-rule", action="append", default=[], dest="no_rule", help="suppress this rule (repeatable)")
    parser.add_argument("--fix", action="store_true", help="apply auto-fixable corrections (conservative subset only)")
    parser.add_argument("--watch", action="store_true", help="re-run on each trigger line from stdin")
    parser.add_argument("--report", action="store_true", help="count every rule's findings and exit 0 (section 2.1.1)")
    return parser.parse_args(argv)


def _run_once(paths: list[str], exclude: list[str], severity: str, suppress, only, fmt: str, templates_dir: str, format_manifest: str, component_manifest: str, level: str, report: bool) -> int:
    """Check the paths once and print the rendered report; return the exit code (1 on errors, 2 on a
    read failure, else 0). The single-pass core that both a plain run and --watch repeat. When a
    template directory is configured, its templates are scanned once and every checked file also runs
    HC002's first-link boundary check against them (spec section 4.2)."""
    diagnostics: list[Diagnostic] = []
    try:
        # Scan every template across the search roots (templates dir + atoms/ + molecules/), tracking each
        # file's root so HC-REF002 can resolve include/extends targets by path relative to a root, exactly
        # as the loader searches.
        pairs = [(troot, f) for troot in _template_roots(templates_dir) for f in _discover_templates(str(troot))]
        resolvable = frozenset(str(f.relative_to(troot)) for troot, f in pairs)
        scanned = [scan_template(f.read_bytes(), str(f)) for troot, f in pairs]
        # HC-REF003 resolves class references against the union of the classes every component stylesheet
        # under the search roots defines. The class references come from templates (scanned above) and from
        # the .js modules under the roots (the classes they emit via classList/className).
        defined_classes = frozenset(cls for troot in _template_roots(templates_dir) for f in _discover_css(str(troot)) for cls in stylesheet_classes(f.read_bytes()))
        js_scanned = [{"path": str(f), "class_refs": js_class_references(f.read_bytes()), "bindings": js_module_bindings(f.read_bytes())} for troot in _template_roots(templates_dir) for f in _discover_js(str(troot))]
        all_routes: list = []
        for file in _discover_files(paths, exclude):
            source = file.read_text(encoding="utf-8")
            diagnostics.extend(check_source(source, str(file)))
            if scanned:
                src_bytes = source.encode("utf-8")
                root = parse(src_bytes, language_for_path(str(file))).root_node
                diagnostics.extend(boundary_diagnostics(root, src_bytes, str(file), scanned))
                all_routes.extend(extract_routes(root, src_bytes))
        # HC-REF001 resolves every template action against the project-wide route union, so a target
        # mounted in a different file is not a false dead reference; HC-REF002 resolves every literal
        # include/extends target against the template search path. With no templates both yield nothing.
        diagnostics.extend(check_references(all_routes, scanned))
        diagnostics.extend(check_template_references(resolvable, scanned))
        diagnostics.extend(check_class_references(defined_classes, scanned + js_scanned))
        # HC-REF004 resolves every authored hf-* attribute value against honest-format's declared
        # vocabulary. With no manifest configured it does not run, exactly as the checks above do not
        # without templates.
        manifest = _load_manifest(format_manifest)
        if manifest is not None:
            diagnostics.extend(check_hf_references(hf_vocabulary(manifest), scanned))
        # HC-REF004 for components resolves every authored hc-* attribute against honest-components'
        # declared behaviour vocabulary. With no manifest configured it does not run.
        components = _load_manifest(component_manifest)
        if components is not None:
            diagnostics.extend(check_hc_references(hc_vocabulary(components), scanned))
        # HC-ST002 resolves every client module's module-level bindings against the user-state slots the
        # templates declare. The manifest is the static declaration of user state, so a second copy of a
        # slot is knowable before the app runs (honest-state section 3).
        diagnostics.extend(check_hc_st002(frozenset(key for s in scanned for key in s["manifest_keys"]), js_scanned))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"honest-check: cannot read source: {exc}", file=sys.stderr)
        return 2
    diagnostics = filter_by_rule(diagnostics, only, suppress)
    if report:
        print(render_report(rule_report(diagnostics, level), level))
        return 0
    diagnostics = apply_adoption(diagnostics, level)
    blocking = has_errors(diagnostics)
    rendered = render(filter_by_severity(diagnostics, severity), fmt, level)
    if rendered:
        print(rendered)
    return 1 if blocking else 0


def watch(run, stdin=None) -> int:
    """Re-run the check on each trigger line read from `stdin`, returning the last exit code at EOF
    (section 2.1). honest-check bundles no filesystem watcher, keeping it dependency-free; an external
    watch tool pipes one trigger per change. The trigger stream is injected so the loop is testable,
    defaulting to stdin exactly as the LSP server does."""
    source = sys.stdin.buffer if stdin is None else stdin
    code = run()
    while source.readline():
        code = run()
    return code


def main(argv: list[str] | None = None) -> int:
    """Run honest-check over the given paths; return the process exit code."""
    args = _parse_args(list(sys.argv[1:]) if argv is None else list(argv))

    if args.lsp:
        return serve()

    try:
        config = _load_config(_find_config(args.config))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"honest-check: cannot load config: {exc}", file=sys.stderr)
        return 2

    paths = resolve_paths(args.paths, config["paths"])
    severity = resolve_severity(args.severity, config["severity"])
    suppress = frozenset(args.no_rule) | frozenset(config["disable"])
    only = frozenset(args.rule)
    level = resolve_level(config["adoption"])

    if args.fix:
        print(
            "honest-check: no auto-fixable corrections — its rules flag dishonesty that needs "
            "restructuring, not a mechanical fix.",
            file=sys.stderr,
        )

    def run() -> int:
        return _run_once(paths, config["exclude"], severity, suppress, only, args.format, config["templates"], config["format_manifest"], config["component_manifest"], level, args.report)

    if args.watch:
        return watch(run)
    return run()


if __name__ == "__main__":
    raise SystemExit(main())

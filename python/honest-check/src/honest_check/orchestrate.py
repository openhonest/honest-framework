"""The orchestrators and doors (§2.1, §2.3). check_paths and run_check compose the
pure core over the discovered files; startup_check and main are the doors that turn
the result into a stderr print, a process exit or a raised HonestCheckError. The
doors hold no checking logic — they carry I/O only."""

import sys

from ._util import choose, pick, read_or
from .boundary import (
    discover_declaration,
    discover_files,
    load_config,
    load_project_config,
    pair_source,
    read_declaration,
    read_fault,
    read_format_manifest,
    read_source,
    resolve_project_config,
    resolve_rule_config,
    write_report,
)
from .context import build_context
from .crossing import check_auth, check_references, check_roles, cross_declaration
from .errors import HonestCheckError
from .report import (
    blocking_findings,
    format_github,
    format_human,
    format_json,
    format_junit,
    parse_args,
    prepare_report,
    resolve_exit_code,
    severity_rank,
)
from .rules import check_source

_CODE_SUFFIXES = (".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".rb", ".go")

_BY_FORMAT = {
    "human": format_human,
    "json": format_json,
    "github": format_github,
    "junit": format_junit,
}


# ---- the startup path (§2.3) ------------------------------------------------


def check_paths(paths, severity):
    """The startup orchestrator: read each file, build its context, run check_source,
    fold the findings, and keep the blocking subset at the run's severity (§2.3)."""
    rule_config = resolve_rule_config(load_config())
    all_diagnostics = []
    for path in paths:
        context = build_context(read_source(path), path, rule_config)
        all_diagnostics.extend(check_source(context, None))
    blocking = blocking_findings(all_diagnostics, severity_rank(severity))
    return {"all": all_diagnostics, "blocking": blocking}


def _render_blocking(blocking):
    return "\n".join(f"{d['source_location']}: {d['severity']} {d['rule_id']}: {d['message']}" for d in blocking)


def _print_blocking(blocking):
    print(_render_blocking(blocking), file=sys.stderr)
    return None


def _on_warn(findings):
    return _print_blocking(findings["blocking"])


def _on_raise(findings):
    return pick(
        len(findings["blocking"]) > 0,
        lambda: _raise_report(findings["all"]),
        lambda: None,
    )


def _raise_report(all_diagnostics):
    raise HonestCheckError(_render_blocking(all_diagnostics))


def _on_halt(findings):
    _print_blocking(findings["blocking"])
    return pick(len(findings["blocking"]) > 0, lambda: sys.exit(1), lambda: None)


_ON_ERROR = {"warn": _on_warn, "raise": _on_raise, "halt": _on_halt}


def startup_check(paths, on_error, severity):
    """The startup door: hand the paths to check_paths, act per on_error over the
    blocking subset, and return the full findings list (§2.3)."""
    findings = check_paths(paths, severity)
    read_or(_ON_ERROR, on_error, _on_warn)(findings)
    return findings["all"]


# ---- the CLI path (§2.1) ----------------------------------------------------


def _source_files(files):
    return [pair_source(path, read_source(path)) for path in files]


def _code_source_files(sources):
    return list(filter(lambda s: s["path"].endswith(_CODE_SUFFIXES), sources))


def _check_each_file(files):
    rule_config = resolve_rule_config(load_config())
    out = []
    for path in files:
        context = build_context(read_source(path), path, rule_config)
        out.extend(check_source(context, discover_declaration(path)))
    return out


def _whole_program(project, sources):
    manifest = read_format_manifest(project["format_manifest"])
    code = _code_source_files(sources)
    return (
        check_references(sources, manifest)
        + check_roles(code, None)
        + check_auth(code)
    )


def _render(fmt, report):
    return read_or(_BY_FORMAT, fmt, format_human)(report)


def _finish(args, project, diagnostics):
    report = prepare_report(diagnostics, args, project["adoption"])
    write_report(_render(args["format"], report))
    return resolve_exit_code(report)


def _base_mode(args, project, files):
    sources = _source_files(files)
    diagnostics = _check_each_file(files) + _whole_program(project, sources)
    return _finish(args, project, diagnostics)


def _cross_mode(args, project, files, declaration):
    sources = _source_files(files)
    export_source = pick(args["exports"] == "", lambda: b"", lambda: read_source(args["exports"]))
    diagnostics = cross_declaration(sources, declaration, export_source, args["include_rules"])
    return _finish(args, project, diagnostics)


def _dispatch_mode(args, project, files, declaration):
    return pick(
        hasattr(declaration, "keys"),
        lambda: _cross_mode(args, project, files, declaration),
        lambda: read_fault(declaration),
    )


def run_check(argv):
    """The CLI orchestrator (§2.1): parse the arguments, discover the files, run base
    mode or the declaration-crossing mode, and return the ExitCode — or the Fault a
    failed declaration read routes outward (§HC-R002)."""
    args = parse_args(argv)
    project = resolve_project_config(load_project_config())
    files = discover_files(args["paths"], project["exclude"])
    return pick(
        args["declaration"] == "",
        lambda: _base_mode(args, project, files),
        lambda: _dispatch_mode(args, project, files, read_declaration(args["declaration"])),
    )


def _discharge_fault(fault):
    raise HonestCheckError(f"{fault['problem']} — {fault['remedy']}")


def main(argv):
    """The CLI door (§2.1): hand argv to run_check and turn its answer into the
    process result — the ExitCode returned, or the Fault discharged as a raised
    HonestCheckError (exit code 2)."""
    result = run_check(argv)
    return pick(hasattr(result, "keys"), lambda: _discharge_fault(result), lambda: result)

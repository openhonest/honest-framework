"""The orchestrators and the doors: the startup path (startup_check -> check_paths) and
the CLI path (main -> run_check), each sharing the one pure core check_source.

check_paths and run_check both pull each file with read_source and run check_source over
it; neither holds a second copy of the checking logic. startup_check and main carry only
I/O. HonestCheckError is the one typed exception, raised at the door on on_error='raise'.
"""

import sys

from honest_check.core import check_source, cross_declaration, pair_source
from honest_check.readers import (
    discover_files,
    load_config,
    load_project_config,
    read_declaration,
    read_source,
    write_report,
)
from honest_check.report import (
    by_format,
    prepare_report,
    parse_args,
    resolve_exit_code,
)

# The minimum severity a finding must reach to block startup, ranked (section 2.3).
_SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}


class HonestCheckError(Exception):
    """A startup block carried as a typed exception at the door (on_error='raise',
    section 2.3). It holds the full diagnostic list the run produced."""


def check_paths(paths):
    """The orchestrator the startup door hands its paths to (section 2.3). It pulls the
    project's resolved rule_config once with load_config and applies that one map to every
    file: for each path it pulls the text with read_source and runs check_source over it,
    folding every file's diagnostics into one list."""
    rule_config = load_config()
    diagnostics = []
    for path in paths:
        diagnostics.extend(check_source(read_source(path), path, rule_config))
    return diagnostics


def startup_check(paths, on_error, severity):
    """The door the framework's development-mode startup integration calls (section 2.3). It
    hands the paths to check_paths, decides which findings reach the blocking severity, acts
    per on_error, and returns the same diagnostic list check_paths produced."""
    diagnostics = check_paths(paths)
    threshold = _SEVERITY_RANK[severity]
    blocking = [d for d in diagnostics if _SEVERITY_RANK[d["severity"]] >= threshold]

    def render_block():
        return "\n".join(
            f"{d['source_location']}: {d['severity']} {d['rule_id']} {d['message']}"
            for d in blocking
        )

    def act_warn():
        if blocking:
            print(render_block(), file=sys.stderr)

    def act_raise():
        if blocking:
            raise HonestCheckError(render_block())

    def act_halt():
        if blocking:
            print(render_block(), file=sys.stderr)
            raise SystemExit(1)

    actions = {"warn": act_warn, "raise": act_raise, "halt": act_halt}
    if on_error not in actions:
        raise HonestCheckError(
            f"on_error {on_error!r} matched no branch; accepted are "
            f"{sorted(actions)}"
        )
    actions[on_error]()
    return diagnostics


def run_check(argv):
    """The orchestrator the CLI door hands the argument vector to (section 2.1). It parses the
    arguments, pulls the [check] config once, and discovers the source files, then runs in one
    of two modes chosen by whether CliArgs.declaration is empty.

    Base mode (empty declaration) pulls the per-rule config and runs the pure core check_source
    over each discovered file, folding every file's diagnostics into one list. Crossing mode
    (non-empty declaration) pulls the one parsed module with read_declaration; when that read
    fails it routes the Fault straight outward as its own answer (ExitCode | Fault), checking
    nothing over a declaration it could not open (§HC-R002). Otherwise it pulls the export
    module's text, pairs each discovered file's path with its text into a SourceFile, and runs
    cross_declaration once over the whole package, crossing only the rules named in
    include_rules. Both modes feed one combined list into the same report/format/write/exit
    tail, returning the exit code resolve_exit_code decides."""
    args = parse_args(argv)
    project = load_project_config()
    files = discover_files(args["paths"], project["exclude"])

    if args["declaration"]:
        declaration = read_declaration(args["declaration"])
        if "problem" in declaration:
            return declaration
        export_source = read_source(args["exports"]) if args["exports"] else ""
        sources = [pair_source(path, read_source(path)) for path in files]
        diagnostics = cross_declaration(
            sources, declaration, export_source, args["include_rules"]
        )
    else:
        rule_config = load_config()
        diagnostics = []
        for path in files:
            diagnostics.extend(check_source(read_source(path), path, rule_config))

    report = prepare_report(diagnostics, args, project["adoption"])
    write_report(by_format[args["format"]](report))
    return resolve_exit_code(report)


def main(argv):
    """The command-line door (section 2.1). It carries only I/O: it hands argv to run_check and
    turns run_check's answer into the process exit. run_check answers either an ExitCode or the
    declaration-read Fault it routed outward. On an ExitCode the __main__ shim exits with it. On
    the Fault — a configured .hd that was missing or did not parse (§HC-R002) — the door
    discharges it at exit code 2 by raising HonestCheckError carrying the Fault's problem and
    remedy, rather than letting a returned value be ignored: this is the one place a Fault
    crosses from a value into a world effect."""
    result = run_check(argv)
    if isinstance(result, dict):
        raise HonestCheckError(f"{result['problem']} {result['remedy']}")
    return result


if __name__ == "__main__":
    try:
        exit_code = int(main(sys.argv[1:]))
    except HonestCheckError as read_failure:
        print(str(read_failure), file=sys.stderr)
        exit_code = 2
    raise SystemExit(exit_code)

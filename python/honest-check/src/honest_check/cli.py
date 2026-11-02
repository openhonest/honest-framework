"""The orchestrators and the doors: the startup path (startup_check -> check_paths) and
the CLI path (main -> run_check), each sharing the one pure core check_source.

check_paths and run_check both pull each file with read_source and run check_source over
it; neither holds a second copy of the checking logic. startup_check and main carry only
I/O. HonestCheckError is the one typed exception, raised at the door on on_error='raise'.
"""

import os
import sys

from honest_parse import language_of

from honest_check.core import (
    check_references,
    check_source,
    cross_declaration,
    pair_source,
)
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

# The grammars whose files carry the cross-file references check_references resolves: the
# template grammars (html, jinja), the stylesheet grammar (css) and the script grammar
# (javascript). run_check pairs only the discovered files honest-parse detects as one of
# these into the whole-set view check_references folds over.
_REFERENCE_GRAMMARS = frozenset({"html", "jinja", "css", "javascript"})


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
        diagnostics.extend(check_source(read_source(path), path, rule_config, None))
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

    # The on_error word picks an outcome as data (section 2.3): whether a block prints to
    # stderr, raises, and halts the process. The door performs the I/O in its own body, so the
    # stderr write sits at the boundary this function already is, not in a nested helper a .hd
    # cannot name.
    outcomes = {
        "warn": {"print": True, "raise": False, "halt": False},
        "raise": {"print": False, "raise": True, "halt": False},
        "halt": {"print": True, "raise": False, "halt": True},
    }
    if on_error not in outcomes:
        raise HonestCheckError(
            f"on_error {on_error!r} matched no branch; accepted are "
            f"{sorted(outcomes)}"
        )
    outcome = outcomes[on_error]
    if blocking and outcome["print"]:
        print(render_block(), file=sys.stderr)
    if blocking and outcome["raise"]:
        raise HonestCheckError(render_block())
    if blocking and outcome["halt"]:
        raise SystemExit(1)
    return diagnostics


def run_check(argv):
    """The orchestrator the CLI door hands the argument vector to (section 2.1). It parses the
    arguments, pulls the [check] config once, and discovers the source files, then runs in one
    of two modes chosen by whether CliArgs.declaration is empty.

    Base mode (empty declaration) pulls the per-rule config and runs the pure core check_source
    over each discovered file, folding every file's diagnostics into one list; after that loop
    it pairs each discovered template, stylesheet and script file into a SourceFile and runs the
    pure core check_references once over the whole set, folding its HC-REF002 and HC-REF003
    cross-file findings into the same list. Crossing mode
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

        def nearest_declaration(path):
            """The parsed module .hd governing a discovered file: walk the file's directory
            ancestors to the first honest-<name>/honest-<name>.hd and read it through
            read_declaration, returning its one parsed module, or NOTHING (None) when no such
            .hd is found or the read/parse fails. Base-mode discovery is best-effort — the
            strict missing-declaration Fault belongs to the explicit --declaration path, not
            here. A .hd that declares more than one module yields read_declaration's first
            module, which is enough to recognize this file's doors by name."""
            directory = os.path.dirname(os.path.abspath(path))
            while True:
                base = os.path.basename(directory)
                candidate = os.path.join(directory, f"{base}.hd")
                if base.startswith("honest-") and os.path.isfile(candidate):
                    parsed = read_declaration(candidate)
                    return None if "problem" in parsed else parsed
                parent = os.path.dirname(directory)
                if parent == directory:
                    return None
                directory = parent

        diagnostics = []
        for path in files:
            declaration = nearest_declaration(path)
            diagnostics.extend(
                check_source(read_source(path), path, rule_config, declaration)
            )
        reference_sources = [
            pair_source(path, read_source(path))
            for path in files
            if language_of(path).get("ok") in _REFERENCE_GRAMMARS
        ]
        diagnostics.extend(check_references(reference_sources))

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

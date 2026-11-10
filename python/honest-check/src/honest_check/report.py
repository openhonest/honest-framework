"""The pure core of the CLI path: argument parsing, adoption, report preparation,
the four formatters, and the exit code (sections 2.1, 6, 9.4).

Everything here is pure: it reads nothing and writes nothing. The adoption-level
membership and the format dispatch are module-level data, never per-rule functions.
"""

import datetime
import json

# The four output format words section 6 defines, and the default / no-match fallback.
_FORMATS = frozenset({"human", "json", "github", "junit"})

# The section 9.4 level-to-rule membership, as data. Four cumulative level sets plus the
# always-on three, 57 members in all. enforced_rules_of folds a named set, never a phrase.
_ALWAYS_RULES = frozenset({"HC-SYN", "HC-SUP001", "HC-SUP002"})
_STRUCTURAL_RULES = frozenset({"HC-P001", "HC-P003", "HC-P007", "HC-P011", "HC-P016", "HC-P015", "HC-P019", "HC-P020"})
_BOUNDARY_RULES = frozenset(
    {
        "HC-P002",
        "HC-P004",
        "HC-P005",
        "HC-P006",
        "HC-P010",
        "HC-P013",
        "HC-ST001",
        "HC-A001",
        "HC-A002",
    }
)
_TYPED_RULES = frozenset(
    {
        "HC001",
        "HC002",
        "HC003",
        "HC004",
        "HC005",
        "HC006",
        "HC007",
        "HC008",
        "HC009",
        "HC010",
        "HC011",
        "HC-SM01",
        "HC-SM02",
        "HC-SM03",
        "HC-SM04",
        "HC-SM05",
        "HC-P014",
        "HC-P017",
        "HC-P018",
    }
)
_DECLARED_RULES = frozenset(
    {
        "HC-R001",
        "HC-R002",
        "HC-R003",
        "HC-R004",
        "HC-R005",
        "HC-OR001",
        "HC-OR003",
        "HC-REF001",
        "HC-REF002",
        "HC-REF003",
        "HC-REF004",
        "HC-REF005",
        "HC-REF006",
        "HC-REF007",
        "HC-REF008",
        "HC-REF009",
        "HC-ST002",
        "HC-HF001",
        "HC-HF002",
    }
)

# The cumulative order of the four levels and the set each one adds on top of the levels
# below it. enforced_rules_of accumulates always_rules then each level's set up to and
# including the one asked for.
_LEVEL_ORDER = ("Structural", "Boundary", "Typed", "Declared")
_RULES_ADDED_AT = {
    "Structural": _STRUCTURAL_RULES,
    "Boundary": _BOUNDARY_RULES,
    "Typed": _TYPED_RULES,
    "Declared": _DECLARED_RULES,
}

# The rules the adoption levels cover, the denominator of the adoption line (section 9.4).
_TOTAL_COVERED = 58

# severity ordering, so the --severity threshold keeps findings at or above it.
_SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}

# The flag tables parse_args dispatches on: value flags consume the next token, list flags
# append it, boolean flags set a field true. A token in none of them is a positional path.
_VALUE_FLAGS = {
    "--config": "config_path",
    "--format": "format",
    "--severity": "severity",
    "--declaration": "declaration",
    "--exports": "exports",
}
_LIST_FLAGS = {"--rule": "include_rules", "--no-rule": "exclude_rules"}
_BOOL_FLAGS = {"--report": "report_mode"}


def parse_args(argv):
    """Turn the raw argument vector into the resolved CliArgs (section 2.1).

    Absence is resolved here, at the boundary, to an explicit bounded value: an omitted or
    unrecognized --format becomes 'human', an omitted --severity becomes 'warning', an omitted
    --declaration or --exports becomes the empty string — the exact signal run_check reads to
    stay in base mode. --fix and --watch are not carried by this layer.
    """
    args = {
        "paths": [],
        "format": "human",
        "severity": "warning",
        "include_rules": [],
        "exclude_rules": [],
        "config_path": "",
        "report_mode": False,
        "declaration": "",
        "exports": "",
    }

    def take_value(index, field):
        args[field] = argv[index + 1]
        return index + 2

    def take_list(index, field):
        args[field].append(argv[index + 1])
        return index + 2

    def take_bool(index, field):
        args[field] = True
        return index + 1

    index = 0
    while index < len(argv):
        token = argv[index]
        if token in _VALUE_FLAGS:
            index = take_value(index, _VALUE_FLAGS[token])
        elif token in _LIST_FLAGS:
            index = take_list(index, _LIST_FLAGS[token])
        elif token in _BOOL_FLAGS:
            index = take_bool(index, _BOOL_FLAGS[token])
        else:
            args["paths"].append(token)
            index += 1

    if args["format"] not in _FORMATS:
        args["format"] = "human"
    return args


def enforced_rules_of(level):
    """Every HC rule enforced at the given adoption level — the section 9.4 cumulative
    membership. always_rules hold everywhere; each level adds its own set on top of the
    levels below it, so Declared returns the whole 53-rule set.

    level is a declared AdoptionLevel bounded by load_project_config, so it names a member of
    _LEVEL_ORDER; the interior trusts that contract and takes the cumulative levels up to and
    including it. A level outside the vocabulary raises here rather than silently returning the
    whole set.
    """
    cutoff = _LEVEL_ORDER.index(level)
    rules = set(_ALWAYS_RULES)
    for name in _LEVEL_ORDER[: cutoff + 1]:
        rules |= _RULES_ADDED_AT[name]
    return sorted(rules)


def prepare_report(diagnostics, args, adoption):
    """Turn the raw per-file findings into the report the formatters render and
    resolve_exit_code judges (sections 2.1, 6, 9.4).

    In order: downgrade every finding whose rule the declared level does not enforce to info
    (so it still reports but never blocks); drop findings below the --severity threshold;
    keep only args.include_rules when non-empty and drop args.exclude_rules; then count the
    survivors and record the adoption-line numbers.
    """
    enforced = set(enforced_rules_of(adoption))
    threshold = _SEVERITY_RANK[args["severity"]]
    include = args["include_rules"]
    exclude = set(args["exclude_rules"])

    survivors = []
    for diagnostic in diagnostics:
        rule = diagnostic["rule_id"]
        severity = "info" if rule not in enforced else diagnostic["severity"]
        if _SEVERITY_RANK[severity] < threshold:
            continue
        if include and rule not in include:
            continue
        if rule in exclude:
            continue
        survivors.append({**diagnostic, "severity": severity})

    rule_counts = {}
    if args["report_mode"]:
        for diagnostic in survivors:
            rule = diagnostic["rule_id"]
            rule_counts[rule] = rule_counts.get(rule, 0) + 1

    return {
        "diagnostics": survivors,
        "errors": sum(1 for d in survivors if d["severity"] == "error"),
        "warnings": sum(1 for d in survivors if d["severity"] == "warning"),
        "infos": sum(1 for d in survivors if d["severity"] == "info"),
        "rule_counts": rule_counts,
        "adoption": adoption,
        "enforced_count": len(enforced),
        "total_count": _TOTAL_COVERED,
        "report_mode": args["report_mode"],
    }


def format_human(report):
    """Render the human-readable CLI default (section 6.1): the adoption line, one block per
    finding, and the 'Found N errors, M warnings.' tally."""
    def split_location(source_location):
        parts = source_location.rsplit(":", 2)
        return tuple(parts) if len(parts) == 3 else (source_location, "", "")

    adoption_line = (
        f"honest-check: adoption level {report['adoption']} — "
        f"{report['enforced_count']} of {report['total_count']} rules enforced."
    )
    lines = [adoption_line, ""]
    for diagnostic in report["diagnostics"]:
        file_name, line, col = split_location(diagnostic["source_location"])
        lines.append(
            f"{file_name}:{line}:{col}: {diagnostic['severity']} {diagnostic['rule_id']}"
        )
        lines.append(f"  {diagnostic['message']}")
        if diagnostic["context"]:
            lines.append(f"  | {diagnostic['context']}")
        lines.append("")
    lines.append(f"Found {report['errors']} errors, {report['warnings']} warnings.")
    return "\n".join(lines)


def format_json(report):
    """Render the JSON machine format for CI and tooling (section 6.2)."""
    def split_location(source_location):
        parts = source_location.rsplit(":", 2)
        return tuple(parts) if len(parts) == 3 else (source_location, "", "")

    diagnostics = []
    for diagnostic in report["diagnostics"]:
        file_name, line, col = split_location(diagnostic["source_location"])
        diagnostics.append(
            {
                "rule": diagnostic["rule_id"],
                "severity": diagnostic["severity"],
                "file": file_name,
                "line": line,
                "col": col,
                "message": diagnostic["message"],
                "context": diagnostic["context"],
                "fixable": diagnostic["fixable"],
            }
        )
    document = {
        "version": "0.1",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": {
            "errors": report["errors"],
            "warnings": report["warnings"],
            "infos": report["infos"],
            "adoption": report["adoption"],
            "enforced_rules": report["enforced_count"],
        },
        "diagnostics": diagnostics,
        "rule_counts": report["rule_counts"],
    }
    return json.dumps(document, indent=2)


def format_github(report):
    """Render GitHub Actions workflow-command annotations (section 6.3): one '::error' or
    '::warning' line per finding, with a leading notice carrying the adoption line."""
    def split_location(source_location):
        parts = source_location.rsplit(":", 2)
        return tuple(parts) if len(parts) == 3 else (source_location, "", "")

    adoption_line = (
        f"honest-check: adoption level {report['adoption']} — "
        f"{report['enforced_count']} of {report['total_count']} rules enforced."
    )
    lines = [f"::notice::{adoption_line}"]
    for diagnostic in report["diagnostics"]:
        file_name, line, col = split_location(diagnostic["source_location"])
        command = "error" if diagnostic["severity"] == "error" else "warning"
        lines.append(
            f"::{command} file={file_name},line={line},col={col},"
            f"title={diagnostic['rule_id']}::{diagnostic['message']}"
        )
    return "\n".join(lines)


def format_junit(report):
    """Render JUnit XML (section 6.4): a <testsuites name="honest-check"> document with one
    <testcase>/<failure> per finding."""
    def split_location(source_location):
        parts = source_location.rsplit(":", 2)
        return tuple(parts) if len(parts) == 3 else (source_location, "", "")

    lines = ['<testsuites name="honest-check">']
    for diagnostic in report["diagnostics"]:
        file_name, line, col = split_location(diagnostic["source_location"])
        lines.append(f'  <testsuite name="{file_name}" failures="1">')
        lines.append(
            f'    <testcase name="{diagnostic["rule_id"]}:{line}" classname="{file_name}">'
        )
        lines.append(f'      <failure message="{diagnostic["message"]}">')
        lines.append(f"        Line {line}: {diagnostic['context']}")
        lines.append("      </failure>")
        lines.append("    </testcase>")
        lines.append("  </testsuite>")
    lines.append("</testsuites>")
    return "\n".join(lines)


def resolve_exit_code(report):
    """Decide the process exit code from the prepared report (section 2.1). A --report run
    is always 0 (it reports, it does not judge); otherwise 1 when any error survived and 0
    when none did. It never returns 2: that catch-all belongs to the door."""
    if report["report_mode"]:
        return "0"
    if report["errors"] > 0:
        return "1"
    return "0"


# The format dispatch (section 6): the resolved --format word picks the renderer. The key
# is bounded to a Format member by parse_args before this runs, so the table is total over
# what it can receive and needs no wildcard row — 'human' is the resolved fallback.
by_format = {
    "human": format_human,
    "json": format_json,
    "github": format_github,
    "junit": format_junit,
}

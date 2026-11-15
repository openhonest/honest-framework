"""The CLI report path: argument parsing, the adoption-level rule sets (§9.4), the
report preparation and the four formatters (§6), the exit-code decision and the
blocking filter (§2.1, §2.3). All pure: data in, rendered text or a code out."""

import datetime
import json
import xml.etree.ElementTree as ElementTree

from ._util import choose, pick, read_or

_SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}

_FORMATS = {"human", "json", "github", "junit"}
_SEVERITIES = {"error", "warning", "info"}

# The section 9.4 adoption-level rule sets, declared as data.
_ALWAYS = {"HC-SYN", "HC-SUP001", "HC-SUP002"}
_STRUCTURAL = {"HC-P001", "HC-P003", "HC-P007", "HC-P011", "HC-P016", "HC-P015", "HC-P019", "HC-P020"}
_BOUNDARY = {"HC-P002", "HC-P004", "HC-P005", "HC-P006", "HC-P010", "HC-P013", "HC-ST001", "HC-A001", "HC-A002"}
_TYPED = {
    "HC001", "HC002", "HC003", "HC004", "HC005", "HC006", "HC007", "HC008", "HC009",
    "HC010", "HC011", "HC-SM01", "HC-SM02", "HC-SM03", "HC-SM04", "HC-SM05",
    "HC-P014", "HC-P017", "HC-P018",
}
_DECLARED = {
    "HC-R001", "HC-R002", "HC-R003", "HC-R004", "HC-R005", "HC-OR001", "HC-OR003",
    "HC-REF001", "HC-REF002", "HC-REF003", "HC-REF004", "HC-REF005", "HC-REF006",
    "HC-REF007", "HC-REF008", "HC-REF012", "HC-ST002", "HC-HF001", "HC-HF002",
}

_LEVEL_ORDER = ["Structural", "Boundary", "Typed", "Declared"]
_LEVEL_ADDITIONS = {
    "Structural": _STRUCTURAL,
    "Boundary": _BOUNDARY,
    "Typed": _TYPED,
    "Declared": _DECLARED,
}

_TOTAL_RULES = 58


def enforced_rules_of(level):
    """Every HC rule enforced at the given adoption level — the cumulative §9.4
    membership, always_rules plus every level up to and including this one."""
    index = _LEVEL_ORDER.index(level)
    result = set(_ALWAYS)
    for name in _LEVEL_ORDER[: index + 1]:
        result |= read_or(_LEVEL_ADDITIONS, name, set())
    return sorted(result)


# ---- argument parsing (§2.1) ------------------------------------------------


def _value_handler(key):
    def handle(token, argv, i, args):
        args[key] = argv[i + 1]
        return i + 2

    return handle


def _list_handler(key):
    def handle(token, argv, i, args):
        args[key].append(argv[i + 1])
        return i + 2

    return handle


def _bool_handler(key):
    def handle(token, argv, i, args):
        args[key] = True
        return i + 1

    return handle


def _positional_handler(token, argv, i, args):
    args["paths"].append(token)
    return i + 1


_FLAG_HANDLERS = {
    "--config": _value_handler("config_path"),
    "--format": _value_handler("format"),
    "--severity": _value_handler("severity"),
    "--declaration": _value_handler("declaration"),
    "--exports": _value_handler("exports"),
    "--rule": _list_handler("include_rules"),
    "--no-rule": _list_handler("exclude_rules"),
    "--report": _bool_handler("report_mode"),
}


def parse_args(argv):
    """Resolve the raw argv into the bounded CliArgs, absence filled at the boundary:
    format 'human', severity 'warning', the rest empty (§2.1)."""
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
    index = 0
    count = len(argv)
    while index < count:
        token = argv[index]
        handler = read_or(_FLAG_HANDLERS, token, _positional_handler)
        index = handler(token, argv, index, args)
    args["format"] = choose(args["format"] in _FORMATS, args["format"], "human")
    args["severity"] = choose(args["severity"] in _SEVERITIES, args["severity"], "warning")
    return args


# ---- report preparation (§2.1, §9.4) ----------------------------------------


def _downgrade(diag, enforced):
    return choose(diag["rule_id"] in enforced, diag, {**diag, "severity": "info"})


def _apply_rule_filters(diagnostics, args):
    include = args["include_rules"]
    exclude = args["exclude_rules"]
    included = pick(
        len(include) == 0,
        lambda: diagnostics,
        lambda: [d for d in filter(lambda d: d["rule_id"] in include, diagnostics)],
    )
    return [d for d in filter(lambda d: d["rule_id"] not in exclude, included)]


def _count_severity(diagnostics, severity):
    return len([d for d in filter(lambda d: d["severity"] == severity, diagnostics)])


def _rule_counts(diagnostics):
    counts = {}
    for diag in diagnostics:
        counts[diag["rule_id"]] = read_or(counts, diag["rule_id"], 0) + 1
    return counts


def prepare_report(diagnostics, args, adoption):
    """Apply the adoption downgrade, the severity threshold and the rule filters,
    then count the survivors into the CheckReport (§2.1, §6, §9.4)."""
    enforced = set(enforced_rules_of(adoption))
    downgraded = [_downgrade(d, enforced) for d in diagnostics]
    threshold = _SEVERITY_RANK[args["severity"]]
    above = [d for d in filter(lambda d: _SEVERITY_RANK[d["severity"]] >= threshold, downgraded)]
    filtered = _apply_rule_filters(above, args)
    return {
        "diagnostics": filtered,
        "errors": _count_severity(filtered, "error"),
        "warnings": _count_severity(filtered, "warning"),
        "infos": _count_severity(filtered, "info"),
        "rule_counts": pick(args["report_mode"], lambda: _rule_counts(filtered), lambda: {}),
        "adoption": adoption,
        "enforced_count": len(enforced),
        "total_count": _TOTAL_RULES,
        "report_mode": args["report_mode"],
    }


# ---- the formatters (§6) ----------------------------------------------------


def _adoption_line(report):
    return (
        f"honest-check: adoption level {report['adoption']} — "
        f"{report['enforced_count']} of {report['total_count']} rules enforced."
    )


def _finding_blocks(report):
    out = []
    for diag in report["diagnostics"]:
        out.append(f"{diag['source_location']}: {diag['severity']} {diag['rule_id']}")
        out.append(diag["message"])
        out.append(diag["context"])
    out.append(f"Found {report['errors']} errors, {report['warnings']} warnings.")
    return out


def _rule_table(report):
    out = [f"{rule}: {count}" for rule, count in report["rule_counts"].items()]
    out.append(f"Found {report['errors']} errors, {report['warnings']} warnings.")
    return out


def format_human(report):
    """Render the human-readable CLI default: the adoption line, one block per
    finding, then the tally — or the per-rule table under --report (§6.1)."""
    body = pick(report["report_mode"], lambda: _rule_table(report), lambda: _finding_blocks(report))
    return "\n".join([_adoption_line(report)] + body)


def _split_location(location):
    parts = location.rsplit(":", 2)
    return pick(
        len(parts) == 3 and parts[1].isdigit(),
        lambda: (parts[0], int(parts[1]), int(parts[2])),
        lambda: (location, None, None),
    )


def _json_diagnostic(diag):
    file, line, col = _split_location(diag["source_location"])
    return {
        "file": file,
        "line": line,
        "col": col,
        "rule": diag["rule_id"],
        "severity": diag["severity"],
        "message": diag["message"],
        "context": diag["context"],
        "fixable": diag["fixable"],
    }


def format_json(report):
    """Render the JSON machine format: version, timestamp, a summary with counts,
    adoption and enforced_rules, and the split diagnostics (§6.2)."""
    obj = {
        "version": "1.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": {
            "errors": report["errors"],
            "warnings": report["warnings"],
            "infos": report["infos"],
            "adoption": report["adoption"],
            "enforced_rules": report["enforced_count"],
        },
        "diagnostics": [_json_diagnostic(d) for d in report["diagnostics"]],
    }
    return json.dumps(obj)


def _github_line(diag):
    file, line, col = _split_location(diag["source_location"])
    command = choose(diag["severity"] == "error", "::error", "::warning")
    return f"{command} file={file},line={line},col={col},title={diag['rule_id']}::{diag['message']}"


def format_github(report):
    """Render GitHub Actions annotations: one ::error/::warning line per finding
    (§6.3)."""
    notice = f"::notice::honest-check adoption level {report['adoption']}"
    return "\n".join([notice] + [_github_line(d) for d in report["diagnostics"]])


def _junit_file_groups(report):
    groups = {}
    for diag in report["diagnostics"]:
        file, line, col = _split_location(diag["source_location"])
        groups.setdefault(file, []).append((diag, line))
    return groups


def format_junit(report):
    """Render JUnit XML: one testsuite per file, a testcase/failure per finding
    (§6.4)."""
    root = ElementTree.Element("testsuites", name="honest-check")
    for file, items in _junit_file_groups(report).items():
        suite = ElementTree.SubElement(root, "testsuite", name=file, failures=str(len(items)))
        for diag, line in items:
            case = ElementTree.SubElement(
                suite, "testcase", name=f"{diag['rule_id']}:{line}", classname=file
            )
            failure = ElementTree.SubElement(case, "failure", message=diag["message"])
            failure.text = diag["context"]
    return ElementTree.tostring(root, encoding="unicode")


def resolve_exit_code(report):
    """The process exit code: '0' always under --report, else '1' on a surviving
    error and '0' otherwise (§2.1)."""
    return pick(report["report_mode"], lambda: "0", lambda: choose(report["errors"] > 0, "1", "0"))


def blocking_findings(diagnostics, threshold):
    """The order-preserving subset of diagnostics whose severity rank reaches the
    threshold (§2.3)."""
    return [d for d in filter(lambda d: _SEVERITY_RANK[d["severity"]] >= threshold, diagnostics)]


def severity_rank(severity):
    """The blocking rank of a severity word, the threshold blocking_findings filters
    by (§2.3)."""
    return read_or(_SEVERITY_RANK, severity, 0)

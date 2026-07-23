"""Output formats (section 6). Pure renderers: diagnostics in, string out.

Format selection is dict-dispatch (`_RENDERERS`), not branching — adding a format is
a row, not a control-flow edit. No I/O here; the CLI boundary prints what these return.
Severity and rule filtering are pure functions too, so the whole report pipeline is
testable as `assert render(filter(...), fmt) == expected`.
"""

import json

from honest_check.adoption import adoption_header, all_rules, enforced_rules
from honest_check.diagnostics import Diagnostic
from honest_check.rules import is_fixable

# Reporting order / threshold for --severity (section 2.1). Higher = more severe.
_SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}


def counts(diagnostics: list[Diagnostic]) -> dict[str, int]:
    """{error, warning, info} totals."""
    totals = {"error": 0, "warning": 0, "info": 0}
    for d in diagnostics:
        totals[d["severity"]] = totals.get(d["severity"], 0) + 1
    return totals


def filter_by_severity(diagnostics: list[Diagnostic], minimum: str) -> list[Diagnostic]:
    """Keep diagnostics at or above the minimum severity (section 2.1, default warning)."""
    floor = _SEVERITY_RANK.get(minimum, _SEVERITY_RANK["warning"])
    return [d for d in diagnostics if _SEVERITY_RANK.get(d["severity"], 0) >= floor]


def filter_by_rule(diagnostics: list[Diagnostic], only: frozenset, suppress: frozenset) -> list[Diagnostic]:
    """Apply --rule (keep only these) and --no-rule (drop these). Empty `only` keeps all."""
    out = []
    for d in diagnostics:
        if only and d["rule"] not in only:
            continue
        if d["rule"] in suppress:
            continue
        out.append(d)
    return out


def has_errors(diagnostics: list[Diagnostic]) -> bool:
    """True if any diagnostic is an error (drives exit code 1)."""
    return any(d["severity"] == "error" for d in diagnostics)


def render_human(diagnostics: list[Diagnostic], level: str) -> str:
    lines = [adoption_header(level)]
    for d in diagnostics:
        lines.append(f"{d['path']}:{d['line']}:{d['col']}: {d['severity']} {d['rule']}")
        lines.append(f"  {d['message']}")
    c = counts(diagnostics)
    lines.append(f"Found {c['error']} error(s), {c['warning']} warning(s), {c['info']} info(s).")
    return "\n".join(lines)


def render_json(diagnostics: list[Diagnostic], level: str) -> str:
    c = counts(diagnostics)
    payload = {
        "version": "0.1",
        "summary": {
            "errors": c["error"],
            "warnings": c["warning"],
            "infos": c["info"],
            "adoption": level,
            "enforced_rules": len(enforced_rules(level)),
        },
        "diagnostics": [
            {
                "rule": d["rule"],
                "severity": d["severity"],
                "file": d["path"],
                "line": d["line"],
                "col": d["col"],
                "message": d["message"],
                "fixable": is_fixable(d["rule"]),
            }
            for d in diagnostics
        ],
    }
    return json.dumps(payload, indent=4)


# GitHub workflow annotation levels (section 6.3); honest-check 'info' maps to 'notice'.
_GITHUB_LEVEL = {"error": "error", "warning": "warning", "info": "notice"}


def render_github(diagnostics: list[Diagnostic], level: str) -> str:
    lines = []
    for d in diagnostics:
        level = _GITHUB_LEVEL.get(d["severity"], "notice")
        message = d["message"].replace("\n", " ")
        lines.append(
            f"::{level} file={d['path']},line={d['line']},col={d['col']},title={d['rule']}::{message}"
        )
    return "\n".join(lines)


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_junit(diagnostics: list[Diagnostic], level: str) -> str:
    c = counts(diagnostics)
    failures = c["error"] + c["warning"]
    rows = [f'<testsuites name="honest-check" failures="{failures}" tests="{len(diagnostics)}">']
    rows.append(f'  <testsuite name="honest-check" failures="{failures}" tests="{len(diagnostics)}">')
    for d in diagnostics:
        name = _xml_escape(f"{d['rule']}:{d['line']}")
        classname = _xml_escape(d["path"])
        rows.append(f'    <testcase name="{name}" classname="{classname}">')
        rows.append(
            f'      <failure message="{_xml_escape(d["message"])}">'
            f"{_xml_escape(d['path'])}:{d['line']}:{d['col']} {d['severity']} {d['rule']}</failure>"
        )
        rows.append("    </testcase>")
    rows.append("  </testsuite>")
    rows.append("</testsuites>")
    return "\n".join(rows)


_RENDERERS = {
    "human": render_human,
    "json": render_json,
    "github": render_github,
    "junit": render_junit,
}


def render(diagnostics: list[Diagnostic], fmt: str, level: str) -> str:
    """Render diagnostics in the named format (dict-dispatch; section 6). Every renderer takes the
    adoption level so the table can dispatch on one uniform signature; the machine-consumed formats
    (github, junit) carry the level in their diagnostics rather than a header, so they ignore it."""
    return _RENDERERS[fmt](diagnostics, level)


def supported_formats() -> list[str]:
    return sorted(_RENDERERS)


def render_report(rows: list[dict], level: str) -> str:
    """The --report table (section 2.1.1): every rule with its finding count, and whether the
    declared level enforces it. It reports, it does not judge — the caller always exits 0."""
    lines = [adoption_header(level), "", f"  {'rule':<12}{'severity':<10}{'findings':>9}  enforced"]
    for row in rows:
        mark = "yes" if row["enforced"] else f"no ({row['introduced']})"
        lines.append(f"  {row['rule']:<12}{row['severity']:<10}{row['findings']:>9}  {mark}")
    return "\n".join(lines)

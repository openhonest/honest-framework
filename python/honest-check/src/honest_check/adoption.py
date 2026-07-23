"""Adoption levels — which rules the codebase being checked currently holds (section 9.4).

Sections 9.1-9.3 grade the checker. This module grades the codebase. An adoption level is a
named, closed set of rules: a codebase declares one, and the level says exactly which rules it
holds, so "clean at level Boundary" means the same thing in every codebase that says it. The bug
category it eliminates is a false guarantee — a project reporting clean because the rule that
mattered to the reader was quietly switched off. A per-rule dial cannot make that claim; a level can.

Pure: diagnostics and a level name in, diagnostics and counts out. Nothing here reads config or
files — the CLI boundary does that and passes the resolved level in.
"""

# Section 9.4 — each level adds these rules to every level below it.
_LEVEL_RULES = {
    "Structural": frozenset({"HC-P001", "HC-P003", "HC-P007", "HC-P011", "HC-P016"}),
    "Boundary": frozenset(
        {"HC-P002", "HC-P004", "HC-P005", "HC-P006", "HC-P010", "HC-P013", "HC-ST001", "HC-A001", "HC-A002"}
    ),
    "Typed": frozenset(
        {f"HC{n:03d}" for n in range(1, 12)}
        | {"HC-SM01", "HC-SM02", "HC-SM03", "HC-SM04", "HC-SM05", "HC-P014", "HC-P017"}
    ),
    "Declared": frozenset(
        {
            "HC-R001",
            "HC-OR001",
            "HC-OR003",
            "HC-REF001",
            "HC-REF002",
            "HC-REF003",
            "HC-REF004",
            "HC-ST002",
            "HC-HF001",
            "HC-HF002",
        }
    ),
}

# Weakest to strictest. The order is the cumulation order, so it is load-bearing.
LEVEL_ORDER = ("Structural", "Boundary", "Typed", "Declared")

# A codebase that does not parse has no level, and the section 7.4 suppression guarantee cannot be
# level-dependent — a low level must never buy the right to hide things.
ALWAYS_ENFORCED = frozenset({"HC-SYN", "HC-SUP001", "HC-SUP002"})

# An absent or unrecognised declaration is held to everything. Silence never buys leniency.
DEFAULT_LEVEL = "Declared"


def resolve_level(configured) -> str:
    """The level to enforce, given whatever `[check] adoption` said (or did not say)."""
    return configured if configured in _LEVEL_RULES else DEFAULT_LEVEL


def enforced_rules(level: str) -> frozenset:
    """Every rule enforced at `level`: its own, all weaker levels', and the always-enforced three. A
    name this table does not know is held to everything, matching resolve_level's default — the
    fallback is fail-closed, so no spelling of the level can ever buy leniency."""
    cumulative = set(ALWAYS_ENFORCED)
    for name in LEVEL_ORDER:
        cumulative |= _LEVEL_RULES[name]
        if name == level:
            break
    return frozenset(cumulative)


def introducing_level(rule: str) -> str:
    """The level at which `rule` starts being enforced; 'every' for the always-enforced three and
    for any rule this table does not place (an unplaced rule is enforced, never silently excused)."""
    for name in LEVEL_ORDER:
        if rule in _LEVEL_RULES[name]:
            return name
    return "every"


def apply_adoption(diagnostics: list, level: str) -> list:
    """Downgrade to `info` every diagnostic whose rule is not enforced at `level` (section 9.4).
    Above-level findings are never dropped — the same treatment a suppressed diagnostic gets, and
    for the same reason: a level states what a codebase holds today, not permission to stop looking."""
    enforced = enforced_rules(level)
    out = []
    for d in diagnostics:
        if d["rule"] in enforced:
            out.append(d)
            continue
        out.append(
            {
                **d,
                "severity": "info",
                "message": f"{d['message']} Not enforced at adoption level {level}; "
                f"introduced at {introducing_level(d['rule'])}.",
            }
        )
    return out


def all_rules() -> frozenset:
    """Every rule an adoption level can place, including the always-enforced three."""
    return enforced_rules(LEVEL_ORDER[-1])


def rule_report(diagnostics: list, level: str) -> list:
    """Per-rule findings for `--report` (section 2.1.1): one row per rule, ordered by findings
    descending then rule name, each carrying whether the level enforces it and which level
    introduces it. Counts the diagnostics as given, before any adoption downgrade."""
    enforced = enforced_rules(level)
    counts: dict[str, int] = {rule: 0 for rule in all_rules()}
    severities: dict[str, str] = {}
    for d in diagnostics:
        counts[d["rule"]] = counts.get(d["rule"], 0) + 1
        severities[d["rule"]] = d["severity"]
    return [
        {
            "rule": rule,
            "severity": severities.get(rule, "—"),
            "findings": counts[rule],
            "enforced": rule in enforced,
            "introduced": introducing_level(rule),
        }
        for rule in sorted(counts, key=lambda name: (-counts[name], name))
    ]


def adoption_header(level: str) -> str:
    """The one line every run opens with, so a passing run always says what it proved (section 9.4)."""
    return f"honest-check: adoption level {level} — {len(enforced_rules(level))} of {len(all_rules())} rules enforced."

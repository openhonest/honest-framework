"""feature_gen — declared in feature_gen.hd.

Reads one module's .hd declaration and writes its .feature file: one Scenario per declared
function, Given/When/Then built mechanically from the signature, invokes list, and side
effects. No prose beyond what the declaration itself says.

Usage:
    uv run python feature_gen.py <module.hd> <module.feature>
"""

from __future__ import annotations

import sys

from honest_design import read_hd

_COLUMN_HEADING = {
    1: "# ---- the doors and readers ----",
    2: "# ---- the orchestrators ----",
    3: "# ---- the pure core ----",
    4: "# ---- the writers ----",
}


def type_text(t: list) -> str:
    """Renders a .hd type (a union of named atoms) back to its source spelling."""
    return " | ".join(
        atom["name"] + (f"<{', '.join(type_text(a) for a in atom['args'])}>" if atom["args"] else "")
        for atom in t
    )


def given_clause(fn: dict) -> str:
    """One Given line naming every parameter the function declares, and its type."""
    params = fn["params"]
    if not params:
        return "Given no input"
    return "Given " + " and ".join(f"{p['name']}: {type_text(p['type'])}" for p in params)


def when_clause(fn: dict) -> str:
    """One When line naming the function."""
    return f"When {fn['name']} is called"


_INLINE_INVOKES_LIMIT = 6


def then_clause(fn: dict) -> str:
    """One Then line. When the function's own .hd note is non-empty, that note is the domain
    description a person already wrote and is used as-is. Otherwise the line falls back to the
    return type and side effects; an invokes list of six or fewer also joins this line, a longer
    list is left to invoke_lines so the sentence does not run on."""
    if fn["note"].strip():
        return f"Then {fn['note']}"
    parts = [f"it returns {type_text(fn['ret'])}"]
    if fn["invokes"] and len(fn["invokes"]) <= _INLINE_INVOKES_LIMIT:
        parts.append(f"calling {', '.join(fn['invokes'])}")
    if fn["side_effects"]:
        parts.append("with side effects: " + ", ".join(f"{se['direction']} {se['target']}" for se in fn["side_effects"]))
    return "Then " + ", ".join(parts)


def invoke_lines(fn: dict) -> list:
    """One 'And it calls NAME' line per callee, produced only when the invokes list has more than
    six names, the point where the Then sentence stops reading as a sentence."""
    if len(fn["invokes"]) <= _INLINE_INVOKES_LIMIT:
        return []
    return [f"    And it calls {name}" for name in fn["invokes"]]


def scenario_text(fn: dict) -> str:
    """One Scenario block: the title line, then Given, When, Then, and an And line per callee when
    the invokes list was too long for Then."""
    lines = [
        f"  Scenario: {fn['name']}",
        f"    {given_clause(fn)}",
        f"    {when_clause(fn)}",
        f"    {then_clause(fn)}",
    ]
    lines.extend(invoke_lines(fn))
    return "\n".join(lines)


def column_heading(column: int) -> str:
    """The comment header for one column."""
    return _COLUMN_HEADING[column]


def group_by_column(functions: list) -> dict:
    """Groups the module's functions by column, keeping each group in declared order."""
    groups: dict[int, list] = {}
    for fn in functions:
        groups.setdefault(fn["column"], []).append(fn)
    return groups


def feature_text(module_name: str, functions: list) -> str:
    """Assembles the full .feature text: the header, then one column-headed block per column."""
    groups = group_by_column(functions)
    lines = [f"Feature: {module_name} — generated, one scenario per function ({len(functions)} total)", ""]
    for column in sorted(groups):
        lines.append(column_heading(column))
        lines.append("")
        for fn in groups[column]:
            lines.append(scenario_text(fn))
            lines.append("")
    return "\n".join(lines)


def read_module(hd_path: str) -> dict:
    """Reads the .hd file through honest-design's read_hd and returns its first declared module,
    or a Fault when the file is malformed or declares no module."""
    with open(hd_path) as f:
        source = f.read()
    doc = read_hd(source)
    if "err" in doc:
        return {"what": doc["err"]["message"], "instead": "fix the .hd and retry"}
    modules = doc["ok"]["modules"]
    if not modules:
        return {"what": f"{hd_path} declares no module", "instead": "add a module declaration"}
    return modules[0]


def write_feature(feature_path: str, text: str) -> bool:
    with open(feature_path, "w") as f:
        f.write(text)
    return True


def generate_feature(hd_path: str, feature_path: str):
    """Reads the module, builds the feature text, writes it; a read fault short-circuits before
    any write."""
    module = read_module(hd_path)
    if "functions" not in module:
        return module  # Fault
    write_feature(feature_path, feature_text(module["name"], module["functions"]))
    return True


def run(hd_path: str, feature_path: str):
    return generate_feature(hd_path, feature_path)


if __name__ == "__main__":
    hd_path, feature_path = sys.argv[1], sys.argv[2]
    result = run(hd_path, feature_path)
    if result is not True:
        sys.stderr.write(f"feature_gen: {result['what']} — {result['instead']}\n")
        sys.exit(1)
    print(f"wrote {feature_path}")

"""The parse contract (sections 3, 3.1): source text in, a Result out, no I/O.

`parse_feature` reads the lines one at a time, folding an immutable state forward. Each line is
sorted into exactly one line kind by an ordered table (first match wins — a `#` line is a comment
even if it begins with "Feature"); a second table maps line kind to a pure handler that returns
the new state. No `if/elif` ladder on keywords: both the sorting and the handling are table
lookups. A malformed feature returns `err(StepFault bad_feature_syntax)`, never a raised exception.
"""

from honest_type import err, ok

from honest_gherkin.ir import STEP_KINDS, step_fault


def _is_blank(line):
    return line.strip() == ""


def _is_comment(line):
    return line.strip().startswith("#")


def _is_tag(line):
    return line.strip().startswith("@")


def _is_feature(line):
    return line.strip().startswith("Feature:")


def _is_scenario(line):
    return line.strip().startswith("Scenario:")


def _is_step(line):
    return line.strip().partition(" ")[0].lower() in STEP_KINDS


# Ordered classification table — first match wins; order is significant (comment before feature).
_LINE_KINDS = (
    ("blank", _is_blank),
    ("comment", _is_comment),
    ("tag", _is_tag),
    ("feature", _is_feature),
    ("scenario", _is_scenario),
    ("step", _is_step),
)


def _classify(line):
    for kind, predicate in _LINE_KINDS:
        if predicate(line):
            return kind
    return "description"


def _flush(state):
    """Move the scenario under construction into the completed list, if there is one."""
    if state["current"] is None:
        return state
    return {**state, "scenarios": [*state["scenarios"], state["current"]], "current": None}


def _on_ignore(state, line, n):
    return state


def _on_tag(state, line, n):
    return {**state, "pending_tags": [*state["pending_tags"], *(t for t in line.split() if t.startswith("@"))]}


def _on_feature(state, line, n):
    return {**state, "name": line.strip()[len("Feature:"):].strip(), "in_header": True}


def _on_scenario(state, line, n):
    state = _flush(state)
    name = line.strip()[len("Scenario:"):].strip()
    errors = state["errors"] if name else [*state["errors"], step_fault("bad_feature_syntax", f"line {n}: scenario has no name", step_text=line.strip())]
    current = {"name": name, "steps": [], "tags": state["pending_tags"], "source_line": n}
    return {**state, "current": current, "pending_tags": [], "in_header": False, "last_resolved_kind": "", "errors": errors}


def _on_step(state, line, n):
    if state["current"] is None:
        return {**state, "errors": [*state["errors"], step_fault("bad_feature_syntax", f"line {n}: step outside a scenario", step_text=line.strip())]}
    keyword, _, text = line.strip().partition(" ")
    kind = keyword.lower()
    resolved = kind if kind in ("given", "when", "then") else state["last_resolved_kind"]
    step = {"kind": kind, "resolved_kind": resolved, "text": text.strip(), "source_line": n}
    current = {**state["current"], "steps": [*state["current"]["steps"], step]}
    return {**state, "current": current, "last_resolved_kind": resolved}


def _on_description(state, line, n):
    if state["in_header"]:
        return {**state, "description_lines": [*state["description_lines"], line.strip()]}
    return {**state, "errors": [*state["errors"], step_fault("bad_feature_syntax", f"line {n}: unexpected text outside a scenario", step_text=line.strip())]}


_HANDLERS = {
    "blank": _on_ignore,
    "comment": _on_ignore,
    "tag": _on_tag,
    "feature": _on_feature,
    "scenario": _on_scenario,
    "step": _on_step,
    "description": _on_description,
}


def parse_feature(source, source_path):
    """Parse Gherkin source into a Feature (sections 3, 3.1). Pure. Returns ok(Feature), or
    err(StepFault code='bad_feature_syntax') with the first structural error."""
    state = {
        "name": "",
        "description_lines": [],
        "scenarios": [],
        "pending_tags": [],
        "current": None,
        "last_resolved_kind": "",
        "in_header": True,
        "errors": [],
    }
    for line_no, line in enumerate(source.splitlines(), start=1):
        state = _HANDLERS[_classify(line)](state, line, line_no)
    state = _flush(state)
    if not state["name"]:
        state = {**state, "errors": [*state["errors"], step_fault("bad_feature_syntax", "no Feature declared")]}
    if state["errors"]:
        return err(state["errors"][0])
    feature = {
        "name": state["name"],
        "description": " ".join(state["description_lines"]),
        "scenarios": state["scenarios"],
        "background_steps": [],
        "source_path": source_path,
    }
    return ok(feature)

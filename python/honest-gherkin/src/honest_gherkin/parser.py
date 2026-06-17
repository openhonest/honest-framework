"""Parse a Gherkin-subset .feature source string into a Feature IR.

Pure function. Source string in, Feature TypedDict out. No I/O.

Grammar handled (M1):
    (comment | blank | tag-line)*
    "Feature:" <name>
    <description-lines>*
    scenario+

    scenario = tag-line* "Scenario:" <name> step+
    step = ("Given" | "When" | "Then" | "And" | "But") <text>

Comments start with '#'. Tags start with '@' and attach to the next
scenario. Blank lines are ignored. Indentation is irrelevant — we parse
line by line with whitespace stripped.

Dispatch is a table of line-kind → handler. No if/elif ladder on keywords.
"""
from __future__ import annotations

from typing import Callable

from honest_gherkin.types import (
    FAULT_BAD_FEATURE_SYNTAX,
    Feature,
    Scenario,
    Step,
    STEP_KINDS,
)


# --- Line classification ---------------------------------------------------


# A parser state is a dict that gets folded forward as each line is
# consumed. Honest-code: pure function over state; no mutation.
_State = dict


def _initial_state(source_path: str) -> _State:
    return {
        "source_path": source_path,
        "feature_name": "",
        "description_lines": [],
        "scenarios": [],
        "pending_tags": [],
        "current_scenario": None,
        "last_step_kind": None,
        "in_feature_header": True,
        "errors": [],
    }


def _line_kind(line: str) -> str:
    """Return one of: 'blank', 'comment', 'tag', 'feature', 'scenario',
    'step', 'description'. Pure function.

    Dispatch via ordered predicate table. The first match wins.
    """
    stripped = line.strip()
    match = _first_matching_kind(stripped)
    return match


_KIND_RULES: list[tuple[Callable[[str], bool], str]] = [
    (lambda s: s == "",                        "blank"),
    (lambda s: s.startswith("#"),              "comment"),
    (lambda s: s.startswith("@"),              "tag"),
    (lambda s: s.lower().startswith("feature:"),  "feature"),
    (lambda s: s.lower().startswith("scenario:"), "scenario"),
    (lambda s: _is_step_prefix(s),             "step"),
]


def _first_matching_kind(stripped: str) -> str:
    for predicate, kind in _KIND_RULES:
        if predicate(stripped):
            return kind
    # Anything else in the feature header is description text.
    return "description"


_STEP_KEYWORDS = ("given ", "when ", "then ", "and ", "but ")


def _is_step_prefix(stripped: str) -> bool:
    lower = stripped.lower()
    return any(lower.startswith(k) for k in _STEP_KEYWORDS)


def _step_kind(stripped: str) -> str:
    """Return the kind keyword (lowercase) from a step line."""
    lower = stripped.lower()
    for k in ("given", "when", "then", "and", "but"):
        if lower.startswith(k + " ") or lower == k:
            return k
    return ""


def _step_text(stripped: str) -> str:
    """Return the step text with the keyword stripped."""
    lower = stripped.lower()
    for k in ("given", "when", "then", "and", "but"):
        if lower.startswith(k + " "):
            return stripped[len(k) + 1 :].strip()
        if lower == k:
            return ""
    return stripped


# --- Line handlers ---------------------------------------------------------


def _handle_blank(state: _State, _line: str, _line_no: int) -> _State:
    return state


def _handle_comment(state: _State, _line: str, _line_no: int) -> _State:
    return state


def _handle_tag(state: _State, line: str, _line_no: int) -> _State:
    tags = [t for t in line.strip().split() if t.startswith("@")]
    return {**state, "pending_tags": state["pending_tags"] + tags}


def _handle_feature(state: _State, line: str, _line_no: int) -> _State:
    name = line.strip().split(":", 1)[1].strip()
    return {**state, "feature_name": name, "in_feature_header": True}


def _handle_scenario(state: _State, line: str, line_no: int) -> _State:
    name = line.strip().split(":", 1)[1].strip()
    new_state = _flush_current_scenario(state)
    new_scenario: Scenario = {
        "name": name,
        "steps": [],
        "tags": list(new_state["pending_tags"]),
        "source_line": line_no,
    }
    return {
        **new_state,
        "current_scenario": new_scenario,
        "pending_tags": [],
        "last_step_kind": None,
        "in_feature_header": False,
    }


def _handle_step(state: _State, line: str, line_no: int) -> _State:
    stripped = line.strip()
    kind = _step_kind(stripped)
    text = _step_text(stripped)
    # and / but inherit the previous kind for grouping, but keep their own
    # literal kind on the step so the runner can dispatch appropriately.
    step: Step = {
        "kind": kind,
        "text": text,
        "source_line": line_no,
    }
    current = state.get("current_scenario")
    if current is None:
        return {**state, "errors": state["errors"] + [
            (line_no, "step outside any scenario")
        ]}
    updated = {**current, "steps": current["steps"] + [step]}
    resolved_kind = kind if kind in ("given", "when", "then") else (
        state.get("last_step_kind") or kind
    )
    return {
        **state,
        "current_scenario": updated,
        "last_step_kind": resolved_kind,
    }


def _handle_description(state: _State, line: str, _line_no: int) -> _State:
    if not state["in_feature_header"]:
        return state
    return {
        **state,
        "description_lines": state["description_lines"] + [line.rstrip()],
    }


# Dispatch table: line kind → handler. Replaces if/elif ladder.
_HANDLERS: dict[str, Callable[[_State, str, int], _State]] = {
    "blank":       _handle_blank,
    "comment":     _handle_comment,
    "tag":         _handle_tag,
    "feature":     _handle_feature,
    "scenario":    _handle_scenario,
    "step":        _handle_step,
    "description": _handle_description,
}


# --- Finalisation ----------------------------------------------------------


def _flush_current_scenario(state: _State) -> _State:
    current = state.get("current_scenario")
    if current is None:
        return state
    return {
        **state,
        "scenarios": state["scenarios"] + [current],
        "current_scenario": None,
    }


# --- Entry point -----------------------------------------------------------


def parse_feature(source: str, source_path: str) -> Feature:
    """Pure function. Source text → Feature IR.

    Raises ValueError with fault_code `bad_feature_syntax` for malformed
    input (e.g. a step declared outside any scenario).
    """
    state = _initial_state(source_path)
    for line_no, line in enumerate(source.splitlines(), start=1):
        kind = _line_kind(line)
        handler = _HANDLERS[kind]
        state = handler(state, line, line_no)

    state = _flush_current_scenario(state)

    if state["errors"]:
        first_line, message = state["errors"][0]
        raise ValueError(
            f"{FAULT_BAD_FEATURE_SYNTAX} at line {first_line}: {message}"
        )

    return Feature(
        name=state["feature_name"],
        description="\n".join(state["description_lines"]).strip(),
        scenarios=state["scenarios"],
        background_steps=[],
        source_path=source_path,
    )

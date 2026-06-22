"""The source-level IR and bounded vocabularies (sections 2, 7): all data, no behaviour.

A Feature, Scenario, and Step are TypedDicts. The step kinds and fault codes are closed
frozensets — honest-test enumerates them, honest-check treats them as discriminant sets. A
StepFault is a fault carried as data, never raised.
"""

from typing import Any, TypedDict

STEP_KIND_GIVEN = "given"
STEP_KIND_WHEN = "when"
STEP_KIND_THEN = "then"
STEP_KIND_AND = "and"
STEP_KIND_BUT = "but"
STEP_KINDS = frozenset({"given", "when", "then", "and", "but"})

FAULT_STEP_UNMATCHED = "step_unmatched"
FAULT_AMBIGUOUS_STEP = "ambiguous_step"
FAULT_ASSERTION_FAILED = "assertion_failed"
FAULT_STEP_ERRORED = "step_errored"
FAULT_BAD_FEATURE_SYNTAX = "bad_feature_syntax"
FAULT_CODES = frozenset({"step_unmatched", "ambiguous_step", "assertion_failed", "step_errored", "bad_feature_syntax"})


class Step(TypedDict, total=False):
    kind: str            # the literal keyword, lowercased: one of STEP_KINDS
    resolved_kind: str   # given/when/then, or what And/But inherit from the most recent of those
    text: str            # the step text with the keyword stripped
    source_line: int


class Scenario(TypedDict):
    name: str
    steps: list[Step]
    tags: list[str]
    source_line: int


class Feature(TypedDict):
    name: str
    description: str
    scenarios: list[Scenario]
    background_steps: list[Step]   # reserved; always [] in M1
    source_path: str


class CompiledPattern(TypedDict):
    regex: str                          # the anchored host regex with named capture groups
    captures: list[dict[str, str]]      # one {name, type} per placeholder, in order; type drives bind-time coercion


class StepFault(TypedDict):
    code: str            # one of FAULT_CODES
    scenario_name: str
    step_text: str
    detail: str


def step_fault(code, detail, scenario_name="", step_text="") -> StepFault:
    """A StepFault (section 7): a fault carried as data, never raised."""
    return {"code": code, "scenario_name": scenario_name, "step_text": step_text, "detail": detail}

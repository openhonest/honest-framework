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
# Built from the named constants so the set and its members are one source of truth (section 2.1):
# a member can never drift from its constant, and dropping a constant breaks the import, not silently.
STEP_KINDS = frozenset({STEP_KIND_GIVEN, STEP_KIND_WHEN, STEP_KIND_THEN, STEP_KIND_AND, STEP_KIND_BUT})

FAULT_STEP_UNMATCHED = "step_unmatched"
FAULT_AMBIGUOUS_STEP = "ambiguous_step"
FAULT_ASSERTION_FAILED = "assertion_failed"
FAULT_STEP_ERRORED = "step_errored"
FAULT_BAD_FEATURE_SYNTAX = "bad_feature_syntax"
FAULT_CODES = frozenset({FAULT_STEP_UNMATCHED, FAULT_AMBIGUOUS_STEP, FAULT_ASSERTION_FAILED, FAULT_STEP_ERRORED, FAULT_BAD_FEATURE_SYNTAX})

STEP_STATUSES = frozenset({"ok", "failed", "unmatched", "ambiguous", "errored"})
SCENARIO_STATUSES = frozenset({"ok", "err", "skipped"})


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


class StepPattern(TypedDict):
    kind: str            # one of STEP_KINDS: the keyword this pattern registers under
    pattern: str         # the {name}/{name:type} source pattern, compiled on demand by match_step
    handler: Any         # StepHandler: (context, **captures) -> context; carried, invoked by the runner


class StepRegistry(TypedDict):
    patterns: list[StepPattern]   # registration is a value, never a module global (section 10.5)


class StepMatch(TypedDict):
    pattern: StepPattern          # the single pattern that matched
    captures: dict[str, Any]      # placeholder bindings, coerced per the pattern's recorded types


class StepResult(TypedDict):
    step: Step
    status: str                   # one of STEP_STATUSES
    fault: Any                    # StepFault, or None iff status == "ok"


class ScenarioReport(TypedDict):
    name: str
    status: str                   # one of SCENARIO_STATUSES
    step_results: list[StepResult]
    duration_ms: int


class FeatureReport(TypedDict):
    feature_name: str
    source_path: str
    scenarios: list[ScenarioReport]
    total_passed: int
    total_failed: int


class StepFault(TypedDict):
    code: str            # one of FAULT_CODES
    scenario_name: str
    step_text: str
    detail: str


def step_fault(code, detail, scenario_name="", step_text="") -> StepFault:
    """A StepFault (section 7): a fault carried as data, never raised."""
    return {"code": code, "scenario_name": scenario_name, "step_text": step_text, "detail": detail}

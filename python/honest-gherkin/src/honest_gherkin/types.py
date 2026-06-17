"""honest-gherkin IR. All TypedDicts. No classes. No methods.

Matches the declarations in examples/honest-gherkin.hd. Keep in sync.
"""
from __future__ import annotations

from typing import Callable, TypedDict


# --- Source-level IR --------------------------------------------------------


class Step(TypedDict):
    """One Given/When/Then/And/But line from a .feature file."""
    kind: str          # "given" | "when" | "then" | "and" | "but"
    text: str
    source_line: int


class Scenario(TypedDict):
    """One Scenario block: name + ordered list of steps."""
    name: str
    steps: list[Step]
    tags: list[str]
    source_line: int


class Feature(TypedDict):
    """One .feature file: name, description, scenarios, background steps."""
    name: str
    description: str
    scenarios: list[Scenario]
    background_steps: list[Step]
    source_path: str


# --- Registry + runtime -----------------------------------------------------


# A step handler takes an immutable context and named args bound from the
# regex match, and returns a new context. Purity is a convention, not
# enforced here; honest-check rule HC-P003 catches mutation at the spec
# layer, not at runtime.
StepHandler = Callable[..., dict]


class StepPattern(TypedDict):
    """One registered pattern: kind + regex source + handler callable."""
    kind: str
    pattern: str
    handler: StepHandler


class StepRegistry(TypedDict):
    """Flat list of declared patterns. No hidden state."""
    patterns: list[StepPattern]


class StepMatch(TypedDict):
    """Result of matching a step text against the registry."""
    pattern: StepPattern
    captures: dict[str, str]


# --- Results ---------------------------------------------------------------


class StepFault(TypedDict):
    """Structured failure. Data, not an exception."""
    code: str          # step_unmatched | ambiguous_step | assertion_failed | step_errored | bad_feature_syntax
    scenario_name: str
    step_text: str
    detail: str


class StepResult(TypedDict):
    """What happened when we tried to run one step."""
    step: Step
    status: str        # ok | failed | unmatched | ambiguous | errored
    fault: StepFault | None


class ScenarioReport(TypedDict):
    """Aggregate of every step's result for one scenario."""
    name: str
    status: str        # ok | err | skipped
    step_results: list[StepResult]
    duration_ms: int


class FeatureReport(TypedDict):
    """Aggregate across every scenario in one .feature file."""
    feature_name: str
    source_path: str
    scenarios: list[ScenarioReport]
    total_passed: int
    total_failed: int


# --- Bounded vocabularies (for honest-test / honest-check) ------------------

STEP_KIND_GIVEN = "given"
STEP_KIND_WHEN = "when"
STEP_KIND_THEN = "then"
STEP_KIND_AND = "and"
STEP_KIND_BUT = "but"

STEP_KINDS: frozenset[str] = frozenset({
    STEP_KIND_GIVEN, STEP_KIND_WHEN, STEP_KIND_THEN,
    STEP_KIND_AND, STEP_KIND_BUT,
})

STEP_STATUS_OK = "ok"
STEP_STATUS_FAILED = "failed"
STEP_STATUS_UNMATCHED = "unmatched"
STEP_STATUS_AMBIGUOUS = "ambiguous"
STEP_STATUS_ERRORED = "errored"

SCENARIO_STATUS_OK = "ok"
SCENARIO_STATUS_ERR = "err"
SCENARIO_STATUS_SKIPPED = "skipped"

FAULT_STEP_UNMATCHED = "step_unmatched"
FAULT_AMBIGUOUS_STEP = "ambiguous_step"
FAULT_ASSERTION_FAILED = "assertion_failed"
FAULT_STEP_ERRORED = "step_errored"
FAULT_BAD_FEATURE_SYNTAX = "bad_feature_syntax"

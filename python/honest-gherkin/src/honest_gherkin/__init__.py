"""honest-gherkin — Gherkin-subset parser + runner in honest-code style.

M1 scope: Feature / Scenario / Given / When / Then / And / But. Tags.
Feature description. Line comments. Parameter binding via named regex
captures with optional type coercion (`{name}` → str, `{name:int}` → int,
`{name:float}` → float).

Explicitly NOT in M1:
    - Scenario Outline + Examples tables
    - Backgrounds per feature
    - Doc strings (triple-quoted step payloads)
    - Data tables on steps
    - Rules (Gherkin 6+)
    - i18n / localised keywords

Those are tracked as follow-ups and will land once the first 5 framework
modules have their feature suites running.
"""
from honest_gherkin.parser import parse_feature
from honest_gherkin.registry import (
    compile_pattern,
    empty_registry,
    match_step,
    register_step,
)
from honest_gherkin.runner import fold_feature_report, run_feature_file, run_scenario
from honest_gherkin.types import (
    Feature,
    FeatureReport,
    Scenario,
    ScenarioReport,
    Step,
    StepFault,
    StepMatch,
    StepPattern,
    StepRegistry,
    StepResult,
)

__all__ = [
    "Feature",
    "FeatureReport",
    "Scenario",
    "ScenarioReport",
    "Step",
    "StepFault",
    "StepMatch",
    "StepPattern",
    "StepRegistry",
    "StepResult",
    "compile_pattern",
    "empty_registry",
    "fold_feature_report",
    "match_step",
    "parse_feature",
    "register_step",
    "run_feature_file",
    "run_scenario",
]

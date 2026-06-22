"""honest-gherkin - the BDD execution engine.

Built unit by unit: the parse contract (section 2 IR, section 3 parse_feature), pattern
compilation (section 4), and the step registry plus matching (section 5). The scenario runner and
the I/O boundary follow.
"""

from honest_gherkin.compile import PLACEHOLDER_TYPES, compile_pattern
from honest_gherkin.ir import (
    FAULT_CODES,
    SCENARIO_STATUSES,
    STEP_KINDS,
    STEP_STATUSES,
    CompiledPattern,
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
    step_fault,
)
from honest_gherkin.parse import parse_feature
from honest_gherkin.registry import empty_registry, match_step, register_step
from honest_gherkin.run import fold_feature_report, run_scenario, run_step

__all__ = [
    "parse_feature",
    "compile_pattern",
    "PLACEHOLDER_TYPES",
    "empty_registry",
    "register_step",
    "match_step",
    "run_step",
    "run_scenario",
    "fold_feature_report",
    "step_fault",
    "STEP_KINDS",
    "STEP_STATUSES",
    "SCENARIO_STATUSES",
    "FAULT_CODES",
    "Step",
    "Scenario",
    "Feature",
    "CompiledPattern",
    "StepPattern",
    "StepRegistry",
    "StepMatch",
    "StepResult",
    "ScenarioReport",
    "FeatureReport",
    "StepFault",
]

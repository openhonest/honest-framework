"""honest-gherkin - the BDD execution engine.

Built unit by unit: the parse contract (section 2 IR, section 3 parse_feature), pattern
compilation (section 4), and the step registry plus matching (section 5). The scenario runner and
the I/O boundary follow.
"""

from honest_gherkin.compile import PLACEHOLDER_TYPES, compile_pattern
from honest_gherkin.ir import (
    FAULT_CODES,
    STEP_KINDS,
    CompiledPattern,
    Feature,
    Scenario,
    Step,
    StepFault,
    StepMatch,
    StepPattern,
    StepRegistry,
    step_fault,
)
from honest_gherkin.parse import parse_feature
from honest_gherkin.registry import empty_registry, match_step, register_step

__all__ = [
    "parse_feature",
    "compile_pattern",
    "PLACEHOLDER_TYPES",
    "empty_registry",
    "register_step",
    "match_step",
    "step_fault",
    "STEP_KINDS",
    "FAULT_CODES",
    "Step",
    "Scenario",
    "Feature",
    "CompiledPattern",
    "StepPattern",
    "StepRegistry",
    "StepMatch",
    "StepFault",
]

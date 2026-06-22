"""honest-gherkin - the BDD execution engine.

Unit 1 (this release): the parse contract (section 2 IR, section 3 parse_feature). Pattern
compilation, the step registry, and the scenario runner follow.
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
    step_fault,
)
from honest_gherkin.parse import parse_feature

__all__ = [
    "parse_feature",
    "compile_pattern",
    "PLACEHOLDER_TYPES",
    "step_fault",
    "STEP_KINDS",
    "FAULT_CODES",
    "Step",
    "Scenario",
    "Feature",
    "CompiledPattern",
    "StepFault",
]

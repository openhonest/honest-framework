"""honest-check — static linter for Python source against honest-code principles.

Rules implemented in M1:
    HC-P001: No if/elif/else dispatch on type/category discriminant.
    HC-P003: No `class` declarations (except TypedDict, Protocol, Exception).
    HC-P014: No catch-all / wildcard recognizers.
    HC-R003: pure-role fns must not perform I/O side effects.

The checker is AST-driven — we walk Python source directly rather than
requiring instrumentation. Reports list diagnostics as data; honest-check
itself raises no exceptions against user code.
"""
from honest_check.diagnostics import Diagnostic, CheckReport, aggregate_diagnostics
from honest_check.rules import (
    check_hc_p001_if_elif_else_dispatch,
    check_hc_p003_class_declaration,
    check_hc_p014_catchall,
    check_source,
)

__all__ = [
    "CheckReport",
    "Diagnostic",
    "aggregate_diagnostics",
    "check_hc_p001_if_elif_else_dispatch",
    "check_hc_p003_class_declaration",
    "check_hc_p014_catchall",
    "check_source",
]

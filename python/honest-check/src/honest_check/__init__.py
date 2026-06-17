"""honest-check — static linter for Honest Code, founded on tree-sitter.

honest-check is the pre-auto-generation gate (spec §1): code that passes is
guaranteed a complete auto-generated test suite. It parses with tree-sitter
(one grammar stack, portable across language spokes), resolves aliases, walks
the tree, and reports violations as data. It never executes application code.

Rules re-founded on tree-sitter so far:
    HC-P003: class declaration (bare class or non-approved base).
    HC-P001: if/elif/else dispatch chain (3+ equality tests on one variable).
    HC-P014: catch-all recognizer (accepts all inputs).
    HC-SYN:  source syntax error.
Construction-time and the remaining static rules land in subsequent units.
"""
from honest_check.diagnostics import (
    CheckReport,
    Diagnostic,
    aggregate_diagnostics,
    diagnostic,
)
from honest_check.parse import parse
from honest_check.rules import (
    check_hc_p001,
    check_hc_p003,
    check_hc_p014,
    check_source,
)

__all__ = [
    "CheckReport",
    "Diagnostic",
    "aggregate_diagnostics",
    "diagnostic",
    "parse",
    "check_hc_p001",
    "check_hc_p003",
    "check_hc_p014",
    "check_source",
]

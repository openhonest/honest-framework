"""honest-check — static linter for Honest Code, founded on tree-sitter.

honest-check is the pre-auto-generation gate (spec §1): code that passes is
guaranteed a complete auto-generated test suite. It parses with tree-sitter
(one grammar stack, portable across language spokes), resolves aliases, walks
the tree, and reports violations as data. It never executes application code.

Rules on tree-sitter so far:
    Principle:     HC-P003 (class), HC-P001 (if/elif dispatch).
    Construction:  HC003 (recognizer overlap), HC006 (composed unknown base),
                   HC007 (empty chain), HC011 (catch-all recognizer).
    HC-SYN:        source syntax error.
Remaining construction (HC-SM01/02/05) and the static rules land in subsequent
units. (Catch-all is HC011 per spec §8; HC-P014 is recognizer-reuse, a later
Full-tier rule.)
"""
from honest_check.construction_rules import (
    check_hc003,
    check_hc006,
    check_hc007,
    check_hc011,
)
from honest_check.diagnostics import (
    CheckReport,
    Diagnostic,
    aggregate_diagnostics,
    diagnostic,
)
from honest_check.parse import parse
from honest_check.rules import check_hc_p001, check_hc_p003, check_source

__all__ = [
    "CheckReport",
    "Diagnostic",
    "aggregate_diagnostics",
    "diagnostic",
    "parse",
    "check_hc_p001",
    "check_hc_p003",
    "check_hc003",
    "check_hc006",
    "check_hc007",
    "check_hc011",
    "check_source",
]

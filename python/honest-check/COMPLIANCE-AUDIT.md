# honest-check self-compliance audit

honest-check must itself pass every Honest Code rule — including the rules it does
not yet *automate*. Until all 35 Full-set rules are implemented, this file records
the **manual** audit of honest-check's own source against each not-yet-automated
rule. Re-run the audit whenever the source changes; promote a row to "automated"
when its rule lands in `_ALL_CHECKS`.

Automated rules (31) enforce themselves on every self-lint (`python -m
honest_check.cli src/honest_check`, exit 0). The rows below are the manual gap
(4 rules remaining: 1 intent, 1 exemption, 2 N/A-and-blocked).

| Rule | Manual audit result |
|---|---|
| ~~HC004 / HC005 / HC-P014~~ | **Now AUTOMATED** (binding tier). No longer a manual row. |
| ~~HC010 / HC-A001 / HC-A002~~ | **Now AUTOMATED** (emission + auth tier). No longer a manual row. |
| **HC-OR003** duplication between orchestrators | **Buildable; not yet automated.** No `@orchestrator` functions (formally N/A). Manual enforcement = the no-duplication intent (see the `function_name` dedup, `git f7c02e9`). Re-audit on new helpers. |
| **HC-SM06** transition writes undeclared field | **N/A + blocked.** No `state_machine()` declarations; rule also needs the honest-state model. |
| **HC-P015** cross-chain TOCTOU guard | **N/A + blocked.** No `guarded_mutation()` / guard expressions; rule also needs honest-persist's guard DSL. |
| **HC-OR003** duplication between orchestrators | **Audited — one finding, fixed.** No `@orchestrator` functions (rule formally N/A), but enforcing the underlying no-duplication intent: `function_name` was duplicated as `rules._function_name`. Removed; `rules.py` now imports `declgraph.function_name`. Re-audit on new helpers. |
| **HC-P010** non-serializable return value | **Audited — standing exemption documented (below).** |

## HC-P010 standing exemption: the AST-traversal layer

honest-check is an AST linter, so its parsing and declaration-graph helpers
necessarily return tree-sitter `Node` / `Tree` objects (`parse`, `first_error_node`,
`link_decorator_call`, `_dictionary_arg`, `constructor_calls`, and others). These
are non-serializable class instances, which the *literal* HC-P010 would flag.

This is the same shape of tension as dict-dispatch-vs-HC008 and cli-I/O-vs-HC-P004:
the rule's intent is to stop *business* logic from returning opaque objects instead
of TypedDicts, not to forbid an AST tool from trafficking in AST nodes. The nodes
**are** the data under analysis.

Resolution (to encode when HC-P010 is implemented): HC-P010 exempts functions whose
return is a parser `Node`/`Tree` (the AST-traversal layer). It still flags a pure
function that returns a *custom* class instance where a TypedDict/dict belongs.
Until then, this is the manual ruling: AST-node returns here are compliant by
exemption; any new helper returning a non-node custom class instance is a violation.

## Re-audit checklist

When `src/honest_check/` changes, re-check the two non-N/A rows: any new duplicated
helper (HC-OR003 intent) and any new function returning a non-node custom class
(HC-P010). The N/A rows stay N/A as long as honest-check declares no honest-type
constructs on its own functions.

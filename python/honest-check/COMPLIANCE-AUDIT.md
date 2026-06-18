# honest-check self-compliance audit

honest-check must itself pass every Honest Code rule — including the rules it does
not yet *automate*. Until all 35 Full-set rules are implemented, this file records
the **manual** audit of honest-check's own source against each not-yet-automated
rule. Re-run the audit whenever the source changes; promote a row to "automated"
when its rule lands in `_ALL_CHECKS`.

Automated rules (33) enforce themselves on every self-lint (`python -m
honest_check.cli src/honest_check`, exit 0). The rows below are the manual gap
(2 rules: 1 exemption, 1 N/A-and-blocked).

| Rule | Manual audit result |
|---|---|
| ~~HC004 / HC005 / HC-P014~~ | **Now AUTOMATED** (binding tier). |
| ~~HC010 / HC-A001 / HC-A002~~ | **Now AUTOMATED** (emission + auth tier). |
| ~~HC-OR003~~ | **Now AUTOMATED** (roles tier). Fires only on `@orchestrator` bodies; the `function_name` dedup intent still re-audited manually on new helpers. |
| ~~HC-P015~~ | **Now AUTOMATED.** Built against the honest-persist guard DSL (§7.5). Traces `slot()` provenance in a guard vs prior `persist.read`/`execute`. (Cross-link taint — read in link N, guard in link M of the same chain — is a documented extension; the within-link case is covered.) |
| **HC-SM06** transition writes undeclared field | **N/A + blocked.** No `state_machine()` declarations; rule also needs the honest-state model (state_fields + transition functions). |
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

# Adding a rule

A new rule touches four places that gates cross-check, not just the one where you write the check. Miss one and a gate stops you, so register all four.

1. **The check and its registry.** Write `check_hc_pNNN(root, source, path)` in the right rule-family module (`honest_code_rules.py` for the structural principles), and add it to `_ALL_CHECKS` in `rules.py`, with its import. A check returns diagnostics; it reads the parse tree and nothing else.
2. **The catalogue.** Add the rule's record to `specs/rules.json`, with `emitted_by_honest_check` set true. Without it, `rules-check.py` reports the rule as undeclared and fails.
3. **The adoption level.** Place the rule in a level in `adoption.py`. An unplaced rule reports as info and blocks nothing, which `rules-check.py` also flags.
4. **The level counts.** The laws in `conformance/laws_hc.py` pin the rule totals and each level's membership by hand. Update the "N of N rules enforced" header counts, the JSON `enforced_rules` count, and the `expected_membership` set for the level you placed the rule in.

A rule also needs one gherkin scenario, named for the check, in `specs/features/honest-check.feature`. The feature gate holds one scenario per function, so a new check with no scenario fails the bijection.

## Build order

Spec first, then the feature scenario, then the test cases, then the code, then the three registry files above. The spec is `specs/02-code-quality/honest-check-architecture.md`: add a row to the rule table, a row to the rationale table, and a detail section. The test cases are a conformance entry in `conformance/suite.json` and generative cases in `conformance/laws_hc_rules.py`, each with the input that must fire the rule and the input that must not.

## Coverage

honest-check holds itself to full line and branch coverage. A new check must have no dead branch. A guard that cannot be false, such as a check for an argument node that a call always carries, is dead code the coverage gate will catch, and it is also a defensive interior check the principles forbid. Leave it out.

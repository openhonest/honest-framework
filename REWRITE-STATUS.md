# Rewrite status register

We are rebuilding the framework one module at a time, spec → `.hd` → features → tests → code. Strengthening the toolchain (honest-check especially) is expected to break downstream and already-"completed" modules; those get back-fixed when we reach them. This register is the single source of truth for what is actually green against the current toolchain, not what was green at some earlier point.

A module is **complete** only when all of these pass against the current toolchain: base-mode `honest-check` (0 errors), the `hd-status` crossing (CLEAN), `feature-gate` (one scenario per function), its own conformance (laws + `suite.json` value cases), and — for the toolchain modules — being runnable against every other completed module (bootstrapping).

Last verified: 2026-11-11.

"Rewritten" is judged from the git rebuild commits, not from current honest-check error counts. A rewritten module can later be broken by toolchain strengthening — that is a back-fix, not a "not rewritten." The honest-check column is the current base-mode error count (a back-fix signal), not a completion verdict.

| Module | Rewritten | honest-check now | Status |
|---|---|---|---|
| honest-type | ✅ `3ced304` rebuild to spec | 7 | rewritten; broken by later checker strengthening → back-fix when prioritized |
| honest-check | ✅ `4604a87`/`b9fbbd1` (11-01) | 0 | rewritten; passes own checker; `.hd` crossing still has ~69 faults |
| honest-test | ✅ `24677c6` (11-04) | 0 | rewritten; back-fix done — 19 HC-P019/P020 cleared, TypedDict `_is_machine` crash fixed (`isinstance(value, dict)`); conformance 75/75 + 90/90, runs on gherkin. 37 HC-P005 warnings left (AST isinstance, non-blocking); two HC-P020 guard-miss branches have no probe |
| honest-parse | ✅ built (tree-sitter); if-free + fault-return back-fix (11-15) | 0 | COMPLETE this pass — all gates green (verified 2026-11-15): honest-check 0/0, hd-status crossing CLEAN, feature bijection 7/7, conformance 33 + 11 laws. The 5 `if`s are gone (two-row `_pick`, `next`/`filter`). `parse` now returns an `unknown_grammar` fault as data on a table miss, the way every table handles a miss; the `UnknownGrammar` exception was deleted as a defensive guard against a case the closed language table never produces, which also removed the last crossing fault (an exported exception class the `.hd` could not name). |
| honest-features | ✅ `7dd4984` (11-11) | 0 | complete this pass (all gates green) |
| honest-gherkin | ✅ `33c46b1` (11-11) | 0 | complete this pass (all gates green) |
| honest-design | ❌ not this pass | 25 | NOT rewritten; grammar spec-rewritten 07-17, code predates the new standard |
| honest-errors | ✅ re-rebuilt this pass (cadence model), `6447fe2`/`e2fab01` (11-15) | 0 (pure core) | PARTIAL — pure core complete, persistence parked. Replaced the earlier door/`FailurePolicy` rebuild with the error-cadence design: the caller declares a `Cadence` (or names a preset), the module normalizes a failure to one `ExceptionReport` and plans `DisplayAction`s against a `CadenceState` it owns; faults return bare `X \| Fault` recognized by the chain executor (no ok/err envelope). The 15 pure functions, the 10 bounded vocabularies, the `NOTHING` absence sentinel and the IR are built if-free: base honest-check 0/0, conformance 24 suite cases + 8 laws green (verified 2026-11-15). NOT complete: four functions — `load_cadence_state`, `store_cadence_state`, `handle_failure`, `capture` — are PARKED until persistence is wired (bead), so the hd-status crossing reports them declared-undefined and the coverage/feature gates are not yet green. observe/alerts consume the returned `CaptureResult`. |
| honest-state | ❌ not this pass | 0 | NOT rewritten (07-19); 0 errors incidentally |
| honest-estimate | ❌ not this pass | 9 | NOT rewritten (07-27) |
| honest-auth | ❌ not this pass | 6 | NOT rewritten (08-25) |
| honest-rca | ⛔ not complete | 11 | NOT complete. The path law (commit 16802b5) flags 11 arrivals: EvidenceItem across seven functions, Symptom on trace and attest, Method on causal_graph and attest. Its pure functions take records that nothing in the module returns, and it declares no door or orchestrator to hand them in, so a Symptom (something a person describes and hands in) arrives with no declared path. I wrongly cleared it on the type-ownership test, which was not the governing law. It needs a door or a fold, same question as errors. The 0-errors column was base-mode honest-check; the 11 are the hd-status path law. |
| honest-page | ❌ not this pass | 3 | NOT rewritten (07-22) |
| honest-alerts | ❌ not this pass | 23 | NOT rewritten (07-xx) |
| honest-observe | ❌ not this pass | 76 | NOT rewritten (07-xx) |
| honest-persist | ⏭️ replace | 257 | slated for wholesale replacement; do not back-fix |

Rewrite order so far (newest last): honest-type → honest-check → honest-test → (honest-parse) → honest-features → honest-gherkin → honest-errors → honest-rca. Update this register row-by-row as each module is finished; a module is complete only when ALL gates pass, never from one gate alone.

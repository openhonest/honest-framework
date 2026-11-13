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
| honest-parse | ✅ built (tree-sitter) | 0 | rewritten; full-gate completion unverified |
| honest-features | ✅ `7dd4984` (11-11) | 0 | complete this pass (all gates green) |
| honest-gherkin | ✅ `33c46b1` (11-11) | 0 | complete this pass (all gates green) |
| honest-design | ❌ not this pass | 25 | NOT rewritten; grammar spec-rewritten 07-17, code predates the new standard |
| honest-errors | ✅ rebuilt this pass (door model); commit pending | 0 | complete at self-check (verified 2026-11-13). The fold decision was reversed to DOOR: it now owns a `capture` boundary_in and a `handle_failure` orchestrator, declares the foreign payloads as `foreign "browser"`/`foreign "cpython"`, and returns one `FailurePolicy`; observe and alerts consume that result instead of owning the catch. All gates green: base honest-check 0, hd-status CLEAN, feature-gate 11/11, conformance 39 cases + 19 laws, 100% line+branch coverage. A latent bug was fixed in the rebuild: a log-only environment no longer renders an email body on a throttle-send. Working tree verified green; not yet committed. Downstream observe/alerts still call the old return conventions and will break until rebuilt (expected). |
| honest-state | ❌ not this pass | 0 | NOT rewritten (07-19); 0 errors incidentally |
| honest-estimate | ❌ not this pass | 9 | NOT rewritten (07-27) |
| honest-auth | ❌ not this pass | 6 | NOT rewritten (08-25) |
| honest-rca | ⛔ not complete | 11 | NOT complete. The path law (commit 16802b5) flags 11 arrivals: EvidenceItem across seven functions, Symptom on trace and attest, Method on causal_graph and attest. Its pure functions take records that nothing in the module returns, and it declares no door or orchestrator to hand them in, so a Symptom (something a person describes and hands in) arrives with no declared path. I wrongly cleared it on the type-ownership test, which was not the governing law. It needs a door or a fold, same question as errors. The 0-errors column was base-mode honest-check; the 11 are the hd-status path law. |
| honest-page | ❌ not this pass | 3 | NOT rewritten (07-22) |
| honest-alerts | ❌ not this pass | 23 | NOT rewritten (07-xx) |
| honest-observe | ❌ not this pass | 76 | NOT rewritten (07-xx) |
| honest-persist | ⏭️ replace | 257 | slated for wholesale replacement; do not back-fix |

Rewrite order so far (newest last): honest-type → honest-check → honest-test → (honest-parse) → honest-features → honest-gherkin → honest-errors → honest-rca. Update this register row-by-row as each module is finished; a module is complete only when ALL gates pass, never from one gate alone.

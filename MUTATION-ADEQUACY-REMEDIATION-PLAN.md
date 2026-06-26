# Remediation Plan — Mutation Adequacy + the Independent-Oracle Rule

**Status:** in progress — Phase D complete (HT-7 fixed `a8bdc69`; three borderlines settled by inspection `1e6bab8`). Phase A: the four originally-missing §9.6 operators are now implemented red-first (`bcd96af`) — float-literal shift, add-`not`, dict-key swap, sole-statement/branch-arm removal — with two narrow sub-gaps remaining (branch-arm removal does not cover try/match/for-else arms; dict-key swap is string-keys-only). Phase B: parse and errors re-verified adequate under the complete operator set; honest-type partial (reserved done, 99 survivors open under the old set, not yet re-run under the new); check/gherkin/observe/persist/test untouched. Phase C not started.
**Spec basis:** commit `34b736a` — *"spec: define mutation adequacy and the independent-oracle rule for the verification model"* (Tier 1 Verification Model + Bootstrapping; honest-test §9.6; GLOSSARY).
**Trigger:** the 2026-06-26 honesty audit caught a test that passed every gate while proving nothing (honest-test §4.5: its expected answer came from the same code it was checking, so it could not fail). 100% coverage could not see it — the line ran. The spec now closes that gap; this plan brings the implementation into line with it.

---

## What the spec now requires

**R1 — Independent oracle (Tier 1).** A test's expected answer must come from somewhere *other* than the code under test: a hand-written value, a different module, or the shared portable contract (`suite.json`). A test that takes its expected answer from the function it checks passes whatever that function does — it proves nothing.

**R2 — Mutation adequacy (Tier 1 + honest-test §9.6).** Every mechanical change to the source, drawn from a fixed finite list, applied with tree-sitter to every site one at a time, must make at least one conformance case fail. A change that cannot alter the result (an equivalent mutant) is set aside *by name with its reason*, never left to pass silently. `caught + set_aside == total`, enforced as a gate alongside coverage. The commit step now requires: **suites pass AND coverage total AND no mutation passes every test.**

**The §9.6 operator list (fixed, finite):**

| Operator | Examples |
|---|---|
| Comparison swap | `<` ↔ `<=`, `>` ↔ `>=`, `==` ↔ `!=` |
| Number shifted by one | `n` → `n + 1`, `n` → `n - 1` |
| Condition flipped | `and` ↔ `or`, remove a `not`, `x` → `not x` |
| Constant replaced | `0` → `1`, non-empty literal → empty, `True` ↔ `False` |
| Result swapped | `ok(...)` ↔ `err(...)` |
| Line removed | delete one statement or one branch arm |
| Membership / key changed | `in` ↔ `not in`, a dict key → a sibling key |

---

## Key realization that shapes the plan

**Mutation adequacy (R2) subsumes most of R1.** A self-referential test cannot kill a mutant — it asserts against the *mutated* output, so the mutant survives. So once the mutation gate exists, every §4.5-style tautology surfaces automatically as a surviving mutant. The **mutation engine is the master mechanism**; R1 is the stated principle plus a cheap early audit. The plan front-loads the engine and runs the R1 audit alongside.

A hopeful note for effort: honest code's **exact-output value cases are unusually strong mutant-killers** — a value case that pins the precise result kills comparison, constant, and result-swap mutants outright. Survivors should cluster in probe-only branches and genuinely-equivalent mutants, so the count may be lower than a typical codebase.

---

## Phases

### Phase A — Build the mutation engine (honest-test §9.6)

The core new capability. Built red-first and incrementally, under the framework's own discipline (100% coverage, value cases, one gherkin per function). The engine must itself become mutation-adequate once it runs (resolve the chicken-and-egg by building under coverage first, then self-mutating in Phase B).

- [~] **A1 — Mutation operators (7)** — the four originally-missing §9.6 sub-cases are now implemented red-first (`bcd96af`): (1) number shift covers float literals and hex/octal/binary integers via `int(text, 0)`, complex skipped — this also fixed a latent crash on non-decimal literals; (2) condition flip negates a condition (`c`→`not (c)`) at if/elif/while/ternary/assert/comprehension-filter/match-guard — the `x`→`not x` case; (3) dict-key→sibling-key swap (string keys); (4) line removal replaces a block's sole statement with `pass`, and branch-arm removal drops an `if`'s elif/else clause. Plus the docstring/annotation skips (`81cf45c`, `19453f5`). **Two narrow sub-gaps remain, verified by probe:** branch-arm removal covers `if` arms only — NOT `try` (except/else/finally), `match` (case), or `for/while…else` arms; and dict-key swap covers string keys only — NOT integer/other-literal keys. The framework forbids `try/except` in business logic (HC-P002) and uses dict-dispatch not `match`, so these forms are largely absent from honest modules (which is why parse/errors stay adequate under the full set), but the engine's coverage of §9.6 is not yet total.
- [!] **Adequacy verdicts must be re-checked under the completed operator set.** Verified so far: **honest-parse** (35 mutants, 0 undeclared) and **honest-errors** (316 mutants, 0 undeclared) remain adequate. honest-type and every untouched module have NOT been re-run under the new operators.
- [x] **A2 — Site enumerator** (`3f17992`). `enumerate_mutants(source)` parses once, runs every operator, returns the full `{operator,label,source}` list.
- [x] **A3 — Mutant runner** (`1a449df`). `run_mutants(mutants, run_suite)` returns survivors; `run_suite` injected, so the decision is pure/testable.
- [x] **A4 — Set-aside registry** (`1a449df`). `mutation_adequacy(mutants, survivors, set_aside)` → `caught + set_aside == total`; `conformance/mutants_setaside.json` per module ({label: reason}).
- [x] **A5 — Gate scripts** (`81cf45c`). `mutate.py` driver (the I/O harness) + `mutate-all.sh` + `mutate-affected.sh`.

**Effort:** large — a genuine new tool, but pure-function-heavy and shaped like honest-test's existing generators.

### Phase B — Dogfood across all modules (the bulk of the remediation)

Run the engine per module; triage every surviving mutant: **add a conformance case that catches it**, or **declare it equivalent-with-reason**. This is where the real work and the real payoff are, and where any other §4.5-clone tautologies surface (as survivors).

- [x] B-parse (`81cf45c`) — 31 mutants, 30 caught, 1 set aside (trailing `return None`), 0 undeclared. Ran in ~3s.
- [x] B-errors — 252 mutants, 250 caught, 2 set aside (`total=False` TypedDict flags), 0 undeclared. First pass surfaced 93 undeclared survivors in clear classes: unpinned boundaries (`<`/`<=`, the hour constant, the context limit), suppression-path state never asserted, the email body never pinned verbatim, fault message/category never pinned, the four closed vocabularies never pinned, and the untested public surface (`__all__`/re-exports). All but the two equivalents were closed by strengthening `laws_he.py` (plus an engine refinement: skip bare type annotations as universally equivalent, `19453f5`).
- [ ] B-type, B-check, B-gherkin, B-observe, B-persist, B-test — one module at a time; record survivor counts; clear to `caught + set_aside == total`.

**Effort:** large, open-ended — scope per module is approved as survivor counts come in.

### Phase C — Wire the gate into the commit step

Per the bootstrapping update: nothing lands unless suites pass, coverage is total, **and** no mutation passes every test.

- [ ] Add the mutation gate to `.githooks/pre-commit` alongside `coverage-all.sh` (per-module as each goes adequate, or globally once Phase B clears all).

**Effort:** small. Depends on Phase B clearing survivors first (can't enforce a gate that fails).

### Phase D — Independent-oracle audit (R1), cheap and early

A fast fan-out over all conformance probes (`laws_*.py` × 8) hunting for self-referential assertions like the §4.5 one — caught before the engine exists, since they're the urgent honesty class.

- [x] Audit probes (3 parallel agents, all 9 `laws_*.py`); fixed the one genuine self-referential law — HT-7 totality (`a8bdc69`), now driven by a hand-written `declared` oracle, proven load-bearing.
- [x] **The three deferred borderlines are now settled by inspection, not punted to the engine:**
  - `reservation_layer` (honest-type) — **was genuinely self-referential**: it drew its words from the module's own `_LAYER*` frozensets, so an emptied word still mapped correctly (the empty string sorts first and is itself a member) and the law passed. Fixed with a hand-written literal oracle pinning all three layers plus every word→layer mapping; the mutation engine confirms it load-bearing (92 caught). Committed `11bddae`.
  - `checked_select`-vs-`select` (honest-persist `_probe_checked`:558) — **benign**: the comparison `checked_select(...)["ok"] == select(...)` leans on `select()` being independently pinned by suite.json hand-written `expect_sql`/`expect_params` (`q-select-star`/`-cols-where`/`-full`), and `checked_select` has its own `cq-select-ok`. Not circular.
  - `manifest`-embeds-`schema` (honest-observe `_probe_event_log`:348) — **benign**: the embedded `table` is pinned against hand-written `expected_columns`/`expected_indexes`/nullability literals in the same probe (laws_ho.py 313–345); the embed check leans on that independent grounding.
- [x] honest-check heuristic rule for self-reference — **deferred** (R2 subsumes it structurally, once the engine is complete — see Phase A's missing operators).

**Effort:** small. **Status: complete.**

---

## Sequencing

```
D (R1 probe audit)  ── cheap, run first/parallel; catches obvious tautologies now
A (build engine)    ── prerequisite for B, C; red-first, operator by operator
   └─ B (dogfood: triage survivors per module)  ── the bulk
        └─ C (wire the gate)  ── enforce once B clears each module
```

**Recommended start order:** D → A → B → C.

---

## Notes & constraints

- **Increment 2 (HC002 template analysis) stays parked** until this remediation is done. State at pause: spec complete (route map + derivation, commits `9135036`); increment 1 (route-map reader) landed (`d3ce61a`); the two grammars are confirmed (`tree-sitter-html` 0.23.2, `tree-sitter-javascript` 0.25.0) and ready to wire into honest-parse for increment 2.
- **The engine eats its own dogfood.** honest-test's own suite must catch its own mutants; build the engine under coverage first, then mutation-check it in Phase B.
- **Self-reference is the smell.** The unifying lesson (in memory `specs-name-patterns-not-frameworks` neighbourhood): green proves internal consistency, not grounding. Coverage shows the line ran; mutation shows it is constrained; an independent oracle shows the assertion is true rather than self-certified.
- **Already remediated (the three audit defects this plan's spec change followed from):** honest-test §4.5 tautology/overclaim (`a144dd3`), honest-persist req 17 construction-time CHECK fault (`7145ca7`), honest-persist req 15 FK re-enable lifecycle (`8d03baa`).

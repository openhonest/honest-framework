# honest-gherkin: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** June 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-gherkin is the **BDD execution engine** of the Honest Framework. It parses Gherkin-subset `.feature` files, matches their steps against a registry of handlers, runs each scenario, and reports the outcome as data. It is the engine that honest-test §8 ("BDD Tests") runs under the hood.

honest-test §8 originally deferred this engine to each spoke: "the BDD framework used under the hood is an implementation detail per spoke; honest-py will wrap an existing Python BDD framework." That deferral is withdrawn. Wrapping an existing BDD framework (behave, pytest-bdd, cucumber-js) imports three things the Honest Framework forbids everywhere else:

- a **mutable shared `context` object** that step functions assign onto,
- **global decorator registration** (`@given`, `@when`) whose effect is an import-time side effect, and
- **exceptions for control flow** to signal unmatched, ambiguous, or failed steps.

A test layer built on those three cannot prove their absence in the code under test. Worse, two spokes wrapping two different frameworks diverge in exactly the property that matters — the execution model — while both technically "support Gherkin." honest-gherkin specifies one execution model that is itself honest-code-conformant, so that divergence class is structurally impossible.

### 1.1 The abstract requirement

> *A BDD scenario is a pure fold of its steps over an immutable context. Step matching, parameter binding, and failure are data, not exceptions. The step registry is a value threaded through the fold, not global state.*

Every property in this spec follows from that one sentence. A step handler receives the current context and its bound captures and returns a new context; it never mutates a shared object. A scenario's result is the fold of its step results. Matching returns a Result; only genuinely external failure (a handler's own assertion or thrown exception) crosses the boundary as an exception, and even that is caught and classified into a bounded fault vocabulary at the engine edge.

### 1.2 Which bug categories this eliminates (poka-yoke)

| Decision | Bug category made impossible |
|---|---|
| Fold over immutable context | State leaking between steps or scenarios; order-dependent flakiness from a shared mutable `context` |
| Registry as a threaded value | Import-order and import-side-effect bugs from global `@given` registration; a step silently registered (or not) by an import |
| Matching returns a Result | Unmatched/ambiguous steps swallowed or surfaced as raw stack traces instead of categorized failures |
| Bounded fault vocabulary | Error surface that cannot be enumerated, and therefore cannot be exhaustively tested by honest-test or asserted on by honest-check |
| Reports as TypedDict data | A pass/fail summary that can only be printed, never folded, asserted, or consumed by another tool |

### 1.3 Relationship to honest-test and honest-check

| Tool | Role |
|---|---|
| **honest-test** | Generates step scaffolding from `@link` declarations (honest-test §8.2) and ships the standard protocol-level assertion steps (honest-test §8.4). The developer authors only `.feature` files; honest-gherkin runs them. |
| **honest-check** | Consumes the bounded vocabularies (`STEP_KINDS`, status sets, `FAULT_CODES`) as discriminant sets. Enforces **universal gherkin coverage**: every roled function carries exactly one gherkin (§9; honest-test §8.3, diagnostic HC-P009). |

### 1.4 What honest-gherkin covers

- The source-level IR: `Feature`, `Scenario`, `Step` (all TypedDicts).
- The runtime IR: `StepRegistry`, `StepPattern`, `StepMatch`.
- The result IR: `StepFault`, `StepResult`, `ScenarioReport`, `FeatureReport`.
- The bounded vocabularies: step kinds, step/scenario statuses, fault codes.
- The pure functions: `parse_feature`, `compile_pattern`, `register_step`, `match_step`, `run_scenario`, `fold_feature_report`.
- The single I/O boundary: `run_feature_file` and the CLI.
- The step-module contract: `register(registry) -> registry`.

### 1.5 What honest-gherkin does not cover (per-spoke freedom)

The execution model in §§3-7 is **normative across every language spoke**. The following are **per-spoke implementation choices** and are deliberately not standardized:

- The concrete regex dialect used inside patterns (a spoke may use its host language's regex engine).
- File discovery and CLI ergonomics beyond the `run` contract in §8.
- Report formatting / pretty-printing.
- The host language's mechanism for declaring a TypedDict-equivalent.

A spoke is conformant if it produces the same IR, the same fault classifications, and the same fold semantics. It is free in everything above.

### 1.6 Gherkin subset (M1 scope)

This version specifies: `Feature:` with a free-text description, `Scenario:`, the five step kinds (`Given`/`When`/`Then`/`And`/`But`), `@tag` lines attaching to the next scenario, `#` line comments, blank-line tolerance, and parameter binding via `{name}` / `{name:int}` / `{name:float}` placeholders.

Explicitly **out of scope for M1**, tracked as follow-ups: `Scenario Outline` + `Examples` tables, per-`Feature` `Background`, doc-strings (triple-quoted step payloads), data tables on steps, `Rule:` (Gherkin 6+), and i18n / localized keywords. The IR reserves `Feature.background_steps` for the `Background` follow-up; it is always `[]` in M1.

---

## 2. The Source-Level IR

All IR is TypedDict. No classes, no methods.

```
Step = {
    kind:        String,    # one of STEP_KINDS
    text:        String,    # step text with the keyword stripped
    source_line: Integer,
}

Scenario = {
    name:        String,
    steps:       list[Step],
    tags:        list[String],   # tags attached to this scenario
    source_line: Integer,
}

Feature = {
    name:             String,
    description:      String,        # free text between Feature: and the first Scenario
    scenarios:        list[Scenario],
    background_steps: list[Step],    # reserved; [] in M1
    source_path:      String,
}
```

### 2.1 Step kinds

```
STEP_KIND_GIVEN = "given"
STEP_KIND_WHEN  = "when"
STEP_KIND_THEN  = "then"
STEP_KIND_AND   = "and"
STEP_KIND_BUT   = "but"

STEP_KINDS = { given, when, then, and, but }   # frozenset
```

`And` and `But` carry their own literal kind on the `Step`. Their *resolved* kind (for grouping and for any kind-sensitive matching a spoke chooses to add) is the kind of the most recent `Given`/`When`/`Then`. The parser tracks the last resolved kind; `And`/`But` inherit it. The literal kind is preserved so a report renders the line as written.

---

## 3. The Parse Contract

`parse_feature(source: String, source_path: String) -> Result[Feature]`

Pure function. Source text in, `Result` out. No I/O.

```
Result[Feature] = { "ok": Feature } | { "err": StepFault }
```

**Normative change from the reference prototype.** Parsing must **return** a `StepFault` with code `bad_feature_syntax` on malformed input; it must not raise. A step declared outside any scenario, a scenario with no name, or any other structural violation produces `{ "err": StepFault(code="bad_feature_syntax", ...) }`. The `detail` field carries the line number and a human-readable message. Faults are data all the way to the edge — the only honest-code-conformant shape.

### 3.1 Parser construction

The parser is a fold over lines. Each line is classified into exactly one **line kind** by an ordered predicate table (first match wins); a handler table maps line kind → pure state-transition function. There is no `if/elif` ladder on keywords; classification and handling are both dict/table dispatch.

Line kinds: `blank`, `comment`, `tag`, `feature`, `scenario`, `step`, `description`. Classification order is significant (a `#` line is a comment even if it begins with the word "Feature"); the table encodes that order.

The parser state is an immutable dict folded forward: feature name, accumulated description lines, completed scenarios, pending tags (awaiting the next scenario), the current scenario under construction, the last resolved step kind, an in-feature-header flag, and an accumulated error list. Each handler returns a new state. At end of input the current scenario is flushed; if the error list is non-empty, the first error becomes the returned `bad_feature_syntax` fault.

---

## 4. Pattern Compilation and Binding

`compile_pattern(pattern: String) -> Result[CompiledPattern]`

A pattern is a literal string with optional placeholders. A placeholder is `{name}` (binds a string) or `{name:type}` (binds and coerces). The placeholder-type dispatch table is the single source of truth for supported types:

```
PLACEHOLDER_TYPES = {
    "str":   regex fragment for a non-empty run of non-quote chars,  coerce: identity
    "int":   regex fragment for an optionally-signed integer,        coerce: to-integer
    "float": regex fragment for an optionally-signed decimal,        coerce: to-float
}
```

A placeholder whose type is not in the table yields `{ "err": StepFault(code="bad_feature_syntax", ...) }` — again, returned, not raised. Compilation translates each placeholder into a named capture and records the coercion to apply at bind time. The compiled pattern is anchored at both ends (full-text match, not substring).

Adding a placeholder type is adding one row to `PLACEHOLDER_TYPES`. A spoke may extend the table; the three above are required of every spoke.

---

## 5. The Step Registry

The registry is a value, never global state.

```
StepPattern = {
    kind:    String,        # one of STEP_KINDS
    pattern: String,        # the {name}-style source pattern
    handler: StepHandler,   # context + captures -> new context
}

StepRegistry = { patterns: list[StepPattern] }

StepMatch = {
    pattern:  StepPattern,
    captures: dict[String, Any],   # bound + coerced
}
```

- `empty_registry() -> StepRegistry` returns `{ patterns: [] }`.
- `register_step(registry, kind, pattern, handler) -> StepRegistry` returns a **new** registry with one pattern appended. It never mutates its argument.

A `StepHandler` takes the immutable context and the bound captures (as named arguments) and returns a new context. Purity of handlers is a convention the framework's own linter enforces structurally elsewhere (no mutation, no `self`); the engine does not re-check it at runtime.

### 5.1 Matching

`match_step(step: Step, registry: StepRegistry) -> Result[StepMatch]`

**Normative change from the reference prototype.** Matching must **return** a Result, not raise. It compiles each registered pattern, attempts a full-text match against the step text, and collects matches:

- zero matches → `{ "err": StepFault(code="step_unmatched", ...) }`
- more than one match → `{ "err": StepFault(code="ambiguous_step", ...) }` (the detail lists the competing patterns)
- exactly one match → `{ "ok": StepMatch }` with captures coerced per the pattern's recorded coercions.

This is the single most important honest-code correction over a wrapped framework: unmatched and ambiguous steps are categorized data, enumerable by honest-test, not stack traces.

---

## 6. The Execution Model

### 6.1 Running one step

Running a step is: match → (on ok) invoke the handler → classify the outcome. The only place an exception legitimately arises is inside the developer's own handler: an `AssertionError` from a `Then` step, or any other exception from handler code. The engine catches it at this single boundary and classifies it into the fault vocabulary via an exception-type dispatch table (§7.1). A handler that returns a falsey value is treated as returning the unchanged context.

A step's outcome is a `StepResult`:

```
StepResult = {
    step:   Step,
    status: String,           # one of STEP_STATUSES
    fault:  StepFault | null, # null iff status == ok
}
```

On any non-ok status the scenario stops; remaining steps are not run (and are not reported as results in M1).

### 6.2 Running one scenario

`run_scenario(scenario, background, registry) -> ScenarioReport`

Fold the steps — background steps first, then the scenario's own — over an **empty immutable context**. Each step produces a `StepResult` and, on success, a new context for the next step. Stop at the first non-ok step. The scenario status is `ok` iff every executed step is `ok`, else `err`.

```
ScenarioReport = {
    name:         String,
    status:       String,            # ok | err | skipped
    step_results: list[StepResult],
    duration_ms:  Integer,
}
```

`duration_ms` is wall-clock for the fold. It is the one impure observation inside `run_scenario` (a clock read); a spoke may treat it as 0 in a deterministic-test mode.

### 6.3 Folding the feature report

`fold_feature_report(feature, scenario_reports) -> FeatureReport`

Pure aggregation. `total_passed` counts `ok` scenarios; `total_failed` is the remainder.

```
FeatureReport = {
    feature_name: String,
    source_path:  String,
    scenarios:    list[ScenarioReport],
    total_passed: Integer,
    total_failed: Integer,
}
```

---

## 7. The Fault Vocabulary

Bounded and closed. honest-test enumerates it; honest-check treats it as a discriminant set.

```
FAULT_STEP_UNMATCHED     = "step_unmatched"
FAULT_AMBIGUOUS_STEP     = "ambiguous_step"
FAULT_ASSERTION_FAILED   = "assertion_failed"
FAULT_STEP_ERRORED       = "step_errored"
FAULT_BAD_FEATURE_SYNTAX = "bad_feature_syntax"

FAULT_CODES = { step_unmatched, ambiguous_step, assertion_failed,
                step_errored, bad_feature_syntax }   # frozenset
```

```
StepFault = {
    code:          String,   # one of FAULT_CODES
    scenario_name: String,
    step_text:     String,
    detail:        String,
}
```

### 7.1 Status vocabularies

```
STEP_STATUSES     = { ok, failed, unmatched, ambiguous, errored }
SCENARIO_STATUSES = { ok, err, skipped }
```

The exception-classification table maps each catchable failure to a `(step_status, fault_code)` pair:

| Caught at the handler boundary | step status | fault code |
|---|---|---|
| match returned `step_unmatched` | `unmatched` | `step_unmatched` |
| match returned `ambiguous_step` | `ambiguous` | `ambiguous_step` |
| handler raised an assertion failure | `failed` | `assertion_failed` |
| handler raised any other exception | `errored` | `step_errored` |

The table is ordered most-specific-first; the catch-all (any other exception) is last. This is the one place the engine touches exceptions, and it converts them to data immediately.

---

## 8. The I/O Boundary

Exactly one module performs I/O. Everything in §§2-7 is pure.

`run_feature_file(path: String, registry: StepRegistry) -> FeatureReport`

Reads the file, calls `parse_feature`, and — on `ok` — runs every scenario and folds the report. On a parse `err`, it yields a `FeatureReport` whose single scenario carries the `bad_feature_syntax` fault (a spoke chooses the exact surfacing, but a parse failure must be reported as a failure, never swallowed).

### 8.1 The CLI

```
honest-gherkin run <path> [--steps <dotted.module.path> ...]
```

`<path>` is a `.feature` file or a directory (searched recursively for `*.feature`). Each `--steps` module exports `register(registry) -> registry`; the CLI threads the registry through them in order. Exit code is `0` iff `total_failed == 0` across all features, else `1`.

### 8.2 The step-module contract

A step module is an ordinary module in the host language exporting a single pure-ish builder:

```
register(registry: StepRegistry) -> StepRegistry
```

It calls `register_step` once per pattern and returns the accumulated registry. There is no decorator, no global, no import-time side effect. This is the contract honest-test §8.2's auto-generated scaffolding must emit, per the amendment to that section.

---

## 9. Universal Gherkin Coverage and Function-Point Velocity

### 9.1 Every function carries exactly one gherkin

A gherkin is not reserved for user-facing chains. **Every function in every honest-check role — `@link`, `@recognizer`, `@boundary`, `@helper` — carries exactly one gherkin scenario** stating its behavior in `Given`/`When`/`Then`. A pure internal helper is specified by a gherkin just as a top-level chain is.

This generalizes honest-test §8.3, which previously scoped `.feature` files to chains. The narrower rule is withdrawn for the same reason the wrap-an-existing-framework deferral was: a partial discipline leaves behavior unspecified and uncounted exactly where it is hardest to see — inside the helpers.

A roled function without a gherkin is a violation of the same kind as an orphan under **HC-R001** (a function with no role and no reachable-from-roled caller). HC-R001 guarantees every function is *reached* by auto-generation; universal gherkin coverage guarantees every function is *specified and counted*. The diagnostic is **HC-P009**, generalized from "chain without `.feature`" to "roled function without a gherkin."

### 9.2 The gherkin is the function-point unit

Because coverage is universal and one-to-one, **the count of gherkins is a direct function-point count.** Not backfired from lines of code, not estimated by expert judgment: counted. Function-point velocity is gherkins-passing per unit time — a measured rate, not a projected one. This is the per-function realization of the "spec-as-FP-count" question posed in `research-protocol.md`: it pushes that model from conformance-law granularity down to every-function granularity.

### 9.3 Gherkin and auto-generation are complementary

The gherkin and honest-test's auto-generated property suite are not redundant; they are the two halves of "defining is testing":

- The **gherkin defines and counts** the behavior: the human-meaningful statement of what the function does, and therefore the function-point unit.
- **Auto-generation proves** it: running the function across every point of its bounded input space (purity, mutation, idempotency, classification per honest-test §§3-7).

Requiring a gherkin per function does not replace auto-generation. It is the countable specification layer that sits above the exhaustive proof. A pure function still earns its exhaustive property run; the gherkin names the one behavior that run proves.

### 9.4 Real FP is triangulated, not read off one method

A single counting method is a single point of failure, exactly as a single correctness check would be. The framework triangulates correctness across three mutually-confirming lenses: static (honest-check), exhaustive (honest-test auto-generation), and behavioral (the gherkin). It triangulates **function points** the same way, across independent measures that must track each other:

1. the per-function gherkin count (§9.2, finest granularity);
2. the conformance-law → IFPUG elementary-process mapping (`research-protocol.md` §3.4 / Appendix A);
3. the feature/screen count (Paper 1 method).

These cover overlapping but non-identical scopes, so they are never numerically identical. The discipline is to treat their agreement, and the shape of their disagreement, as a signal:

- **Mild divergence is acceptable**: measurement noise from differing granularity (one chain is several functions is several gherkins, but maps to fewer IFPUG elementary processes). Recorded, not actioned.
- **Wild divergence is a defect signal**, and its *direction* localizes the defect (gherkin count far above the others → over-decomposition or trivial-function inflation; far below → claimed behavior with no specifying function).

The thresholds that separate mild from wild, and the triage by direction, are normative in `research-protocol.md` §3.4. This section only fixes the unit (the gherkin) and the requirement (universal coverage) that make the triangulation possible.

---

## 10. Conformance Requirements

A language spoke's honest-gherkin is conformant iff:

1. **IR shape.** `parse_feature` on a given source produces a `Feature` with the field set in §2 and identical `Scenario`/`Step` decomposition.
2. **Faults as data.** `parse_feature`, `compile_pattern`, and `match_step` all **return** Results; none raises for malformed input, unknown placeholder type, unmatched, or ambiguous steps.
3. **Bounded vocabularies.** The four frozensets (`STEP_KINDS`, `STEP_STATUSES`, `SCENARIO_STATUSES`, `FAULT_CODES`) match this spec exactly.
4. **Fold semantics.** `run_scenario` folds over an empty immutable context, threads each handler's returned context forward, and stops at the first non-ok step.
5. **No global registration.** Steps are registered only through `register_step` on a `StepRegistry` value; no decorator or module-global registry exists.
6. **Exception boundary.** The only exception caught is one thrown by a developer's handler, classified per §7.1. Engine-internal control flow uses Results.
7. **Single I/O boundary.** Only `run_feature_file` and the CLI read the filesystem.
8. **Universal coverage.** Every roled function (`@link`, `@recognizer`, `@boundary`, `@helper`) carries exactly one gherkin (§9.1); a roled function without one raises HC-P009. The gherkin count is exposed as the direct function-point count (§9.2).

The cross-tier test-of-record for these requirements lives in `specs/honest-conformance-suite.md`.

---

## 11. Relationship to the prototype

The Python reference at `python/honest-gherkin/` predates this spec and was authored ad hoc, but with the execution model this spec ratifies: pure fold parser with line-kind dispatch, registry-as-data, fold-over-immutable-context runner, bounded fault vocabulary, reports-as-data, single CLI I/O boundary. The spec is normative; where the prototype diverges, the prototype is the bug:

- `parse_feature` currently raises `ValueError` for `bad_feature_syntax`; §3 requires it to return `{ "err": StepFault }`.
- `match_step` currently raises `StepUnmatchedError` / `AmbiguousStepError`; §5.1 requires it to return a Result.
- `compile_pattern` currently raises `ValueError` for an unknown placeholder type; §4 requires a returned fault.
- `match_step` carries dead code (a kind-comparison block with no effect); it must be removed.

These are the corrections the spec-first rebuild applies. Everything else in the prototype stands.

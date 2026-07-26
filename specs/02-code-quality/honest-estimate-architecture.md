# honest-estimate: the size, cost, and duration estimator (component spec)

The estimator derives the three dimensions every software project has always been measured by — size, cost, and duration — plus a quality reading, from the contract boundary: the same declared surface the framework already uses to generate types and tests. Size is read off the declaration and is exact. Cost and duration are projected as bands at declaration time and measured directly as actuals at build time. Each is reported in its own native unit. Capers Jones's constants are a benchmark the estimator tests against, not the ruler it measures with. The estimator adds outputs to the boundary artifact that already yields types and tests; it introduces no new source of truth.

This is a component of the framework. The empirical study that validates its claims is registered separately and is not part of this spec; §14 points to it.

## 1. Purpose

Function-point counting has two incumbent forms and both are inferences with variance: IFPUG counts from a human's reading of a specification, and backfiring estimates from lines of code. The estimator changes the epistemic status of the number. Because every elementary process is declared on the contract boundary and proven to exist by a passing test, size is a census of verified behaviours rather than an estimate. An unverified function point is a claim; a verified one is a fact.

The estimator reads the declaration (the `.hd`), not the code, for everything it can know at declaration time. That is what lets it emit size and projected cost and duration bands before implementation exists — a capability neither IFPUG (needs a human counter) nor backfiring (needs finished code) has.

**The north star.** A single verified feature should map to a fixed size value with tight variance — so that counting features *is* counting size, with no translation layer to trust. This is reachable in the Honest world specifically because Honest Test decomposes complexity into atomic features (one behaviour, one branch, one edge case per feature): the per-process complexity that IFPUG puts in a Low/Average/High *weight*, Honest puts in the *count*. Uniform atomic features have a tight size-per-feature ratio by construction. COSMIC's uniform, judgment-free unit (§6.1) is the native realization of that target. Whether the variance is actually tight is a measured result of the validation registration (§14), never an assumption.

## 2. Working terms

- **Elementary process.** The smallest unit of activity meaningful to a user OR enforceable as a system-boundary contract. The second clause promotes internal and system behaviour to first-class; standard function-point counting sees only the first. Counting rule in §7.1.
- **COSMIC function points (CFP).** The uniform native size unit: a count of data movements (Entry, eXit, Read, Write), each worth exactly 1, no weighting, no cap. ISO/IEC 19761. The realization of the north star. §6.1, §7.2.
- **Verified Function Points (VFP), provisional name.** The IFPUG-flavoured weighted size unit: the count of elementary processes, split into an IFPUG-countable subset and a beyond-IFPUG internal subset. The corpus-comparability bridge, because Jones's tables are IFPUG-denominated. §6.1, §7.1.
- **Bits of specified case-distinction.** The depth reading. Defined in §6.1.
- **Cost.** Dollars: compute + human oversight + tooling. The business axis, and the clean dollar bridge to Jones. §6.2.
- **Duration.** Wall-clock calendar time. The time-to-market axis. §6.3.
- **Code-honesty census.** The existing per-`def` count that `feature-gate.sh` enforces (one gherkin scenario per function, privates included). It is NOT a size number. See §4.

## 3. Scope and non-goals

In scope: emit size (three readings), cost, duration, and a quality reading, plus a Jones-comparison block, from the `.hd` and the built code, each carrying its grain, epistemic status, and availability stage.

Non-goals, stated so they are not drifted into:

- The estimator is not a code-honesty gate. honest-check keeps that job. It must not re-purpose the per-`def` census as size (§4), nor count feature files or scenarios as size (§6.1, §7.1) — those are the per-`def` grain the unit decision rejects.
- The estimator does not emit a single fused "adjusted" figure. It reports components (§6, invariant I2), now more of them, so the rule matters more.
- The estimator does not report effort in person-months. Person-months was the human-era proxy for cost; the estimator measures cost in dollars directly (§6.2, I3).
- The estimator does not apply the IFPUG or Jones estimating adjustments — VAF, Feature Points algorithm estimation, verbosity haircut. Those estimate content the estimator counts directly; applying them double-counts (invariant I4).
- The estimator does not measure "in Jones units." It measures in native units and *tests* Jones's constants as a benchmark (I3, §6.5).

## 4. The unit (settled; do not re-open)

The size unit is the **spec-tier elementary process, read from the `.hd` contract boundary.** It is NOT the code-tier function, and it is NOT the feature-file/scenario count.

Rationale on the record: the per-`def` count is implementation-dependent. Splitting one function into five helpers raises it with zero new functionality (observed on this codebase: the honest-check per-`def` census moved 237 → 245 as private helpers were added). An implementation-dependent count cannot be a functional-size metric, because two conformant implementations of one spec would post different sizes, which breaks implementation-independence.

Reading from the `.hd` makes the grain problem structural rather than a rule to police: the `.hd` declares design-significant functions, not every helper, so a count taken from it cannot be inflated by decomposition. Both native size units (CFP and VFP) are spec-tier, read from the `.hd`. The per-`def` code-honesty census stays, unchanged, under its own name, as proof that nothing in the tree is unspecified. The estimator and honest-check read two different grains and emit two different numbers, and the spec keeps them separate by construction.

## 5. Inputs

1. **The contract boundary — the `.hd` Document IR** (`honest_design.read_hd`). Each module's functions and their roles, the `invokes` graph, chains, routes, entries, `side_effect` reads/writes, closed sets, vocabularies, and composed types. Available at declaration time, before implementation exists. The estimator's primary and only declaration-time input.
2. **The built code and its suite.** Required only for the quality reading (§6.4) and for the actuals fed to the corpus.
3. **The price and rate model.** Compute/API prices (exact, per provider, dated), a loaded oversight labour rate, and Capers Jones benchmark constants (productivity, cost-per-FP, defect potential, defect removal efficiency, backfiring, schedule). Every Jones figure is a prior to verify against the published tables, and to *test* rather than assume for AI-generated code (I3).
4. **The corpus.** The accreting store of prior tuples (§12). Consumed for local ratios once significant; written to on every build.

## 6. Outputs: three dimensions plus quality, never fused

Software has always been measured on three axes — size (what got built), cost (what it took in dollars), duration (how long in calendar time) — plus quality. The estimator reports each in its own native unit, and a separate block comparing to Jones. Each field carries a grain (spec-tier or code-tier), an epistemic status (deductive, measured, or inductive-proxy), and an availability stage (declaration-time or build-time). No field is fused into another (I2).

### 6.1 SIZE (spec-tier, deductive)

Three readings of one declared surface, none of them fused:

**COSMIC CFP — the uniform native unit.** Count of data movements across all elementary processes, one CFP each, additive, no cap (§7.2). This is the "reliably one unit" reading: judgment-free and mechanical from the `.hd`.

**VFP — the weighted IFPUG-comparable unit.** Count of elementary processes (§7.1), split into an IFPUG-countable subset (user-facing transactions plus internal logical and interface files) and a beyond-IFPUG internal/system subset, with the ratio between them. Rate application depends on this split (I4).

**Bits of specified case-distinction — depth.** The log-2 of the declared case space: the SUM over an elementary process's parameters of log-2 of each parameter's declared cardinality, where the parameter is typed by a closed set or vocabulary, recursing into composed types (a composed type's cardinality is the product of its components', so its log is the sum of their logs). Log turns the multiplicative case space additive and bounded. Counted over closed vocabularies and declared equivalence classes, NOT raw input cardinality: a parameter typed `str` or `int` contributes nothing (see §7.4). Bits are summed over *inputs* only: a deterministic contract cannot distinguish more cases than its input partition admits, so the output vocabulary (e.g., a classifier's result set) does not add depth — it is already counted as an eXit movement in CFP.

### 6.2 COST (dollars, dated)

- Status: projected band at declaration-time (size × rate); measured actual at build-time.
- Decomposition, all in dollars: **compute/API** (exact, off the provider bill — the dominant, shrinking term), **human oversight** (review and steering time × loaded rate), **tooling/infra** (amortized). Report the total and each term.
- Cost is the business axis and the clean bridge to Jones: Jones publishes cost-per-FP in dollars, so no unit translation is needed (unlike person-months ↔ tokens). Tokens and iterations are *inputs to compute-cost*, not a labour unit.
- **Cost is non-stationary.** Compute prices fall, so AI cost-per-FP drops over time independent of the code. Every cost figure MUST carry the date and price basis it was computed at ("cost/FP at compute prices on date X"). Size and duration are quoted flat; cost is quoted dated (I6).

### 6.3 DURATION (wall-clock)

- Status: projected band at declaration-time (from size); measured actual (clocked) at build-time.
- Calendar time to deliver. Directly measured — nothing to infer — and business-critical (time-to-market). Stationary.
- This is the axis where AI most violates the incumbent models: Jones and COCOMO derive schedule from effort with a hard floor (Brooks's law — a human team cannot compress past a communication-overhead limit). An AI "team" scales instantly with no communication overhead, so duration can compress below that floor; what now bounds it is the generate/test/fix loop, review bandwidth, and non-parallelizable dependencies. The AI-era size→duration model is new and unmeasured, which makes this dimension a contribution in its own right, not a leftover.

### 6.4 QUALITY (code-tier, inductive proxy)

- Status: proxy-measured at build-time.
- **Mutation density per process:** non-equivalent mutants admitted per elementary process (`mutate.py`, net of `conformance/mutants_setaside.json`). Also the falsifier of the claim that Honest construction bounds logical complexity: expected low and flat under the target domain, and a build that violates that is a finding, not a defect in the metric.
- **Escaped-defect density:** held-out-suite escapes per elementary process. A proxy for Jones's defect potential, not the full construct: a fresh build has no requirements/design/field-defect lifetime data, only the code-time proxy. Report it as a proxy, labelled.

### 6.5 JONES comparison (tested, not assumed)

A separate block, never mixed into the native numbers. For each Jones construct, report the estimator's native measurement, Jones's benchmark value, and the measured local ratio between them: backfiring (LOC/FP), cost-per-FP, defect potential, and schedule. Jones's constants may not hold for AI-generated code — his corpus predates it — and any discrepancy is a finding, not an error (§12, §14).

## 7. Counting rules

### 7.1 Elementary-process rule (VFP breadth; reads from the `.hd`)

An elementary process is a declared function the module exposes at its boundary rather than consumes internally. **The boundary role is the authority:**

- every function carrying a boundary or orchestrator role (`boundary_in`, `boundary_out`, `orchestrator`) is an elementary process — a declared I/O or coordination contract.

Where roles are populated, that is the count. Where a module's roles are not yet populated, a **fallback heuristic** applies and the module is flagged as under-declared, never silently trusted: a pure `fn` not invoked by any sibling in the module is treated as a boundary contract, and one invoked by a sibling is treated as an interior helper (covered by its caller, §7.2). The fallback resolves the dual-use case wrongly — a function can be both a genuine external contract and invoked internally — which is exactly why the role, not the graph, is the authority; the graph is a stopgap for un-enriched modules and its use is surfaced, not hidden.

A chain link is excluded as interior by the invoke rule already, *unless* it also carries `boundary_out` (it is the chain's output contract), in which case it is counted by role. This is why the exclusion is stated for non-terminal links specifically: the terminal link may be the boundary_out and must count. Do not "simplify" this to exclude all chain links.

The size count is a census, not an estimate, and it is read from these `.hd` elementary-process declarations — NOT from the count of feature files or scenarios (that is the per-`def` grain the unit decision rejects, §4). The relationship to feature files is a *verification guarantee*, not a counting source: because every elementary process is a declared function, it has a scenario and a passing test, and that is what makes the census verified. No elementary process without a passing test; the test count is not the size.

> Enrichment precondition: a correct census requires the `.hd` corpus to populate roles (and, for the fallback, the `invokes` graph) faithfully. A module with public contracts but no boundary roles and an empty `invokes` graph is under-declared, and this is itself checkable (§15).

### 7.2 COSMIC data-movement rule (CFP; reads from the `.hd`)

Each elementary process is a COSMIC functional process; its size is its count of data movements, minimum 2. Mapped from the `.hd`:

- `boundary_in` receiving external data → **Entry** (the triggering data group).
- `boundary_out` / a data group returned across the boundary → **eXit**.
- `side_effect reads "<store>"` → **Read**.
- `side_effect writes "<store>"` → **Write**.

Each movement is 1 CFP; total CFP is the sum over all processes. A data movement moves a **data group** — a bundle of attributes about one object of interest that travel together — not a single field and not necessarily one-per-parameter: three parameters describing one object are one Entry. Data-group identity is read from composed types (one composed type ≈ one data group).

> Caveat (open item, §15): this boundary-role → data-movement mapping is clean conceptually, but COSMIC has specific counting rules (data-group identity, when repeated movements collapse, what bounds a functional process). Validate the mapping against COSMIC's measurement manual before treating `.hd`-derived CFP as certified COSMIC; until then it is reported as "CFP (Honest mapping, uncertified)."

### 7.3 Boundary integrity is the counting boundary

Only behaviours exposed on the module's contract boundary count. A helper internal to a module does not add to size; it is covered by the boundary contract that invokes it. This prevents inflation by decomposition and keeps size at the spec grain.

### 7.4 Closed-vocabulary precondition (hard gate on the depth number)

Bits of specified case-distinction is deductive and meaningful only over closed vocabularies and declared equivalence classes. Where a parameter admits an open or unbounded input with no declared partitions, the case space is ill-defined and the estimator MUST flag that parameter and refuse to emit a depth contribution for it, rather than emit a raw-cardinality figure. This is the principled reason the estimator is Honest-native: closed vocabularies are what make case-space equal behavioural-distinction-space.

Declaring the number of equivalence classes for an otherwise-open scalar (so a bounded integer contributes the log of its partition count rather than nothing) requires a honest-type primitive that does not yet exist. Until it lands, depth ships for closed-vocabulary and composed-type parameters and flags open ones; the open-scalar contribution is an upstream dependency, not an estimator gap (§15).

## 8. Invariants (the honesty contract, load-bearing)

- **I1. Deductive size; measured cost and duration; proxied quality.** Size (§6.1) is read off contracts and reported as certain. Cost and duration are projected as bands at declaration time and are directly *observed actuals* at build time (bills, clock) — not inferred after the fact. Quality (§6.4) is a labelled proxy. No dimension borrows another's certainty, and no projected band is reported as a point value.
- **I2. Never fuse orthogonal measurements.** The three size readings, cost, duration, and quality are separate outputs. No single adjusted figure. The bits-per-process ratio (bits over VFP) may be reported as the computed replacement for IFPUG Low/Average/High weighting, but the components remain visible. With more outputs than before, this rule matters more, not less.
- **I3. Native units; Jones tested, not borrowed.** The estimator measures in native units (CFP, VFP, dollars, calendar time). Jones's constants are a benchmark it tests against and reports a measured local ratio for (§6.5); they are never imported as the unit of measure, and any COSMIC↔IFPUG relationship is measured on Honest code, never taken from a generic off-the-shelf conversion.
- **I4. Explicit internal turns estimators off.** Because internal and system function points are counted, the VAF, Feature Points algorithm estimation, and any verbosity haircut are not applied. Base-rate constants are applied to the IFPUG-countable subset (§6.1); the beyond-IFPUG internal count is the correction for atypical internal share, not an additional multiplicand.
- **I5. Manipulation checks are not outcomes.** Slop-Audit adherence indicators are adherence signals, never quality outputs, so no output is a Honest principle scored against itself.
- **I6. Cost is dated; size and duration are flat.** Compute prices fall, so cost is non-stationary. Never quote a cost without its price-date and basis. Size and duration carry no such date.

## 9. Integrity and the Goodhart limit

Auto-generated size is only as honest as the `.hd` is complete. Under-declaring the boundary shrinks size, so once money or schedule attaches to it there is an incentive to thin the declaration. Three defences, with their limits:

- honest-check's conformance tier already checks that code matches its `.hd` declaration (role reachability, orchestrator discipline). The measurement instrument and the quality instrument are largely the same instrument.
- The bits-per-process ratio is an integrity tripwire: hollowing a process drops bits-per-process even when the process count holds. Emit it as a monitored signal.
- Limit, stated plainly: honest-check can verify a vocabulary is closed but not that its members are semantically real; a linter cannot tell a meaningful vocabulary value from padding. At the point size carries economic weight, human audit of vocabulary meaningfulness is still required. The tripwire does not make gaming impossible; it makes gaming visible and expensive.

## 10. Staging

- **Declaration-time (before implementation):** all of SIZE (§6.1), a projected COST band (§6.2), and a projected DURATION band (§6.3), from the `.hd` alone.
- **Build-time (after green):** QUALITY (§6.4), COST actuals (bills + tracked oversight), DURATION actuals (clock), and the Jones comparison (§6.5) — all fed to the corpus.

## 11. Gate ordering and the Silence index (target state)

This section describes a target, not the current gate. The estimator is designed to report alongside the framework's verification gates, in order of what each closes: structural adherence, then specified-behaviour completeness, then verification completeness.

The gate chain as it exists today (`coverage-all.sh`, `feature-gate.sh`, `mutate-*.sh`, `.githooks/pre-commit`): honest-check (structural) → coverage to 100% line+branch → value-oracle → feature bijection → mutation adequacy. Umbra and its Silence index are NOT wired into this chain. When Umbra is wired, the Silence index is emitted as the measure of how much declared behaviour the delivered suite actually constrains, bounding the residual semantic risk that structure and passing tests alone do not close. Until then, the estimator emits its numbers without a Silence index.

## 12. Corpus interface — the empirical bridge-builder

Promoted from a byproduct to a deliberate program. Every build emits one tuple: the three size readings (CFP, VFP, bits), cost (dated, decomposed), duration (projected and actual), and the quality proxy. From it, empirically and with real variance, the corpus establishes: the COSMIC↔IFPUG crosswalk *for AI-generated code* (measured, not converted), native cost/FP and duration/size constants for the AI regime, and a test of whether Jones's constants hold there at all.

Phase 1 uses Jones constants (and current compute prices) as priors. Phase 2, once the corpus reaches its own significance, reports native constants from the corpus; the switch is explicit and dated, and nothing borrows significance it has not earned. No incumbent can accrete a corpus this way, because their size numbers cost human labour; here every build emits one for free.

Two design requirements, because they decide validity:

- **Diversity, not volume.** Credibility comes from a broad, non-toy population of specifications (domains, sizes, languages) — not from running one spec through many seeds. Large N of a narrow population is precise and useless. Sampling the spec space broadly is the real cost; volume is nearly free.
- **Reproducibility.** The pipeline, specs, and generation/counting harness are published so anyone can regenerate and recount the corpus. A reproducible corpus is more credible than an authoritative-but-private one — the credibility asset Jones's proprietary corpus never had. Pre-registration and blind defect scoring close the allegiance gap on top of that.

## 13. Output artifact (schema sketch)

A structured object, each field tagged with grain and status, organized by dimension:

- `size` (spec-tier, deductive): `{ cosmic_cfp, vfp: {total, ifpug_countable, beyond_ifpug_internal, internal_share_ratio}, bits_of_case_distinction, open_vocab_flags: [...], cfp_certified: false }`
- `cost` (dollars, dated): `{ compute, oversight, tooling, total, priced_at_date, price_basis }`
- `duration` (clocked): `{ projected_band, actual_wallclock }`
- `quality` (code-tier, proxy): `{ mutation_density_per_process, escaped_defect_density }`
- `jones` (tested, not assumed): `{ backfiring_ratio, cost_per_fp_vs_jones, defect_potential_vs_jones, schedule_vs_jones }`
- `integrity`: `{ bits_per_process, honest_check_conformance_clean, umbra_silence_index }`
- `assumptions`: a ledger, each entry with value and source, or "uncalibrated — verify". The diseconomy-of-scale exponent lives here as a labelled Jones prior recalibrated by the corpus (§12) — never hardcoded, because whether Honest code flattens that exponent is exactly what the scaling arm of the validation tests.

## 14. Validation

The estimator's claims are tested by a separate empirical registration and its companion arms, held in the personal research track, not in this repo. This spec defines the instrument; the registration: measures the size-per-feature variance that the north star (§1) claims is tight; establishes the COSMIC↔IFPUG crosswalk and its spread on Honest code by counting both on the same builds; tests whether size predicts cost and duration as scale grows (and whether Honest flattens the diseconomy exponent); and stress-tests Jones's constants in the AI-generated-code regime he never had. The Foundation cites that research; it does not author it.

## 15. Open items to lock before this is load-bearing

- **`.hd` enrichment (roles + `invokes`).** The census authority is the boundary role; a correct count requires the corpus to populate roles faithfully, with the graph fallback only for un-enriched modules (flagged). Reproducibility check needed so two runs converge.
- **COSMIC mapping certification (§7.2).** Validate the boundary-role → data-movement mapping and data-group identity against COSMIC's measurement manual before calling `.hd`-derived CFP certified COSMIC.
- **Open-scalar equivalence classes (§7.4).** A honest-type primitive to declare an open scalar's N equivalence classes. Upstream dependency; depth ships closed-vocab-and-composed-type-only until it lands.
- **Umbra wiring (§11).** The Silence index is a target, not a current gate.
- **Rate and price constants (§5.3).** Every Jones benchmark figure is a prior to verify against the published tables and to test for AI code; compute prices are dated inputs.
- **Corpus diversity (§12).** A broad, non-toy spec population is the validity bottleneck, not run volume.

## 16. Placement and relationship to other specs

honest-estimate is dev/authoring tooling, like honest-check and honest-design; it is never a runtime dependency of an adopter's app. It reads honest-design's `.hd` IR (§5.1) and, at build time, honest-test's mutation output (§6.4). It sits downstream of honest-design in the dependency order — it cannot read a surface that does not yet exist — and, like honest-check's conformance tier, it consumes the `.hd` IR rather than the tree-sitter grammar directly.

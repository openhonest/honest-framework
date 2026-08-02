# Finite-testability: the shared definition

Status: v0.1, locked core. **Tool-neutral and shared.** This is the common definition of finite-testability that the Honest Framework gate (honest-check `HC-P018`, honest-test §4.8) and the Slop Audit meter (`L1.18` / `L1.19`) both build on. It is **coupled to neither tool**: each implements it independently and both are checked against the same conformance vectors (`finite-testability-vectors.json`). Neither tool imports the other; the audit **cites** this definition and **vendors** the vectors by case id.

Interim location note: this document lives under `honest-framework/specs/` only because the Foundation repository is not yet initialised. It is a standalone artifact intended for a neutral Foundation home and is relocatable without change. Placement does not imply ownership by the framework.

## 1. The predicate

A piece of state is **testability-neutral** iff the production decisions reaching it partition its domain into a statically-enumerable finite set of equivalence classes.

**Partition-count, not value-count.** The cost is the number of equivalence classes the reaching decisions impose on the state, not the cardinality of the state's values. `if count >= max` carves a 64-bit integer into two classes, so an integer that only ever meets comparisons against constants is cheap. A value used as an unbounded lookup key is not: the decision it reaches has an unbounded arm-space.

**Observe-only** state — written but never reaching any production decision — is the degenerate neutral case: an empty reaching-set.

## 2. Definitions

- **Production decision.** A site whose outcome depends on a value: a branch condition, a `match`/dispatch arm selector, an effect argument, a return value, or a call argument to a non-asserter.
- **Reaching-domain of S.** The set of distinct values of state S that can reach a production decision.
- **Partition.** The equivalence classes the reaching decisions impose on the reaching-domain (e.g. `>= max` imposes two classes; a dispatch over a closed vocabulary imposes one class per member).
- **Observe-only.** S reaches no production decision (empty reaching-set). Written by an observer/boundary, read only by an asserter.
- **Bounded target set (of a call).** The callees a call site can invoke are a finite, statically-visible set. Its complement — an unbounded target set — makes the reaching-domain uncomputable (§6).

## 3. Verdicts

Every piece of state resolves to exactly one of three verdicts:

- **NEUTRAL** — the reaching partition is a statically-enumerable finite set (or empty). Finitely testable.
- **PROMISCUOUS** — the reaching partition is *provably* unbounded (e.g. a shared-write value reaching an unbounded-key dispatch). Not finitely testable; a proven finding.
- **UNRESOLVED** — the reaching-set cannot be decided statically within the analysis scope (§6). Fail-closed: counted against testability, but disclosed as *undetermined*, never asserted as promiscuous.

## 4. Operational rules

- **Analysis scope is the class or module, not the function.** Instance-state writers and self-branches are the methods of the class, enumerable with no whole-program pass. At function scope everything escapes; at class scope most instance state resolves.
- **Returns are output, not promiscuity.** A returned value is NEUTRAL for the function that produces it; covering the returned domain is the caller's concern (compositional). Returns are never fail-closed.
- **Fail-close (UNRESOLVED) only on** a value passed to an unbounded call target, or reflective/dynamic access that hides the reaching-set. A shared-write value reaching an unbounded-partition decision is PROMISCUOUS (proven), not merely unresolved.
- **Bounded includes declared-closed-set dynamic access.** `getattr`/`setattr`/`import` whose name argument ranges over a *declared closed set* (a vocabulary, a watch-list, an enum) has a bounded target set and is NEUTRAL. The violation is an *unbounded* name argument, not dynamism as such (this is the bounded-vs-unbounded, not static-vs-dynamic, line).

## 5. Two forces, one predicate: the gate/meter asymmetry

The same predicate is realised two ways, because the two tools have different evidence:

- **The gate** (Honest Framework, declaration-aware). It *demands* the property be locally provable and rejects code that is not: a decision must dispatch over a closed set (`HC-P001`), a domain must be a declared Set (honest-type), a call target must be bounded (`HC-P018`). Instrumentation that holds observe-only state is recognised by **declaration** — a role, a boundary marker, or an explicit `# honest: disable <rule> <reason>` — never by guessing. The gate achieves finite-testability by construction: it forbids the constructs that create unbounded reaching-domains, so it never needs to compute the partition.
- **The meter** (Slop Audit, declaration-agnostic). It cannot demand structure, because it audits any repository. It *infers* the reaching-domain from the AST and **fail-closes to UNRESOLVED** whatever it cannot prove, then discloses that blindness (§7). Clean code earns the neutral verdict by being provably local; the burden is on the code.

Same definition, different amount of evidence, different force: the gate rejects, the meter measures.

## 6. The decidability precondition

The reaching-domain is undecidable in the sound direction precisely when dynamic dispatch, reflection, `getattr`/`import` from unbounded input, or monkeypatching make "where does S go, and what reads it" unknowable. The gate's rejection of exactly those constructs (`HC-P018` for unbounded call targets, honest-test §4.8 for runtime rebinding) is therefore not incidental hygiene: it is the precondition that makes the partition **locally computable**. The gate manufactures the decidability the meter otherwise lacks; the meter fail-closes on the same constructs and names them.

## 7. Coverage disclosure (meter obligation)

A meter over arbitrary code MUST publish its own coverage beside the ratio — the cone of light turned on its own blindness. The disclosure is **mandatory and decomposable**, never a bare scalar (a scalar lies by aggregation: "90% resolvable" can hide that 100% of the security-critical state fail-closed). It is a two-dimensional matrix, reported per module and per finding-band:

|                | observe-only | drives-a-decision |
|----------------|--------------|-------------------|
| NEUTRAL        | count        | count             |
| PROMISCUOUS    | count        | count             |
| UNRESOLVED     | count        | **headline blind spot** |

The **UNRESOLVED-and-drives-a-decision** cell is the load-bearing hole: where the score is both a lower bound and consequential. A low resolvable-fraction is itself a true finding — the code is too dynamic to measure and the score is a lower bound.

## 8. Conformance vectors

Both tools pass the same cases in `finite-testability-vectors.json` (the gate by construction/declaration, the meter by measurement). The locked case set and expected verdicts:

| case id | verdict | drives a decision | reason |
|---|---|---|---|
| observe-only-recorder | NEUTRAL | no | empty reaching-set |
| value-indexed-cache | PROMISCUOUS | yes | reaching partition unbounded (unbounded key) |
| multi-writer-capped-counter | NEUTRAL | yes | domain {0..N}, two classes; writer-count irrelevant |
| raw-int-vs-constant | NEUTRAL | yes | partition = comparison count + 1 |
| single-writer-local-but-dynamic-dispatch | UNRESOLVED | yes | callee set unbounded; single-writer + local is not sufficient |
| returned-raw-value | NEUTRAL | n/a | compositional; the caller's concern |
| module-global-in-branch | PROMISCUOUS | yes | shared-write into an unbounded partition |
| pass-to-unknown-callee | UNRESOLVED | yes | reaching-set undecidable (the HC-P018 construct) |
| closed-set-dispatch | NEUTRAL | yes | partition = the closed Set's members, enumerable |
| bounded-enum-accumulator-driving-branch | NEUTRAL | yes | finite reaching-domain; drives behaviour yet stays bounded |

## 9. Governance and independence

- **Cite-and-vendor.** Neither tool imports the other. The audit cites §1 as its definition and vendors §8's vectors by case id. The framework's `HC-P018` and honest-test §4.8 cite this document.
- **Supersession.** The partition-count definition (§1) supersedes any prior scalar mutable-state ratio. A meter re-run should report the pre-partition scalar and the three-verdict distribution side by side.
- **Pre-registration.** A brand-new measured indicator built on this definition needs its own pre-registration; it must not be folded into a frozen indicator.
- **Relocatable.** This document and its vectors are a standalone artifact intended for a neutral Foundation home.

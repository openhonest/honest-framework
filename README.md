# Honest Framework

**Honest Framework isn't a framework you switch to. It's a discipline you switch on, inside the one you already use.**

Keep the framework you build on — Rails, Django, Spring. Move your business logic out of your models and into plain functions, drop the callbacks and signals that bite you at 3am, and let a linter keep you honest. Whole classes of bug stop happening, and your tests stop needing a database. Nothing new to learn — a few habits to unlearn.

Language-agnostic framework specification for code that is correct by design. The structural-correctness side of the Open Honest Foundation's three-standard portfolio.

**About.** The Honest Framework is an architectural standard for software that is correct by construction: no Big State, pure-function dispatch tables in place of classes, no hidden state, and named categories of defect eliminated by design. It is one of the three open standards governed by the Open Honest Foundation, alongside the Slop Audit and MÉTRON. It is not a tool for explainable or interpretable AI. By **Adam Zachary Wasserman** ([ORCID](https://orcid.org/0009-0002-8865-6583), [OSF](https://osf.io/user/8t64r)), founder of the [Open Honest Foundation](https://openhonest.org).

## The honesty gate

> **Any code that passes `honest-check` is, by definition, structurally Honest Code.**

The linter is the operational definition of Honest Code. Code that passes cannot represent the bug categories the framework eliminates: hidden state via classes, if/elif/else value-dispatch, I/O off the boundary, catching exceptions in business logic, indiscriminate mutable state, recognizer reuse, and the rest. There is no "mostly honest." Code passes the gate, or it is rejected as dishonest.

This is enforced at commit time: a pre-commit hook runs `honest-check` over every module, so **no dishonest code can land**. Enable it once per clone:

```sh
./bootstrap.sh
```

It points git at the in-repo hooks, verifies `uv`, and syncs the workspace. Idempotent.

**The scope, stated honestly.** The gate enforces the *structural* half of Honest Code: what is decidable from source. Behavioural honesty (purity, idempotency, correctness over every bounded input) is verified by `honest-test`'s auto-generated suite. Full honesty is `honest-check` **and** `honest-test` together.

## What's here

- `specs/` — Honest Framework specifications, tiered:
  - `specs/01-framework/` — core framework spec + conformance suite
  - `specs/02-code-quality/` — code-quality dimension
  - `specs/03-application-production/` — application-production dimension
- `articles/` — three canonical articles (honest-advantages, honest-testing, honest-type-magic)
- `principles/` — foundational philosophy
  - `poka-yoke.md` — velocity-multiplier manifesto: which categories of bug each design decision eliminates structurally
  - `honest-code-principles.md` — nineteen Honest Code practices
- `methodology/` — verification approach
  - `contract-testing.md` — user-journey-to-function contract mapping methodology
- `python/` — Python reference implementation (in active development)
- `javascript/`, `ruby/` — placeholders for additional language implementations
- `integration-test-challenge.md` — public unbreakable-todo-app challenge (a marketing activity for the framework whose results feed back into research)
- `INSTRUMENT_CONE_SYNTHESIS.md` — epistemic anchor: the instrument defines what is visible. A reminder that current code-quality metrics can't find what they aren't looking for; the framework's value is partly about expanding the cone of what's visible.
- `analyst-strategy-handoff.md` — industry analyst landscape positioning
- `bootstrap.sh` — one-time setup after clone (idempotent): enables the git hooks, verifies uv, syncs the workspace. Turns on the honesty gate (see above).
- `.githooks/` — `pre-commit` (the **honesty gate**: on the modules with staged changes it runs `honest-check` (structural) **and** their conformance suite (behavioral), blocking either failure) and `commit-msg` (enforces commit-message prefixes for research instrumentation).
- `python/lint-affected.sh` / `python/lint-all.sh` — structural gate: `honest-check` over the changed modules (pre-commit) / every module (CI).
- `python/test-affected.sh` / `python/test-all.sh` — behavioral gate: the conformance suite over the changed modules (pre-commit) / every module (CI).
- `python/honest-check/conformance/suite.json` — honest-check's conformance suite (section 9.2): each case is source-as-data plus the diagnostics it must produce. `run_conformance.py` runs it. The test-of-record, with no hand-coded per-rule tests.

The architectural-diagram renderer (honest-design) is out of scope for this repo; rendered output for FOSS modules is published at `~/dev/open-honest/honestframework-website/explorer/`. The `ui-audit` reference tool lives at `~/dev/open-honest/slop-audit/tools/ui-audit/` since it instruments one aspect of Slop Audit dimension 4.18.

## Companion standards under the Foundation

- [Slop Audit](https://github.com/openhonest/slop-audit) — measurement instrument for software quality

**The Slop Audit is the same idea pointed the other way.** This framework governs how code is written. The audit measures whether code can be exhaustively verified, which is a property of construction: it is fixed at the moment of writing, and no amount of later review repairs it. Can this be verified and has this been verified are different questions, and the audit answers the first. It reads that off the commit history, so the same panel also measures the development practice that produced the code, not only the artifact it produced. The link is mechanical, not thematic. Three of the audit's twenty Layer 1 indicators measure finite testability. The tightest is L1.18, the mutable-state ratio: the share of functions whose behavior depends on state outside their parameter list. That is the direct measure of what the no-Big-State and no-hidden-state rules forbid here. L1.19 measures the decision space those rules keep finite. L1.20 measures whether a test suite is order-independent, which pure functions are by construction. A codebase built to this framework scores well on the audit because the audit measures what the framework eliminates.

The audit's 200-repository study puts the median mutable-state ratio at 61.1% for Python, 53.0% for Java, 40.0% for C# and 14.8% for TypeScript. That spread is the case for the discipline. The default sits a long way from it, and the distance differs by language. Layer 1 ships as a tool covering nine languages. You can run it against a public repository at [try.slopaudit.org](https://try.slopaudit.org) without installing anything. Read this framework first if you are writing a codebase and want to avoid needing the audit; read the audit first if you inherited one and need to know what you have.

## Documentation site

The persona-aware reading guide lives at [honestframework.software](https://honestframework.software) (source: [openhonest/honestframework-website](https://github.com/openhonest/honestframework-website)).

## License

- Code: Apache-2.0
- Documentation content: CC-BY-NC-4.0

Foundation-governed. Will be flipped public when the framework reaches v1 reference implementation.

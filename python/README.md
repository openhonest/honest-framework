# Honest Framework — Python reference implementation

This is the active reference implementation of the Honest Framework. It is a uv
workspace: one shared virtual environment and lockfile, with each `honest-<name>/`
an independently publishable package implementing exactly one spec module.

The normative source is the specification, not this code. The flow is
**spec → implementation → conformance**, never the reverse. When behaviour here
diverges from `../specs/`, that is an implementation bug, not a spec amendment.

## Two audiences

The packages built so far are **substrate** — the type system and the linter that
the rest of the framework stands on. They are not the surface an application
author works against. Read the path that fits you:

- **You want to *use* the framework** to build an application. The adopter-facing
  surface lives in the upper-layer modules (components, dom, page), which are
  still being built. The one substrate package you invoke directly today is the
  linter: see [`honest-check/README.md`](honest-check/README.md). Everything else
  here runs underneath the modules you will actually call.
- **You want to work *on* the framework** — add a rule, implement a module, fix a
  bug. Start with [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Packages

| Package | Role | Adopter-facing? |
|---|---|---|
| [`honest-check`](honest-check/) | The static linter — the honesty gate. Parses source with tree-sitter and flags structural dishonesty. Also the toolchain that gates this repo. | Yes — you run it on your tree. |
| [`honest-type`](honest-type/) | The pure-function-table type system — recognizers, vocabularies, `classify()`, links, chains. The substrate the upper modules build on. | No — plumbing. The modules call it for you. |
| [`honest-test`](honest-test/) | The auto-generated verification layer — test cases derived from declarations (Set enumeration, adversarial neighbours). The behavioural half of the gate. | No — plumbing. You declare; it generates. |
| [`honest-parse`](honest-parse/) | The shared tree-sitter parsing boundary — the single place source is parsed. honest-check and honest-test both depend on it. | No — plumbing. |
| [`honest-persist`](honest-persist/) | Schema-first persistence — schema as data, migrations as a pure diff, queries and transactions as data. Pure functions on top, I/O only at the boundary. Transactions are atomic (all-or-nothing); making overlapping writes race-safe is the application's job, not the framework's. | Partly — adopters declare schemas; the diff/query engines are plumbing. |
| [`honest-observe`](honest-observe/) | Event-sourced observability — one append-only event log; projections are pure folds over it; `emit` writes events. `emit` reaches the outside world (id, clock, sequence, log writer) only through an injected runtime, so observe is stored by persist without importing it. The persistence boundaries instrument through it. | No — plumbing. The boundaries emit for you. |
| [`honest-errors`](honest-errors/) | The error-policy leaf — two raw payloads (browser, server) normalized to one report; what happens to a report is a pure function of the environment; a pure state-threaded throttle suppresses repeats. No I/O. Composed by observe (normalizers) and alerts (behavior table + rate-limiter). | No — plumbing. Composed by observe and alerts. |
| [`honest-gherkin`](honest-gherkin/) | The BDD execution engine — parse a feature, compile step patterns, match steps against a registry, fold and run the scenario over an immutable context, and report; all as data, no shared mutable context, faults as data. A single I/O boundary (`run_feature_file` + the CLI). honest-test runs on it. | No — plumbing. honest-test runs features through it. |
| [`honest-auth`](honest-auth/) | The authentication interface — the AuthProvider contract, a value registry, and the boundary dispatch. Identity is validated at the boundary and passed inward as data (`actor`); a link never trusts an actor from request input (honest-check HC-A001/HC-A002). Pure; the provider's recognizer and resolver are the injected I/O. | Partly — adopters declare a provider; the dispatch is plumbing. |
| [`honest-state`](honest-state/) | The single-mutator law and the taxonomy of state kinds — every declared piece of state has exactly one mutator. honest-state ships no primitives: it states the law and names each kind's store and mutator as data. The mechanics live in the home modules (user state is DATAOS in honest-DOM, domain transitions are honest-type state machines). | No — it is the law honest-check enforces. |
| [`honest-features`](honest-features/) | The feature-flag subsystem — a static flag vocabulary, flag state threaded as a value, and an HMAC-signed toggle. Pure functions only; the route is the integration boundary. honest-check (HC-HF001/HC-HF002) verifies every call site references a declared flag and every handler table covers its states. | Partly — adopters declare FEATURES and handler tables; the engine is plumbing. |
| [`honest-alerts`](honest-alerts/) | The Tier 3 message-passing layer — messages between actors, the mailbox as a projection over the event log, table-driven routing, a stateless supervisor, the lifecycle state machine, `send`/`send_and_wait`, DOM surfaces, and the observe event catalog. The decisions are pure; delivery, emit, and the reply wait reach the world only through an injected runtime, so honest-alerts imports neither honest-persist nor honest-observe. | Partly — adopters call `send` and render surfaces; the engine is plumbing. |

The package inventory and per-module status are the authoritative checkpoint; this
table is the short form. honest-alerts is the first application-tier (Tier 3) module;
the rest above are the Tier 2 substrate.

## The honesty gate

Any code that passes `honest-check` is, by definition, structurally Honest Code.
The linter is the operational definition: code that passes cannot represent the
bug categories the framework eliminates (hidden state via classes, if/elif/else
value-dispatch, I/O off the boundary, catching exceptions in business logic, and
the rest). A pre-commit hook runs the gate on every commit, so no dishonest
Python lands. Enable it once per clone from the repo root:

```sh
./bootstrap.sh
```

It points git at the in-repo hooks, verifies `uv`, and syncs the workspace. It is
idempotent. The full statement and the structural/behavioural split are in the
[repository README](../README.md).

## Conformance: the behavioural circle

The structural gate is only half the story. Every module is also verified
behaviourally, two complementary ways, and both must pass:

- A **portable contract** — `<module>/conformance/suite.json` — a language-agnostic
  collection of input/output cases. The *same* file is the cross-language
  test-of-record: it is meant to prove any language implementation conformant, with no
  host language in the loop.
- A **generative proof** — `<module>/conformance/laws_*.py` — the module's own
  declarations driven through honest-test's generators and asserted as laws across the
  generated space. This reaches what no data format can express: predicates, composed
  types, throwing functions, fake I/O boundaries, malformed input. It is where
  *defining is testing* is actually realised.
- A **value oracle** — the `value_case`s in `suite.json`, run through honest-test's
  value-assertion vocabulary (`value-check.py`, wired into the gate). Generation proves
  *properties* and *shape* but never *value*, so a pure, fully-covered function can still
  return the wrong answer; the value oracle is the known-good `(input, expected)` pair
  that catches it. A function is `proved` only when it passes the honesty checks, is fully
  covered, and its value oracle holds — or, where a value oracle cannot apply, it is
  declared exempt with a reason. Every public function that exists across the twelve
  packages is so accounted for.

**Coverage** is measured, not asserted: the gate (`coverage-all.sh`) fails below **100%
line and branch coverage**, and below a clean value-oracle run. An unhit line is dead code
or an unspecified behaviour — both are defects the gate surfaces. All twelve packages are
at 100%, and each is self-verifying in isolation.

Coverage is not spec-completeness, and the difference matters. 100% coverage proves every
line *that exists* is honest, reached, and value-checked; it cannot prove a package
implements every requirement of its specification, because a line never written is a line
the gate never misses. A module can sit at 100% coverage with a whole spec section unbuilt.
So the gate answers "is what is here correct?" — an emphatic yes across all twelve — but
not "is everything the spec asks for here?" That second question is answered per package
below. The full path — build order, seeding, and what carries across languages — is in
[`../specs/01-framework/honest-framework-spec.md`](../specs/01-framework/honest-framework-spec.md)
under *Bootstrapping a New Language Implementation*.

## Where each package stands

Every package's pure decision core is built to full depth and passes all gates. What varies
is how much of each spec's *surface* — the orchestration, drivers, CLIs, and cross-module
enforcement rules layered on that core — is built.

| Package | Spec surface |
|---|---|
| honest-parse, honest-errors, honest-type, honest-check, honest-features, honest-design, honest-rca | Spec-complete — no significant in-scope gaps. |
| honest-gherkin | Spec-complete for its current milestone; later Gherkin features (Scenario Outline, Background execution, data tables, `Rule:`) are deferred by the spec itself. |
| honest-persist, honest-auth | Substantially complete, one bounded gap each — persist: the Turso migrate-remote DDL path; auth: the no-domain-mutation conformance probe and the end-to-end conformance suite. |
| honest-observe | Pure core substantially complete; the runnable CLI (`tail`/`inspect`/`query`), the config loader, and the default threshold-projection records are unbuilt. |
| honest-test | Generation engine, honesty checks, state-machine and mutation adequacy complete; the orchestrating runner and the persist/component contract-test kinds are unbuilt. |
| honest-alerts | Pure schema and decision core complete; the active runtime drivers (escalation, TTL-expiry, the SSE live surface, channel handlers) are unbuilt. |
| honest-state | Taxonomy and the single-mutator law predicates complete; three of the four enforcement rules are in honest-check (HC-P004, HC-P016, HC-ST001 boundary-write). The fourth, HC-ST002 DOM-as-single-store, awaits honest-DOM's DATAOS manifest to read user-state declarations from the templates. |

Every code-quality module in the build order is now built, honest-rca included (the apophatic root-cause solver — the last code-quality module placed in the order). The application-production tier (`page`, `DOM`, `format`, `components`) is JavaScript, of which `honest-format` and the `domx` core of `honest-DOM` are gate-complete — honest-DOM is at the `Full` conformance level plus the §5 browser-observability primitives — and the rest is in progress. The per-package detail lives in each spec under [`../specs/`](../specs/).

## Running things

All Python runs through `uv` from the workspace root (`python/`):

```sh
# Run one module's conformance (its suite.json contract + its generative laws)
uv run --package honest-check python honest-check/conformance/run_conformance.py

# Lint a path with the linter
uv run honest-check <path-to-source>

# Gate scripts
./lint-all.sh        # honest-check (structural) across all modules
./test-all.sh        # every module's conformance (suite.json + laws)
./coverage-all.sh    # conformance + 100% line/branch coverage gate — the dogfooding bar
./lint-affected.sh   # structural check, staged modules only
./test-affected.sh   # conformance for staged modules + dependents

# The pre-commit hook runs lint-affected then coverage-all: no Python lands unless it
# is structurally honest AND its suites pass at 100% coverage.
```

## License

- Code: Apache-2.0
- Documentation content: CC-BY-NC-4.0

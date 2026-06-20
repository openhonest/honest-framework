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
| [`honest-persist`](honest-persist/) | Schema-first persistence — schema as data, migrations as a pure diff, queries as data. Pure functions on top, I/O only at the boundary. | Partly — adopters declare schemas; the diff/query engines are plumbing. |

The package inventory and per-module status are the authoritative checkpoint; this
table is the short form.

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

Completeness is **measured, not asserted**: the gate (`coverage-all.sh`) fails below
**100% line and branch coverage**. An unhit line is dead code or an unspecified
behaviour — both are defects the gate surfaces. All five packages are at 100%, and each
is self-verifying in isolation. The full path — build order, seeding, and what carries
across languages — is in
[`../specs/01-framework/honest-framework-spec.md`](../specs/01-framework/honest-framework-spec.md)
under *Bootstrapping a New Language Implementation*.

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

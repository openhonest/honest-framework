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

## Running things

All Python runs through `uv` from the workspace root (`python/`):

```sh
# Run one module's conformance suite
uv run --package honest-check python honest-check/conformance/run_conformance.py

# Lint a path with the linter
uv run honest-check <path-to-source>

# Gate scripts (CI vs pre-commit)
./lint-all.sh        # honest-check across all modules
./test-all.sh        # every module's conformance suite
./lint-affected.sh   # only modules with staged changes
./test-affected.sh   # conformance for staged modules + dependents
```

## License

- Code: Apache-2.0
- Documentation content: CC-BY-NC-4.0

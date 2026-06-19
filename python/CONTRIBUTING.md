# Contributing to the Python reference implementation

This is the under-the-covers guide: how the implementation is built, why it is
shaped the way it is, and how to extend it without breaking the one rule that
drives everything. If you only want to *use* the linter, read
[`honest-check/README.md`](honest-check/README.md) instead.

## The one rule

Every decision answers: **which category of bug does this make structurally
impossible?** A capability that does not eliminate a named bug category does not
earn its complexity. The full statement is in `../principles/poka-yoke.md`. Read
it before proposing a rule, a module, or an abstraction.

## Spec is the source of truth

The normative flow is **spec → implementation → conformance**, never the reverse:

- `../specs/01-framework/` — Tier 1, the language-agnostic framework definition. A
  Tier 1 change propagates to every language implementation.
- `../specs/02-code-quality/` — Tier 2, the per-module architectures (type, check,
  test, features, state, persist, observe).
- `../specs/03-application-production/` — Tier 3 (dom, alerts, components, page).

When the implementation behaves differently from the spec, that is an
implementation bug. To change behaviour, change the spec first, then bring every
language implementation back into line. Empirical claims must trace to a paper
indexed in `../../foundation/research-program-index.md`.

## The code obeys the rules it enforces

Every module here must itself pass `honest-check`. The constraints, in practice:

- **No classes** — `TypedDict`, `Protocol`, and `Exception` subclasses are the only
  permitted declarations. Data is plain dicts; behaviour is free functions.
- **Dict-lookup polymorphism** over if/elif/else value-dispatch. A dispatch table
  (`_RENDERERS`, `_CHECKERS`, `_ALL_CHECKS`) replaces the branch.
- **Pure functions** in the middle, **I/O only at the boundary**. The one module
  that touches argv, the filesystem, or stdout is the CLI; it carries the boundary
  declaration and is the only place that catches exceptions by design.
- **Single mutator** — there is no "the state." Each kind of mutable state has one
  mutator, so behaviour stays verifiable. See `../specs/02-code-quality/honest-state-architecture.md`.

`# honest:` suppression directives are an auditable record, not an escape hatch.
They must be **real comments**, never inside a docstring — a directive in a
docstring parses as a string, not a comment, and is silently ignored (the gate
will then fail on the very line you meant to exempt).

## tree-sitter is the only parser

Source is parsed with tree-sitter and nothing else — no Python `ast`, no Lark, no
regex parsing. tree-sitter is what makes the linter language-agnostic (the same
rule shape applies to Python, Rust, C). `honest-check/src/honest_check/parse.py`
is the single parsing boundary; every rule consumes the tree it returns.

## How a module is laid out

Each `honest-<name>/` is an independent hatchling package and a uv workspace
member:

```
honest-<name>/
  pyproject.toml                 # independently publishable package metadata
  src/honest_<name>/             # the implementation (pure, honest-check-clean)
  conformance/
    suite.json                   # the test-of-record: cases as data
    run_conformance.py           # a generic runner that builds objects from the data
```

There are **no hand-coded per-case tests**. The conformance suite is data; the
runner builds the inputs from that data and checks the outputs. The module is its
own test: anything that passes the suite is, by the suite's definition, conformant.
This is the realization of "the modules are their own test."

## The honesty gate

`.githooks/pre-commit` runs on any commit that stages `python/*.py`:

1. `lint-affected.sh` — `honest-check` (structural) over the modules with staged
   changes.
2. `test-affected.sh` — the conformance suites (behavioural) of those modules plus
   their transitive dependents, with the dependency graph read live from each
   `pyproject.toml`.

No Python commit lands while the framework fails its own linter or its own
conformance. `lint-all.sh` / `test-all.sh` are the CI-wide counterparts. Install
the hooks once with `../bootstrap.sh`.

Commit messages carry a research-instrumentation prefix (the colon is required):
`spec:` `design:` `impl:` `refactor:` `test:` `fix:` `chore:` `docs:`. A commit-msg
hook enforces it.

## honest-check internals

- `rules.py` — every rule plus `check_source(source, path) -> list[Diagnostic]`, the
  entry point. Rules are registered in the `_ALL_CHECKS` tuple.
- `declgraph.py` — the declaration graph: resolves aliases and extracts honest-type
  constructor calls so rules can reason about what a name actually refers to.
- `diagnostics.py` — the `Diagnostic` data shape and its constructor.
- `formats.py` — pure renderers (human / json / github / junit) selected by the
  `_RENDERERS` dispatch table.
- `config.py`, `suppression.py`, `watchlists.py` — pure: config normalization,
  `# honest:` directive handling, the normative I/O and nondeterminism watch lists.
- `cli.py`, `lsp.py`, `startup.py` — the boundary: I/O, the LSP loop, framework
  startup integration.

### Adding a rule

1. Implement it in `rules.py` as a pure function over the parsed tree, returning
   `Diagnostic`s. Cite the spec rule ID it implements in the docstring.
2. Register it in `_ALL_CHECKS`.
3. Add conformance cases to `honest-check/conformance/suite.json`: source-as-data
   plus the diagnostics it must produce (and counter-cases that must produce none).
4. Run the suite. Keep the linter clean on its own source.

A rule that is not yet automated is tracked in
[`honest-check/COMPLIANCE-AUDIT.md`](honest-check/COMPLIANCE-AUDIT.md) and manually
enforced until it is. The principle-to-rule map is in
[`honest-check/PRINCIPLES-COVERAGE.md`](honest-check/PRINCIPLES-COVERAGE.md).

## honest-type internals

The pure-function-table type system the upper modules build on. Recognizers are
tagged data (`{"kind": "set" | "insensitive" | "predicate"}`); `vocabulary()`
validates at construction (reserved-word collisions, Set×Set overlap) and raises
`VocabularyError`; `classify()` is the two-pass engine (classify tokens, then
resolve bindings, composed types, and Maybe). Its conformance suite has two case
kinds — `construction` (vocabulary contract) and `classify` (token-to-manifest) —
both built from data by `run_conformance.py`. Terms are defined in
[`GLOSSARY.md`](GLOSSARY.md).

## Adding a module

1. Create `honest-<name>/` with `pyproject.toml`, `src/honest_<name>/`, and a
   `conformance/` directory. The workspace picks it up via the `honest-*` member
   glob.
2. Write the implementation from the spec — pure, honest-check-clean.
3. Write `conformance/suite.json` (cases as data) and a `run_conformance.py` that
   builds inputs from the data. The gate scripts discover and run it automatically.
4. Update [`README.md`](README.md) and the glossary.

## License

Code is Apache-2.0; documentation content is CC-BY-NC-4.0.

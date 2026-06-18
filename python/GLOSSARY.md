# Glossary — Honest Framework reference implementation

A living lexicon, maintained in parallel with the Python reference build. Each
entry is the working definition as implemented, with the governing spec section
where one applies. Terms are added as each module/rule tier lands.

Specs referenced: `specs/01-framework/honest-framework-spec.md` (Tier 1),
`specs/02-code-quality/honest-type-architecture.md`,
`specs/02-code-quality/honest-check-architecture.md`,
`principles/honest-code-principles.md`, `principles/poka-yoke.md`.

---

## Framework concepts (honest-type)

| Term | Definition |
|---|---|
| **Recognizer** | A function `recognize(token, declaration) → bool`. The declaration is a Set, a callable, or a `predicate()`. Three kinds in the impl, tagged `('set', members)`, `('predicate', node)`, `('ref', name)`. |
| **Vocabulary** | A named collection of type declarations: `base_types` (name→recognizer dict) plus `composed_types` (list). The application's type system. Constructed with `vocabulary({...}, composed_types=[...])`. |
| **Base type** | A recognizer that classifies a *single* token — a Set (bounded) or a `predicate()` (unbounded). |
| **Composed type** | A *multi-token* recognizer that matches when specified base classifications are present: `composed(name, requires={type: value}, captures=type)`. Stored in `vocabulary.composed_types`; no inline/annotation form exists. |
| **requires** | Base type/value pairs that must already be classified for a composed type to match. |
| **captures** | The base type whose value a composed type binds to *its* slot, overriding that base type's own binding for the captured token. May be `maybe(type)`. |
| **Predicate** | An open-ended recognizer wrapping a callable, `predicate(fn)`. Unbounded — boundary-tested, not exhaustively enumerated. |
| **Set recognizer** | A finite, enumerable set of valid tokens. Bounded → exhaustively testable; the permutation space is closed at definition time. |
| **Binding** | A dict mapping type names → slot names; renames the keys `classify()` produces. Base and composed types share one flat binding table; composed bindings override base bindings for captured tokens. |
| **Slot** | The manifest key a classified value is bound to. |
| **Manifest** | The flat `dict` that `classify()` returns (slot→value). The typed input every link receives. Carries `_rejections` only if present; never nested. |
| **Ticket** | The result of classifying one token: `{type, value}`. An intermediate, not part of the manifest. |
| **Rejection** | A token that could not be classified or bound — represented as data in the manifest, never an exception. |
| **Fault** | A processing error inside a chain — data `{code, message, link, input}`, not an exception. Exceptions only at the HTTP boundary. |
| **Maybe** | Optional binding. A slot declared `maybe()` is always present in the manifest, as a value or as `Nothing`. |
| **classify()** | Runs recognizers over a token list → manifest. Two passes: base classification, then composition + binding resolution. |
| **Link** | A function wrapped with `@link(accepts=, emits=, boundary=)` so it receives a typed manifest. Pure unless declared a boundary. |
| **Chain** | An ordered list of links; the manifest flows from one to the next. A chain is itself a link (chains compose). |
| **Serializer link** | A link that produces HTTP output (a `Response`/`JSONResponse`/etc.) and declares an `emits` vocabulary covering the protocol surface (status, content-type, body shape). Inline serialization outside such a link escapes chain-contract testing (HC-P017). |
| **State machine** | A lookup table `(state, event) → next_state`. States and events are vocabularies; `transition()` is pure. `state_machine(states=, events=, initial=, terminal=, transitions={(s,e): next})`. |
| **Transition** | One `(state, event) → next_state` entry in a state machine's table. |

## Honest Code principles

| Term | Definition |
|---|---|
| **Honest Code** | Code that does what it says and says what it does. The prerequisite discipline: no classes (except TypedDict/Protocol/ABC/Exception), dict-lookup polymorphism, pure functions, I/O only at boundaries. |
| **Dict-lookup polymorphism** | Replace `if/elif/else` value dispatch with a dict dispatch table; adding a case is a row, not a control-flow edit. |
| **TypedDict over classes** | Data is a plain dict with declared keys — no behaviour attached. |
| **Pure function** | Input in, output out; no side effects, no hidden/global state, no I/O. |
| **I/O at the boundary** | Pure business logic in the middle; all I/O confined to the edges (CLI, routes, boundary links). |
| **Boundary** | A function/link that intentionally performs I/O, marked `@boundary` or `@link(boundary=True)` — exempt from purity rules. |
| **Big State** (the enemy) | Hidden state, undifferentiated state, and multiple sources of truth — the failure modes the framework refuses to represent. |
| **DATAOS** | "DOM As The Authority On State." The DOM *is* the state store; no parallel client-side data model. |
| **Poka-yoke** | The meta-principle: every framework decision must make a *named category of bug* structurally impossible, or it does not earn its complexity. |

## honest-check (the linter / pre-auto-generation gate)

| Term | Definition |
|---|---|
| **honest-check** | The static linter. Answers one question: *can the complete auto-generated test suite be generated from this code's declarations?* If not, the code is dishonest and is rejected at the pre-commit boundary. |
| **Rule (HCxxx / HC-Pxxx / HC-SMxx)** | A single static check; each names a reason auto-generation cannot proceed. Implemented as a pure `check(root_node, source_bytes, path) → [Diagnostic]`, registered in `_ALL_CHECKS`. |
| **Diagnostic** | A reported violation: `{rule, severity, path, line, col, message}`. The single record that drives every output format. |
| **Severity** | `error` / `warning` / `info`. Any `error` sets exit code 1; default reporting threshold is `warning` (infos hidden). |
| **Declaration graph (declgraph)** | The extracted honest-type constructor calls (vocabularies, bindings, links, chains, composed types, state machines) that rules operate on — separating parsing from rule logic. |
| **Alias resolution** | Mapping import aliases to canonical `honest_type` names so calls are recognised regardless of import form (`from honest_type import chain as c`, `import honest_type as ht`). |
| **Watch list** | The normative, conformance-tested sets of I/O and non-deterministic calls (`IO_WATCH_LIST`, `NONDETERMINISTIC_WATCH_LIST`) that mark impurity. Matched exact / `prefix.*` / `prefix*`. |
| **Constant lookup table vs hidden state** | A module-level dict/list/set that is *never mutated* is an honest dispatch table (exempt). One that is mutated (subscript-assign, mutating method, del, reassignment) is hidden state and is flagged (HC-P004). |
| **Suppression** | `# honest: ignore\|disable\|enable RULE` directives. A suppressed diagnostic is downgraded to `info` (visible, never dropped), so suppressions can't silently accumulate. |
| **Conformance level** | `Core` = all construction-time rules pass; `Full` = all static-analysis rules pass; `Complete` = Full + LSP + framework-startup integration. |

## Tooling

| Term | Definition |
|---|---|
| **tree-sitter** | The *sole* AST mechanism (no Python `ast`, Lark, libcst, or regex-as-parser). One parse boundary (`parse.py`); grammars in a per-language table; rules consume tree-sitter nodes via shared helpers. |
| **`.hd`** | The architecture-declaration layer — an authoring tool for *building* the framework, never imposed on adopters. Its parser/IR/validator is FOSS; the visual producer is commercial. |

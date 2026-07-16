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
| **Fault** | A processing error — data `{code, message, category, detail}`, not an exception. `category` (`client`\|`server`) is required (a fault without one is itself a server error). Exceptions only at the boundary. |
| **Maybe** | Optional binding. A slot declared `maybe()` is always present in the manifest, as a value or as `Nothing`. |
| **classify()** | Runs recognizers over a token list → manifest. Two passes: base classification, then composition + binding resolution. |
| **Link** | A function declared with `@link(accepts=, binds=, boundary=, authorizes=, emits=)`. The decorator attaches metadata (read via `link_meta()`) and leaves the function callable and its behaviour unchanged — it records intent, never scopes the manifest. Pure unless declared a boundary. |
| **Chain** | An ordered list of links; the manifest flows from one to the next. A chain is itself a link (chains compose). `chain(*links)` builds one; `execute_chain(links, manifest)` runs it, short-circuiting on the first `err`. |
| **Result** | The only two shapes a link may return: `ok(manifest)` → `{"ok": manifest}` or `err(fault)` → `{"err": fault}`. A link returning neither is a `non_result_return` server fault. |
| **validate_all** | An accumulating combinator, itself a link: `validate_all(*links)` runs every link against the *same* manifest; any failure yields a `validation_failed` fault carrying every result, `ok` and `err` alike. |
| **Vocabulary merge** | `merge(a, b)` combines two vocabularies, failing at construction on a name collision (a type in both) or a value collision (a Set member shared under different names). No `\|` operator — that would need a dict subclass (HC-P003). |
| **catch_at_boundary** | The boundary wrapper (the one place that catches): renders `ok` as success, routes a fault through a `fault_to_output` table (category default as fallback), and turns an unhandled exception into an `unhandled_exception` server fault. Routing is lookup, never branching. |
| **Rejection policy** | The table that decides, at the boundary, whether a manifest's rejections block (`fault`) or pass with a warning (`warn`). `check_rejections()` applies it; inside the chain there are no rejections. |
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
| **Role** | A function's declared kind — `@link`, `@recognizer`, `@boundary`, `@helper`, or `@orchestrator` — which determines how auto-generation exercises it. Every function must have a role or be reachable from one (HC-R001). |
| **Orchestrator** | The root of a request/operation: it wires input I/O, chain execution, and output I/O. Orchestrators do **not** compose — one may not call another (HC-OR001); shared logic becomes a helper or a chain. |
| **Helper** | A roled-but-internal function, exercised transitively through the roled functions that call it; must be branchless so every reachable path is exhaustively covered. |
| **Orphan** | A function with no role that is not reachable from any roled function — auto-generation cannot reach it, so it has no test story (HC-R001). |

## honest-test (the auto-generated verification layer)

| Term | Definition |
|---|---|
| **honest-test** | The behavioural half of the gate. It runs the suite honest-check confirmed is generatable: every test case is derived from declarations, never hand-written. *Defining is testing.* |
| **Set enumeration** | The full cartesian product of a vocabulary's bounded Set types (section 3.2) — exhaustive, no sampling. A maybe-bound type adds Nothing. `enumerate_sets(vocab, bind)`. |
| **Adversarial neighbours** | For every Set member, the near-miss inputs that must be rejected (section 3.5): edit-distance-1, Unicode confusables, control characters, length extensions, encoding variants. `adversarial_neighbors(value)`. A neighbour that is accepted is a recognizer bug. |
| **Predicate classification** | Reading a predicate's AST to pick a generation strategy (numeric → Fibonacci, length-bounded → enumerate lengths, character-class, external-lookup → supplied-values). |

## honest-alerts (the message-passing layer, Tier 3)

| Term | Definition |
|---|---|
| **honest-alerts** | The actor-model message-passing layer: messages pass between actors, no actor shares state with another. Pure decisions in the middle; delivery, emit, and the reply wait reach the world only through an injected runtime. |
| **Message** | An immutable, typed record (section 3.1). Every field that affects delivery, persistence, or lifecycle is declared at send time; it is the payload of an `alert.sent` event. |
| **ActorRef** | An actor identity `{type, id?, tenant_id?}` (section 2). A null `id` broadcasts to every actor of that type. |
| **Mailbox** | Not a data structure — a projection over honest-observe's event log answering "which messages addressed to me have not yet terminated?" (`mailbox`, section 4). Pure fold over the events. |
| **Termination** | How a message ends: one of `ttl`, `acknowledged`, `event`, `never` (section 3.3), selected through a dispatch table, never a branch. |
| **Routing table / AlertRoute** | The honest-persist records that declare how each message type is delivered (section 5). Table-driven: there is no listener registry. |
| **Supervisor** | The pure decision that matches a message to routes and plans one delivery per channel (`matching_routes`, `delivery_plan`); `supervise` and `execute_deliveries` are the injected-runtime boundaries that write and emit (section 6). |
| **alert_lifecycle** | The message lifecycle as honest-type's pure state machine (section 7); `advance` applies one transition and names the honest-observe event it produces. |
| **send / send_and_wait** | The send API (section 8). `send` is fire-and-forget; `send_and_wait` suspends on native async until a reply arrives or the wait times out, holding no thread. |
| **DOM surface** | A message rendered as a server-rendered HTMX fragment declared by its `dom_surface` (banner, toast, modal, badge, inline; section 9). `render_surface` is pure; the surface selects the renderer through a table. |
| **Injected runtime** | The boundary object carrying the clock, ids, resume token, routing-table read, delivery-queue writes, emit, and reply wait. Injecting it keeps honest-alerts import-free of honest-persist and honest-observe, and lets every boundary be proved against a stand-in. |
| **ALERT_EVENTS** | The complete catalog of `alert.*` events and when each fires (section 10), all flowing through honest-observe under the `alert` aggregate. |

## Tooling

| Term | Definition |
|---|---|
| **tree-sitter** | The *sole* AST mechanism (no Python `ast`, Lark, libcst, or regex-as-parser). One parse boundary (`parse.py`); grammars in a per-language table; rules consume tree-sitter nodes via shared helpers. |
| **`.hd`** | The architecture-declaration layer — an authoring tool for *building* the framework, never imposed on adopters. Reading and viewing it is FOSS (the format spec, the reference reader — parser/IR/validator — and the static renderer that draws the 4-column diagram); authoring it visually is commercial (the interactive design surface). See the framework spec, "What is open and what is commercial." |

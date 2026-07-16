# honest-design: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** July 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-design is the `.hd` architecture-declaration layer: the format in which a module's architecture is stated as data, and the read path that turns that statement into something a machine can check and draw. A `.hd` file declares what a module *is* — its types, its functions and their roles, the chains that orchestrate them, the boundaries where I/O happens, the routes that enter it, and the surfaces it renders — independently of the language the module is implemented in.

The bug category it eliminates is **architectural drift**: the implemented structure silently diverging from the intended structure. Without a declared architecture, the design lives in prose and in people's heads, and nothing detects when the code stops matching it — a function that was meant to be pure quietly does I/O, an orchestrator grows a branch, a role becomes unreachable, and no tool notices because there was never a machine-readable statement of what the architecture was supposed to be. honest-design removes that category the same way honest-type removes untyped-string drift: the architecture becomes a declared artifact, read into an intermediate representation, and honest-check's conformance tier verifies the code against it. The rule is **declared, never inferred** — the architecture is authored, not reverse-engineered from whatever the code happens to do.

`.hd` is authoring and development tooling for *building* the framework and applications on it. It is never a runtime dependency of an adopter's application, and conformance to it is opt-in — an adopter who does not declare `.hd` simply does not get the conformance-tier checks that read it. This is the same posture as any authoring aid: it makes building the framework safer without imposing itself on what the framework builds.

### 1.1 What honest-design defines (FOSS)

Four things, all open under the framework's standard licence tiers:

- **The `.hd` format** — its grammar and its semantics (§3, §2). This specification is the normative definition of the format; any producer of `.hd`, visual or otherwise, conforms to it.
- **The reader** — `source → intermediate representation` (§5). Parses `.hd` through the tree-sitter `.hd` grammar (owned by honest-parse) and folds the parse tree into a normalized, language-agnostic IR (§4).
- **The validator** — the well-formedness and architectural-invariant checks over the IR (§6). What honest-check's conformance tier consumes.
- **The static renderer** — `IR → the 4-column diagram` (§7). A pure function from IR to a deterministic diagram; no interaction.

### 1.2 What honest-design does not define (commercial)

- **The interactive design surface** — the visual editor where an architect draws the diagram and the tool emits `.hd`, enforcing the boundary invariant at composition time. This is the commercial product, protected by its own trademark, its patent on the composition-interaction model, and its certification programme, not by the format (framework spec, "What is open and what is commercial"). Reading and viewing `.hd` is open; authoring it *visually* is the commercial line.
- **The IDE, LSP, MCP surface, and Claude-skill orchestration** built on top of the read path (framework spec, "The Third Pillar"). These consume the FOSS reader and renderer; they are not part of this module.

The split is deliberate and load-bearing: a file format is not meaningfully protectable, and an open format with an open reader is exactly what lets every other tool and AI agent *consume* `.hd`, which is what makes the commercial visual *producer* valuable.

### 1.3 Position in the build order

honest-design builds immediately after honest-parse and before honest-type:

```
parse                     the shared tree-sitter boundary (the one true leaf; hand-checked first)
design    → parse         the .hd layer: grammar, reader, validator, static renderer
type      → (nothing)     the type system — itself declared in .hd
...
```

The reasoning is in §11. In short: honest-design depends only on `parse` (it needs the parser machinery and its own tree-sitter `.hd` grammar), and it is the layer in which every subsequent module — `type` included — declares its architecture, so it precedes them. The `.hd` format and the framework's own `.hd` declarations are the genuine first artifact, hand-authored and hand-checked before the reader exists to automate the check, in the same way honest-parse is "the shared parser, checked by hand first."

### 1.4 Reference implementation

The reference implementation is `python/honest-design/`, with the tree-sitter `.hd` grammar (`tree-sitter-honest-hd`) hosted in honest-parse's grammar table. When this document and the implementation disagree, this document is correct.

---

## 2. The architectural model `.hd` expresses

`.hd` describes one thing: a module laid out in **four columns**, the framework's canonical picture of an honest module.

| Column | Contains | Framework correspondence |
|---|---|---|
| 1. Input boundary | Routes, request intake, classification | the closed input boundary; `classify()` at the edge |
| 2. Orchestrators | Chains — ordered sequences of links | honest-type chains / `execute_chain` |
| 3. Pure functions | Links, dispatch tables, pure transforms | `@link` pure functions; dict-dispatch |
| 4. Output boundary | Templates, persistence writes, event emits | rendered surfaces; persist/observe boundaries |

Every declared function carries a **role** that places it in a column: `boundary` (columns 1 and 4, distinguished by direction of I/O), `orchestrator` (column 2), or `pure` (column 3). The role is not decoration — it is a claim the validator and honest-check enforce: a `pure` function that does I/O is a violation; an `orchestrator` that does I/O off a boundary is a violation; a `boundary` function is the only place a declared side effect may occur.

The model is language-agnostic. The same `.hd` describes the module whether it is implemented in Python, JavaScript, Ruby, PHP, Elixir, or Go; the file is byte-identical across targets (framework spec, "Same engine, same grammar, same files"). What differs per language is only the code an adapter emits into each column, never the columns themselves.

---

## 3. The `.hd` grammar

`.hd` is a declarative, indentation-scoped format. A file declares one module and its parts. The grammar is small by design: each primitive names one architectural concept, and there is exactly one way to say each thing.

### 3.1 Example

```hd
module orders

  type OrderStatus = { "pending", "paid", "shipped", "cancelled" }
  type Email       = predicate(is_email)
  type OrderTokens = composed(Email, quantity: PositiveInt)

  boundary intake
    accepts  request
    produces OrderTokens
    reads    http.request

  pure validate_order
    accepts  OrderTokens
    produces OrderManifest | fault

  pure price_order
    accepts  OrderManifest
    produces PricedOrder

  boundary write_order
    accepts  PricedOrder
    produces OrderRecord
    emits    persist.query, hf.order.created

  chain create_order
    intake -> validate_order -> price_order -> write_order

  route POST "/orders" -> create_order

  transitions OrderStatus
    pending -> paid      on payment_received
    paid    -> shipped   on dispatched
    pending -> cancelled on cancelled

  uses persistence.table(OrderRecord)
```

### 3.2 Declarations

| Keyword | Declares | Notes |
|---|---|---|
| `module` | The module name (one per file). | The unit of editing and of the diagram. |
| `type` | A recognizer vocabulary. | `{ ... }` Set, `predicate(fn)`, `composed(...)`, `maybe(T)`. Mirrors honest-type. |
| `boundary` | A function in column 1 or 4. | Must declare `reads` and/or `emits`; it is the only role that may. |
| `pure` | A function in column 3. | May declare `accepts`/`produces` only; declaring `reads`/`emits` is a violation. |
| `orchestrator` | A chain-runner in column 2. | Rare as an explicit declaration; usually implied by `chain`. |
| `accepts` / `produces` | A function's input and output manifest types. | `produces T \| fault` marks a fallible function. |
| `reads` / `emits` | A boundary function's declared side effects. | Named against the closed vocabulary of framework side effects (`http.*`, `persist.*`, `hf.*` events). |
| `chain` | An ordered orchestration of links. | `a -> b -> c`; each link is a declared function; adjacent types must compose. |
| `dispatch` | A dict-dispatch table. | `key -> handler` rows; the honest replacement for `if/elif`. |
| `route` | An input-boundary binding. | `METHOD "path" -> chain`. |
| `template` | An output-boundary surface. | Names the surface and the references it emits (for HC-REF resolution). |
| `transitions` | A state machine over a type. | `from -> to on event` rows; mirrors honest-type state machines. |
| `schedule` | A scheduled entry point. | Names the cadence and the chain it runs. |
| `uses` | A capability reference into another module. | `uses persistence.table(T)`; resolved to a framework-module surface, never reaching past it. |

### 3.3 Grammar summary (EBNF)

```
file        = module , { declaration } ;
module      = "module" , name ;
declaration = type | function | chain | dispatch | route
            | template | transitions | schedule | uses ;
type        = "type" , name , "=" , type_expr ;
type_expr   = set | "predicate(" , name , ")"
            | "composed(" , field_list , ")" | "maybe(" , name , ")" ;
function    = ( "boundary" | "pure" | "orchestrator" ) , name , { attribute } ;
attribute   = ( "accepts" | "produces" ) , type_ref
            | ( "reads" | "emits" ) , name_list ;
chain       = "chain" , name , link_seq ;
link_seq    = name , { "->" , name } ;
transitions = "transitions" , type_ref , { transition } ;
transition  = name , "->" , name , "on" , name ;
route       = "route" , method , string , "->" , name ;
uses        = "uses" , capability_ref ;
```

Indentation scopes a declaration's attributes to it. A blank line or a dedent ends a declaration. The grammar carries no control flow, no expressions beyond type references, and no imperative statements: `.hd` states structure, it does not compute.

---

## 4. The intermediate representation (IR)

The reader produces a normalized, language-agnostic IR — plain data, the single value every downstream consumer (validator, renderer, honest-check conformance tier) reads. It is not tied to tree-sitter node shapes; the reader folds the parse tree into it so no consumer touches the grammar.

```
Module   = { name, types, functions, chains, dispatches,
             routes, templates, transitions, uses, edges }
Function = { name, role, accepts, produces, reads, emits, column }
Chain    = { name, links }        # links: [function name], in order
Route    = { method, path, chain }
Transition = { from, to, event }
Edge     = { from, to, kind }     # cross-declaration dependency
```

`column` is derived, not authored: `pure → 3`, `orchestrator → 2`, and `boundary → 1` if it only `reads` (intake) or `4` if it `emits` (output). Deriving the column in the reader keeps the diagram and the checks reading the same field, so they cannot disagree about where a function sits. The IR is byte-stable for a given `.hd` file across every language target.

---

## 5. The reader (source → IR)

The reader is pure over the parse tree. Its only I/O is reading the `.hd` file at the boundary; everything after — parse (delegated to honest-parse), walk, fold — is a function of its inputs.

- **Parse** — `honest_parse.parse(source, "hd")`, using the `tree-sitter-honest-hd` grammar hosted in honest-parse's grammar table (§9.1). honest-design never touches tree-sitter directly; it goes through the shared parsing boundary like every other consumer.
- **Fold** — a walk over the tree that accumulates the IR by dict-dispatch on node type, one handler per declaration kind. Adding a primitive is adding a handler row, never branching control flow.
- **Faults as data** — malformed `.hd` (a syntax error node, an unknown keyword, a type reference that names nothing) produces a fault in the shared `Result` shape, never a raised exception. `read_hd(source) → Result[Module]`.

The reader does not resolve cross-module references or check invariants; it produces the IR faithfully and hands it to the validator. Reading and validating are separate so that a syntactically valid but architecturally invalid file still yields an IR to diagnose against.

---

## 6. The validator

The validator is a pure function `Module (IR) → [fault]`. An empty list is a valid architecture. Its checks fall into two groups.

**Well-formedness** — every reference resolves within the file or its declared `uses`:

- Every chain link names a declared function (else `unknown_link`).
- Every `accepts`/`produces` names a declared type or a framework-primitive type (else `unknown_type`).
- Every `transitions` row names states that belong to the referenced type (else `unknown_state`).
- Every `route` names a declared chain (else `unknown_chain`).
- No declaration is orphaned — every function is reachable from a route, a schedule, or a chain (else `unreachable_role`, the declaration-level dual of HC-R001).

**Architectural invariants** — the boundary discipline, checked at the declaration level:

- A `pure` function declares no `reads` and no `emits` (else `impure_pure_function`).
- An `orchestrator`/`chain` performs no I/O of its own — every side effect in a chain lives in a `boundary` link (else `orchestrator_side_effect`).
- Adjacent chain links compose: link *n*'s `produces` matches link *n+1*'s `accepts`, up to a fault short-circuit (else `chain_type_mismatch`, the declaration-level dual of HC002).
- Every `emits`/`reads` names a member of the closed framework side-effect vocabulary (else `unknown_side_effect`).

The validator's faults are the contract honest-check's **conformance tier** consumes: it reads this IR and this fault set to verify that the *code* matches the *declaration* — role reachability, orchestrator discipline, chain type-matching within a module. The universal tier of honest-check needs only `parse` and fires without any `.hd`; the conformance tier is what `.hd` unlocks.

---

## 7. The static renderer (IR → the 4-column diagram)

The renderer is a pure function `Module (IR) → diagram`. Deterministic: the same IR renders the same diagram every time, with no interaction, no layout randomness, and no external state. It places each function in its derived `column`, draws chains as left-to-right edges through the columns, marks boundary functions with their declared side effects, and renders cross-declaration `edges` and `uses` as dependency lines. The output is the framework's canonical 4-column picture — input boundary, orchestrators, pure functions, output boundary — the same view the repository's explorer renders and core contributors reason about (framework spec, "Framework-author view").

The renderer is the *static* half only. It draws a given `.hd`; it does not let anyone draw *into* `.hd`. The interactive surface that produces `.hd` from a drawn diagram is the commercial line (§1.2).

---

## 8. Relationship to other modules

- **honest-parse** hosts the `tree-sitter-honest-hd` grammar as one row in its grammar table, alongside the jinja and css grammars it already owns (§9.1). honest-design reads through `parse`; it is the module's only upstream dependency.
- **honest-check** consumes the reader's IR in its conformance tier to check code-against-declaration. `check` seeds early on `parse` (its universal tier), and its conformance pass lands after `design` exists.
- **honest-type** is itself declared in `.hd`. Its recognizer/chain/state-machine concepts are the vocabulary `.hd`'s `type`/`chain`/`transitions` primitives name; the correspondence is exact so a type declaration and its `.hd` declaration cannot drift.
- The **framework's own modules** are declared in `.hd`; those declarations are the design artifacts every downstream check reads. Authoring them is part of designing each module, spec-first.

---

## 9. Bootstrapping and grammar ownership

### 9.1 The tree-sitter `.hd` grammar

honest-parse owns every grammar the framework parses, so the `.hd` grammar is built and validated there as `tree-sitter-honest-hd` and added as one row to `_LANGUAGES`, following the framework's tree-sitter grammar-build recipe (the same path that produced `tree-sitter-honest-jinja`). Until that grammar exists, honest-design cannot read `.hd`; building it is the first concrete step of this module.

### 9.2 The seed

The `.hd` format and the framework's own `.hd` declarations are hand-authored and hand-checked before the reader automates the check — the direct parallel to honest-parse being "the shared parser, checked by hand first." The order of standing-up is therefore:

1. `parse` exists (tree-sitter boundary).
2. `tree-sitter-honest-hd` grammar added to `parse`.
3. honest-design reader → IR → validator → static renderer built against it.
4. Every subsequent module authored with its `.hd` declaration, checked by honest-check's conformance tier once that tier lands.

---

## 10. Conformance

honest-design is held to the same five gates as every module:

- **honest-check clean** — the reader, validator, and renderer are themselves honest code (dict-dispatch folds, pure functions, I/O only at the file-read boundary).
- **100% line + branch coverage.**
- **A portable value oracle** — `conformance/suite.json`: `.hd` source → expected IR, and IR → expected validator fault set. The same file proves any language implementation of the reader/validator conformant, with no host language in the loop.
- **A generative proof** — `conformance/laws_hd.py`: reader and validator laws across generated `.hd` inputs (round-trip stability of the IR, fault-as-data on every malformed input class, column-derivation totality).
- **Feature bijection** — one gherkin scenario per reader/validator/renderer function point.

---

## 11. The build-order decision

honest-design's placement follows from one dependency fact and one architectural fact.

**The dependency fact.** honest-design depends only on `parse` — it needs the tree-sitter machinery and its own `.hd` grammar, and nothing else. It does *not* depend on `type`. So it cannot precede `parse` (the reader has nothing to parse with), but nothing forces `type` ahead of it.

**The architectural fact.** `.hd` is the layer in which every other module — `type` included — declares its architecture, and honest-check's conformance tier checks each module's code against its `.hd` declaration. For that discipline to be available from the first architecture-bearing module onward, the `.hd` layer must exist before those modules.

Together these place honest-design at **position 2, immediately after `parse` and before `type`** — first among the architecture-bearing modules, second only to the one leaf (`parse`) that the reader itself is built on. It is not literally first: `parse`, the shared tree-sitter boundary, is the single artifact that must exist before anything, honest-design included. But the `.hd` *format* and the framework's own `.hd` declarations — hand-authored, hand-checked — are the genuine first design artifact, preceding every line of module code, exactly as the framework's own architecture precedes its implementation.

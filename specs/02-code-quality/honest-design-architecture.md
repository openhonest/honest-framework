# honest-design: Architecture Specification

**Version:** 0.1 (Draft) **Date:** November 2026 **Status:** Active **Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-design is the `.hd` architecture-declaration layer: the format in which a module's architecture is stated as data, and the “read path” that turns that statement into something a machine can check and draw. A `.hd` file declares what a module *is* — its types, its functions and their roles, the chains that orchestrate them, the boundaries where I/O happens, the routes that enter it, and the surfaces it renders — independently of the language the module is implemented in.

The "read path" is the set of steps that read a `.hd` file and produce two results: a declaration of the module architecture, and a list of any errors that might be present in the declaration. The steps run in one order, and each hands its result to the next.

1. **The parser** takes the `.hd` text and turns it into a tree, the text broken into its parts and nested by structure. Its one job is to find that structure, or to report that the text is malformed. honest-parse owns the grammar it uses.
2. **The reader** walks that tree and builds the intermediate representation, the declaration written as plain data. The data lists the module's functions, keys its types by name, and holds the chains and the boundaries, each piece in a named field. Every later step reads this data, never the raw text.
3. **The validator** reads that data and checks it against the rules. Where a rule is broken it returns a fault, a record that says what is wrong and, where it can, what to do instead. An empty list of faults means the module is clean.
4. **The renderer** reads the same data and draws the diagram: the inputs on the left, the outputs on the right, the orchestrators above, and the pure functions in the middle. It draws from the data, so the picture cannot say anything the declaration does not.

Every one of those four steps only reads a `.hd` file. Nothing in the read path writes one, which is what the name marks. The renderer draws the declaration, so the diagram is a view of the first result, not a third one.

The bug category it eliminates is **architectural drift**: the implemented structure silently diverging from the intended structure. Without a declared architecture, the design lives in prose and in people's heads, and nothing detects when the code stops matching it — a function that was meant to be pure quietly does I/O, an orchestrator grows a branch, a role becomes unreachable, and no tool notices because there was never a machine-readable statement of what the architecture was supposed to be. honest-design removes that category the same way honest-type removes untyped-string drift: the architecture becomes a declared artifact, read into an intermediate representation, and honest-check's conformance tier verifies the code against it. The rule is **declared, never inferred** — the architecture is authored, not reverse-engineered from whatever the code happens to do.

`.hd` is authoring and development tooling for *building* the framework and applications on it. It is never a runtime dependency of an adopter's application, and conformance to it is opt-in — an adopter who does not declare `.hd` simply does not get the conformance-tier checks that read it. This is the same posture as any authoring aid: it makes building the framework safer without imposing itself on what the framework builds.

### 1.1 What honest-design defines

Four things:

- **The `.hd` format** — its grammar and its semantics (§3, §2). This specification is the normative definition of the format; any producer of `.hd` conforms to it.
- **The reader** — `source → intermediate representation` (§5). Parses `.hd` through the tree-sitter `.hd` grammar (owned by honest-parse) and folds the parse tree into a normalized, language-agnostic IR (§4).
- **The validator** — the well-formedness and architectural-invariant checks over the IR (§6). What honest-check's conformance tier consumes.
- **The static renderer** — `IR → the 4-column diagram` (§7). A pure function from IR to a deterministic diagram; no interaction.



### 1.2 Position in the build order

honest-design builds immediately after honest-parse and before honest-type:

```
parse                     the shared tree-sitter boundary (the one true leaf; hand-checked first)
design    → parse         the .hd layer: grammar, reader, validator, static renderer
type      → (nothing)     the type system — itself declared in .hd
...
```

The reasoning is in §11. In short: honest-design depends only on `parse` (it needs the parser machinery and its own tree-sitter `.hd` grammar), and it is the layer in which every subsequent module — `type` included — declares its architecture, so it precedes them. The `.hd` format and the framework's own `.hd` declarations are the genuine first artifact, hand-authored and hand-checked before the reader exists to automate the check, in the same way honest-parse is "the shared parser, checked by hand first."

### 1.3 Reference implementation

The reference implementation is `python/honest-design/`, with the tree-sitter `.hd` grammar (`tree-sitter-honest-hd`) hosted in honest-parse's grammar table. When this document and the implementation disagree, this document is correct.

---

## 2. The architectural model `.hd` expresses

`.hd` describes one thing: a module laid out in **four columns**, the framework's canonical picture of an honest module.

| Column | Contains | Declared as |
|---|---|---|
| 1. Input boundary | Routes, request intake, the reads from the outside world | `boundary_in fn ... side_effect reads "..."` |
| 2. Orchestrators | The chains that compose the pure pipeline and dispatch results | `orchestrator fn ... invokes ...` |
| 3. Pure functions | The grid of pure transforms — recognizers, classifiers, folds | `fn ...` |
| 4. Output boundary | Writes to the outside world — responses, persistence, event emits | `boundary_out fn ... side_effect writes "..."` |

Every declared function carries its column in its **role keyword**: `boundary_in` (column 1), `reader` (column 1), `orchestrator` (column 2), `fn` (column 3), `boundary_out` (column 4), `edge` (column 1). The role is not decoration. It is a claim the validator and honest-check enforce: a pure function that does I/O is a violation, and so is an `orchestrator` that reaches the outside world off a boundary.

Which roles may name a `side_effect` is narrower than "a boundary" and wider than the two doors. The validator states the rule on the pure side and nowhere else: the pure roles are `fn` and `edge`, and a function in either that declares a side effect is `impure_pure_function`. Every other role may name one. A `boundary_in` or `boundary_out` names the side of the world it reads or writes. A `reader` names the side it pulls, which is why it stands in column 1. An `orchestrator` names `store:<name>`, and only an orchestrator may: the store holds what each step returned, and only the thing that runs the steps can keep them (§3.2, `store`). Whether an orchestrator may name any *other* side is not decided per module. §6 says why: the corpus holds orchestrators that legitimately declare one, so that split is left to honest-check's code-level rules.

An `edge` is a pure function a module with boundaries exposes as an import surface: the world reaches it by import, named by an `entry`, it may call into the core, and nothing inside the module invokes it. It keeps every pure discipline — a side effect on it or a handle in its signature is a violation, exactly as for a plain `fn` — and differs from a `fn` only in that the world arrives at it directly. It stands in column 1 with the doors because it is a way in, drawn under its own "imported (pure)" heading. A boundary-less pure library does not need `edge`: its whole surface is already exempt because it has no door for the world to bypass. `edge` is for the hybrid, a module that has real boundaries and also publishes a pure import surface.

**The four columns are the functions. `.hd` also names the data those functions move and the sources they pull it from.** A **type** is a named shape a value must match. It is a record of named fields, a union of alternatives, or a vocabulary, which is a closed set of allowed words (§3). A **data structure** is a record type: the shape of a request, a result, or a row, named once and used by that name wherever it crosses a column, so the file says what passes between the functions and not only that something passes. A **source** is a thing outside the module that a function pulls a value from rather than receiving it as an argument, such as the clock, the schema the database holds, a file, or an environment variable. A reader names the source it pulls from, and the orchestrator that needs the value invokes the reader. So a reader of the file sees the whole architecture: the functions by column, the types and data structures they move, and the sources they pull from.


**Why surfaces are declared and not inferred.** A page's contract is which surfaces it renders and in what order. Until now that could be written in prose and asserted by a conformance law, but not declared. So a module whose whole contract was an ordering had no `.hd` at all, and nobody noticed: the missing file read as unfinished work rather than as a gap in this language. The `surfaces` block closes it. The order is the declaration, honest-check resolves a rendered template's ids against it, and a module that renders surfaces is now describable in the same file as everything else about it.

**The columns are ordered, and the arrows run one way.** Work enters at column 1, is composed in column 2, is computed in column 3, and leaves at column 4. Two consequences follow, and both are claims rather than description.

**An output boundary is a terminus.** A `boundary_out` may call pure functions and other output boundaries. It may not invoke an orchestrator, a chain, or an input boundary. An output that re-enters the interior turns the graph into a loop: the pipeline stops being something that runs once between an arrival and a departure, an emit can trigger work that emits again, and the interior is no longer reachable only from column 1. That last point is what the finite-testability argument rests on, so a backward arrow from column 4 does not merely look untidy, it removes the property the layout exists to show.

**A pure function does not reach a boundary.** Column 3 is downstream of column 2 and upstream of column 4, and it calls neither. A pure function that invokes a boundary has performed I/O at one remove, which is the defect `HC-P004` names when the I/O is written inline and which no rule yet names when it is one call away.

The model is language-agnostic. The same `.hd` describes the module whether it is implemented in Python, JavaScript, Ruby, PHP, Elixir, or Go; the file is byte-identical across targets (framework spec, "Same engine, same grammar, same files"). What differs per language is only the code an adapter emits into each column, never the columns themselves.

---

## 3. The `.hd` grammar

`.hd` is a declarative, indentation-scoped format. A **module file** declares one `module` and its parts, indented beneath it. Two **workspace files** sit above the modules and declare cross-cutting `rule`s and runtime `flow`s (§3.3). `#` begins a line comment. The grammar carries no control flow and no expressions beyond type references: `.hd` states structure, it does not compute.

### 3.1 A module file

```hd
module honest-type

  layer foundation
  note "the type layer: it recognizes tokens, composes vocabularies, and classifies input into a dispatch-ready manifest."

  # Living-spec examples, each bound to a chain.
  example classify_email of classify_pipeline = "classify_token('alice@example.com', vocab); recognizer 'email' matches; resolve_bindings maps 'email' to slot 'user_email'; ticket emitted."

  # Dispatch table: key -> handler.
  dispatch reject_emitters = { "rejection" -> emit_rejection, "fault" -> emit_fault }

  # Types: scalar aliases, generics, and records.
  type Recognizer = Callable<str, bool>
  type Ticket = {
    kind: str
    value: str
    slot: str
  }

  # Bounded recognizer sets (members optionally carry a description),
  # and vocabularies composed from them.
  set format_name = { "currency", "number", "percent", "date", "phone", "duration" }
  set order_state = { "pending" : "Awaiting payment.", "paid" : "Awaiting fulfilment." }
  vocabulary format_vocab = { format_name, currency_code, style_name }

  # Column 1 — input boundary: reads the outside world.
  boundary_in fn extract_http_tokens : (request: Request) -> list<str> side_effect reads "HTTP"

  # Column 2 — orchestrator: runs chains, invokes other declarations, and returns the faults they return.
  orchestrator fn classify_and_dispatch : (tokens: list<str>, vocab: Vocabulary) -> Manifest | Fault invokes classify_pipeline, classify

  # Column 3 — pure function.
  fn classify_token : (token: str, vocab: Vocabulary) -> Ticket

  # Column 4 — output boundary: writes the outside world.
  boundary_out fn emit_manifest : (manifest: Manifest) -> Response side_effect writes "memory"

  # Chain: ordered function composition.
  chain classify_pipeline = classify_token -> resolve_bindings
```

A module may also declare `route "METHOD /path" -> fn` (an input-boundary route binding) and `html_attr "attr" "description"` (a declared client-side attribute, e.g. `hs-event`).

### 3.2 Declaration reference

| Form | Declares |
|---|---|
| `module <name>` | The module — one per file, the unit of editing and of the diagram. |
| `layer <name>` | The module's tier: `foundation`, `correctness`, `tooling`, `domain`, ... |
| `env <NAME> : <type>` | An environment variable the module reads: the name the deployment must supply, and its type. Write the type as a union with `Absent` when the variable may be missing, so the boundary that reads it has to handle that case; a bare type means required. The function that reads it declares `side_effect reads "env:<NAME>"`. |
| `inputs = { "side" : "description", ... }` | Every side of the world the module reads, closed: `HTTP`, `caller`, `clock`, `filesystem`. A door reads a listed side when the world knocks; a reader reads one when the program asks. A side a boundary names that the list does not carry is a fault, so the surface has one source of truth and a wrong boundary cannot be declared. `env:` targets stay outside the list, closed by their own declarations. |
| `outputs = { "side" : "description", ... }` | Every side of the world the module writes, closed, the same way. A `reads_writes` side is in both lists. The DOM appears here once and a `surfaces` block enumerates what sits behind it; `store:` targets stay outside, being the module's own memory. A door exists only if something outside starts the work and the module cannot obtain the value itself; everything else is a reader, or is built where it is needed. |
| `store <name> = <fn> "<why>"` | State the module holds between calls: the answers of the pure function `<fn>`, keyed by its arguments, so what the store is keyed by and what it holds are read from that function's signature and never declared twice. Holding anything else makes staleness possible, so `<fn>` must be a plain `fn`. The string is the reason the store exists, because a cache follows a measurement. The orchestrator that keeps the answers declares `side_effect reads_writes "store:<name>"`; only an orchestrator may, since it is the thing that keeps what each step returned. |
| `type <Name> = <expr>` | A type. `<expr>` is a scalar (`str`, `int`, `bool`, `void`, `any`, `handle`), a generic (`list<T>`, `dict<K,V>`, `set<T>`, `Callable<...>`), or a record (`{ field: type ... }`); a return or field type may be a union (`Manifest \| Fault`). Types from other modules are referenced by name, not redeclared. `handle` is an opaque reference to something outside the process, a driver connection or a file: obtained from a boundary, carried in records, handed back to boundaries, never read. `any` is a type nobody has decided yet; the two used to share a spelling and looked alike. |
| `set <name> = { "a", ... }` | A bounded recognizer set of string literals; each member may be written `"member" : "description"`. |
| `surfaces <name> = [ "id" as <element>, ... ]` | The surfaces a module renders, in the order the page requires. Each member names the `id` it is identified by and the element it lives in. Square brackets, not braces: the order is the contract, and a `set` is unordered. |
| `vocabulary <name> = { set, ... }` | A vocabulary composed of sets (its Cartesian product is the exhaustive test space). |
| `type <Name> = foreign "<source>"` | A type the module does not own. It names the source it comes from and declares no fields, because a module cannot describe someone else's object honestly: the description is a copy, and the copy drifts. tree-sitter's syntax node is the case this exists for. honest-parse wraps tree-sitter and hands the node straight out, and consumers read ten of its members, one a method that takes an argument, so no record of any length is true. A foreign type is exempt from the type-card crossing test by construction, since it names no field anyone may declare. It is not `handle`: a handle is never read, and a foreign value is read by everybody. It names no version. A version does not cross the card; it decides what the card means, and a fact that decides meaning belongs with whatever supplies the artifact, which is the package lockfile. Writing the version in the card is a second copy of what packaging already states, and two copies drift. |
| `dispatch <name> = { "k" -> handler, ... }` | A dict-dispatch table — the honest replacement for `if/elif`. |
| `dispatch <name> = { "k" -> handler from <field>, ... }` | The same, where each entry names the slice of the caller's input its handler is fed. `from` is optional per entry. Without it every handler in a table must declare the same wide input, which hides which field each one actually reads. |
| `example <name> of <chain> = "..."` | A living-spec example bound to a chain. |
| `boundary_in fn <name> : (args) -> ret side_effect reads "<source>" [raises <faults>]` | Column 1. A door: the world calls in here, and nothing inside the module calls it. It invokes the orchestrator that owns the sequence, or heads a chain to it. A door that must stop a server starting raises, and names what it raises. |
| `reader fn <name> : (args) -> ret side_effect reads "<source>"` | Column 1. A read the program initiates, a clock, a file it chose to open, the environment mid-run. An orchestrator invokes it; it invokes nothing and heads no chain. It stands on the input side with the doors because it reads the world and writes nothing, and it differs from a door in who asks. |
| `orchestrator fn <name> : (args) -> ret invokes <list>` | Column 2. Runs chains and names what it invokes. A fault it receives comes back in its return type (`-> Manifest \| Fault`), and it decides whether a boundary raises the fault or an output boundary logs it. |
| `fn <name> : (args) -> ret` | Column 3. A pure function. A fault comes back in its return type, never as a raise. |
| `edge fn <name> : (args) -> ret` | Column 1. A pure function a module with boundaries publishes as an import surface, named by an `entry`. It keeps every pure discipline — the validator treats `fn` and `edge` as the two pure roles, so a side effect on either is `impure_pure_function` and a handle in either signature is `handle_read` — and differs from a `fn` only in that the world reaches it directly rather than through a door. Nothing inside the module invokes it. |
| `boundary_out fn <name> : (args) -> ret side_effect writes "<sink>" [raises <faults>]` | Column 4. Output boundary; declares what it writes, and names what it raises if it throws. |
| `chain <name> = a -> b -> c` | An ordered composition of functions. |
| `route "METHOD /path" -> fn` | An input-boundary route binding. |
| `entry "<callsite>" -> fn` | An entry point whose call-site shape is a string — a decorator, a context manager, a middleware registration — dispatching to a function. |
| `html_attr "attr" "desc"` | A declared client-side attribute. |
| `awaited` | Among a function's annotations: the caller gets a promise of the answer and must await it. The word states the caller's obligation, not the host's mechanism, and a host with blocking calls has no equivalent, which is why it is a word on the card rather than a return type. An awaited callee makes its caller awaited, along the edges a fault travels, out to the door. |
| `note "..."` | The one comment the reader keeps. It sits at module scope to say in one line what the module is for, trails a `type`, `env`, `set`, `vocabulary`, `dispatch` or `chain`, or sits among a function's annotations, and it is drawn on that declaration's card. The module's own note is drawn on the system card and at the head of the module page, so the module is no longer the one declared thing that cannot say what it is. It is optional, the way a note is optional everywhere else. A `#` comment is for the file and never reaches the IR. |

A function signature is `: (name: type, ...) -> ret`. `side_effect reads "X"` / `writes "X"` / `reads_writes "X"` names the source or sink — `HTTP`, `DOM`, `filesystem`, `network`, `localStorage`, `stdout`, `database`, an environment variable by name as `env:<NAME>`, a store by name as `store:<name>`, or another module such as `honest-observe` — and a function may declare more than one. `invokes` lists the chains and functions an orchestrator (or boundary) calls. `raises` lists the codes of the faults a boundary throws, written bare (`no_transition`) or quoted (`"alert.delivery_failed"`). Only a `boundary_in` or `boundary_out` throws, so only one of them carries `raises`; a fault anywhere else comes back in the return type. A dispatch entry may add `from <field>`, naming the slice of the caller's input that entry's handler is fed; the handler then declares that field's type instead of the whole record, so a predicate reading one field of sixteen says so in its signature rather than in a comment. There is exactly one way to say each thing.

### 3.3 Workspace files

Two file kinds sit above the modules and describe the workspace as a whole:

- **Rules** (`rules.hd`) — `rule <ID> = "..."` states a structural check honest-check enforces across every module; `rule <ID> on <module> = "..."` scopes it to one. The short statement is the machine-readable index for the diagram; the full rule and rationale live in the honest-check spec.
- **Flows** (`flows.hd`) — `actor <name>` names a non-module runtime participant (e.g. `browser`, `htmx`, `sse`), rendered as a pill node; `flow <name> in <group> = a -> b -> c` declares a representative module-to-module call order for one runtime scenario, grouped `browser` / `server` / `startup` / `tooling`. A flow is what actually happens at runtime, not a type dependency.

---

## 4. The intermediate representation (IR)

The reader produces a normalized, language-agnostic IR — plain data, the single value every downstream consumer (validator, renderer, honest-check conformance tier) reads. It is not tied to tree-sitter node shapes; the reader folds the parse tree into it so no consumer touches the grammar.

```
Module   = { name, layer, note, envs, stores, inputs, outputs, surface_declared, types, sets, vocabularies, dispatches,
             surfaces, functions, chains, examples, routes, entries, html_attrs }
             # surfaces: [ { name, members } ], members [ { id, element } ] in declared order,
             #   because that order is the contract. Distinct from `surface_declared`, the boolean
             #   saying whether the module closed its world with an inputs/outputs block.
Env      = { name, type }         # type: a union with Absent when the variable may be missing
Store    = { name, fn, why }      # fn: the pure function whose answers are held, by its arguments
Function = { name, role, params, ret, side_effects, invokes, raises, column, note, awaited }
             # note: the declaration's note, "" when it has none; also on Module, TypeDecl, Env, SetDecl, Vocabulary, Dispatch, Chain
             # awaited: false when the word is absent. Absence alone cannot tell a function nobody awaits from one whose author had no word for it, so honest-check HC-R003 verifies it against the code: an async def declared without the word, or the word on a plain def, is a fault. The default is verified, not assumed.
             # role: "boundary_in" | "reader" | "orchestrator" | "fn" | "boundary_out" | "edge"
             # params: [ { name, type } ] ; ret: type (possibly a union)
             # side_effects: [ { direction: "reads"|"writes"|"reads_writes", target } ]
             # invokes, raises: [ name ]
Chain    = { name, links }        # links: [function name], in order
Route    = { method, path, fn }
Example  = { name, chain, text }
```

Two workspace files fold into their own IR: `Rule = { id, module, statement }` (module is null for a global rule) and `Flow = { name, group, steps }` with `Actor = { name }` for the non-module participants.

`column` is derived from the role keyword, not authored: `boundary_in → 1`, `reader → 1`, `orchestrator → 2`, `fn → 3`, `boundary_out → 4`, `edge → 1`. Deriving it in the reader keeps the diagram and the checks reading one field, so they cannot disagree about where a function sits. The IR is byte-stable for a given `.hd` file across every language target.

---

## 5. The reader (source → IR)

The reader is pure over the parse tree. Its only I/O is reading the `.hd` file at the boundary; everything after — parse (delegated to honest-parse), walk, fold — is a function of its inputs.

- **Parse** — `honest_parse.parse(source, "hd")`, using the `tree-sitter-honest-hd` grammar hosted in honest-parse's grammar table (§9.1). honest-design never touches tree-sitter directly; it goes through the shared parsing boundary like every other consumer.
- **Fold** — a walk over the tree that accumulates the IR by dict-dispatch on node type, one handler per declaration kind. Adding a primitive is adding a handler row, never branching control flow.
- **Faults as data** — malformed `.hd` (a syntax error node, an unknown keyword, a type reference that names nothing) produces a fault in the shared `Result` shape, never a raised exception. `read_hd(source) → Result[Module]`.

The reader does not resolve cross-module references or check invariants; it produces the IR faithfully and hands it to the validator. Reading and validating are separate so that a syntactically valid but architecturally invalid file still yields an IR to diagnose against.

---

## 6. The validator

The validator is a pure function `Module (IR) → [fault]`. An empty list is a valid module. The per-module pass decides everything checkable from one module's IR, and is verified to raise nothing on the real `.hd` corpus — the declaration-level duals of the `rules.hd` structural rules:

- Every chain link names a declared function (else `unknown_link`; dual of HC001).
- Every `route` and `entry` targets a declared function (else `unknown_target`; the input-boundary dual of HC001).
- Names are unique within each declaration kind — functions, types, sets, chains, vocabularies, envs (else `duplicate_name`; duals of HC004/HC005/HC006).
- A fault bubbles up through returns. Along every call whose answer comes back, an `invokes`, each handler of an invoked dispatch table, each link of a chain to the next, a callee whose return names `Fault` makes its caller's return name `Fault` too (else `fault_swallowed`). Never a log line, never a flag on something shared. A caller invoking a table inherits every handler's answer, because it cannot know which ran.
- A module declares one `layer`, from a closed set: `foundation`, `correctness`, `data`, `domain`, `application`, `ui`, `tooling`. The word was free text and nothing read it, so values ran by convention and one more was always one keystroke away. It is a vocabulary because things are measured against it: whether a module's seams run the way a layered system's seams run, and whether a module in the domain layer holds a wider spread of the world than a module at that level should. `correctness` sits below `foundation`: the pure substrate is `foundation`, and the checker, the test harness, the declaration layer, the BDD engine, and the error-policy leaf that keep it honest are `correctness`. A measure keyed on a word anyone may coin measures nothing, so the validator faults a layer the set does not carry (`unknown_layer`). The order in which the set is written is the order of the stack. A renderer of the system view places the bands in that order, top to bottom, so the format owns the order and a second renderer cannot draw a different stack from the same files.
- A side string names one thing outside the module, and it may be qualified two ways that do not mean the same. The colon decides first. A **colon** names a kind, and everything after the first colon is a free name: `env:DATABASE_URL` is an environment variable, `store:cache` is the module's own held state, `file:design/data` is a path, `HTTP:studio.local` is a host. The name is free text, so a dot, a slash, or a further colon inside it is part of the name and splits nothing. A **dot**, in a target that carries no colon, names a seam: `reads "honest-parse.parse_source"` says which door of that module this side enters, and the reader splits it into `module` and `door`. The colon, not the number of dots, tells a named side from a seam, because the count of dots in a host name or a file name is not a fact about the format. The reader leaves `module` and `door` each `""` for every colon target, and for a dotless target, and for a target with more than one dot, because a field that answers `""` in one place and `null` in another makes every caller check twice.
- A few words below carry a precise sense, so they are defined here before the passage uses them. A **side** is a thing outside the module that the module reads or writes. The bullet above calls it a side string. A **kind** is one of the names the format allows for a side, the word before the colon. The **world** is every side a module touches, taken together. A **door** is a function another module may call into, a `boundary_in`. A **seam** is a declared call from one module into another module's door. A side is **ambient** when every module may touch it without meeting another module there, as with the clock. The **families** below group the kinds for reading, and a module writes a kind, never a family.
- The sides of the world are a closed set of kinds, closed the way the layer list above is closed. Adam ruled this on 22 October 2026, as honest-framework-j15. The reason was a measure that reads coupling off the sides and answered by spelling rather than by meaning. A kind may carry a colon and a free name: `clock`, `file:design/data`, `HTTP:studio.local`. The colon is the convention `env:DATABASE_URL` and `store:cache` already follow, now applied to every side. Two rules make the set usable. A module writes the kind and never the family it sits in. One place named at two heights, `file:design/data` by one module and `persistence:design/data` by another, would miss its own match and hide the pair the coupling question exists to find. A kind that takes a name must carry one. `HTTP` and `database` both require it, so a module writes `HTTP:studio.local` and `database:mockument`. Two modules touching one database then read as touching the same database, rather than as both touching a database. A kind whose name does not exist at declaration carries the reserved name `given`: `database:given`, `HTTP:given`. The module learns the name at run time, from an argument, a connection, an injection or the deployment. `given` says the name is unknowable at declaration, rather than leaving the kind bare. One `given` never matches another, because two modules each handed a database cannot be shown to hold the same one. So `given` raises no coupling question (Adam, 22 October 2026). The test is the name, not the module. A module handed its connection writes `database:given`; a tool handed a path on the command line writes `file:given`; a server that learns its host from a deployment it does not hold writes `HTTP:given`. A module whose name is fixed at declaration writes that name, because the name exists, so a module with a known database may not write `database:given`. Two modules writing `database:given` to dodge a database they each know would hide the one coupling between them and let the rule report a clean sheet, which is the gate passed by declaring less that HC-REF009 exists to refuse.
  - A module writes only the kind, and the rendered system view shows the full family path, so a reader sees the whole address of a side rather than the one word the author typed. `file:design/data` shows as `OS, persistence / file / design/data`. Adam set this condition on 22 October 2026: a module writes the kind on condition that the page shows its family. The families live as one exported mapping from each kind to the families that hold it, `KIND_FAMILIES` in honest-design's validator, next to `LAYERS`. The renderer reads it home the way it reads `LAYERS`, so the page and the gate read one structure and cannot disagree. The prose below is the same mapping in human form. **OS:** clock, random, signal, env, process, file. **console:** stdin, stdout, stderr, argv, exit. **persistence:** database, cache, index, file. **network:** HTTP, socket, DNS, mail. A session and a server-sent stream are not kinds: each is an HTTP conversation between two named hosts, so both write `HTTP:<host>`. A bare `sessions` kind would be ambient under the test below and would hide the coupling the question exists to find. **API:** a service another party runs, named after the colon, `API:stripe`. **messages:** a queue or a log another process reads, named after the colon, `messages:inbox`. **browser:** DOM, localStorage, sessionStorage, cookies, history, clipboard. **device:** camera, microphone, screen, location, serial. **identity:** keychain, secrets, token, kept apart from env because a secret manager is a service a module calls and an environment variable is handed to the module at launch. A runtime is not in this set. A host that owns the main loop and calls into the module is a caller, not a side the module pulls or pushes, so it is named on an `entry` or a `route` and never in a `side_effect`, by the direction-of-initiation rule below. One sentence settles every future case: a runtime calls the module, and everything else here the module calls. `file` sits under both OS and persistence on purpose, because a config file read at startup and a data directory written as a store are two uses of one mechanism. The mapping therefore runs one kind to many families rather than one to one, and splitting `file` into two kinds would let two architects name one path two ways.
  - Ambient is now a property of the side, not a second list to keep. A bare kind is ambient and couples nobody: every module may read `clock` or write `stdout` without meeting another module there. A kind carrying a name is never ambient, so one module writing `file:design/data` and another reading it name the same place, and honest-check surfaces the pair as a question (`HC-REF009`). The set lives in the format, not in a checker or a renderer, for the reason the layer list does: a second copy drifts from the gate. The validator faults a side whose kind the set does not carry (`unknown_side_kind`), the dual of `unknown_layer`.
  - Three names leave the set. `caller` is dropped, because it splits three ways a module can already draw: a caller in view is a seam the caller declares, a caller that owns the loop is a `runtime`, and a caller that is the world is a named side such as `HTTP:<host>`. `tree-sitter`, and any in-process library, is dropped, because a library is reached by import and touches no side of the world. `HTMX` is dropped as a side, because a host that calls in is not a side the module touches. A `boundary_in` reached by `entry "htmx:afterSwap"` already says the HTMX runtime calls in, and the runtime is named on that entry, not in a `side_effect`.
  - The direction of initiation decides where a thing is written, and the picture shows it. The module reaches out to a side it pulls or pushes: a `reader` pulls a clock, a file, or the queue, and a `boundary_out` pushes the network or stdout. A host reaches in: a runtime or server calls one of the module's functions to start the work, which is an `entry` or a `route`. So a `side_effect` names only a side the module pulls or pushes, a runtime is named on an entry or a route, and a runtime named in a `side_effect` is an unknown side kind the validator refuses once j15 enforcement lands. The renderer draws the two in opposite directions, which Adam ruled on 23 October 2026: a caller is an arrow pointing into the module from a host node outside it, and a pulled or pushed side is the module reaching out to an edge card. The arrowhead is the difference a reader sees, so a door the world calls and a reader the module drives no longer read as the same thing on the input edge.
  - The set was settled against the studio and mockument trees. Applied to the framework's own library modules it met three cases Adam ruled on 22 October 2026 and one he left open, recorded in honest-framework-j15. honest-persist writes `database:given` and honest-page reads `HTTP:given`, because each learns the name at run time. honest-alerts is not a vocabulary case: Adam ruled on 23 October 2026 (honest-framework-6un) that it owns its boundaries rather than reaching the world through an injected `runtime` object, so it declares the sides it actually touches, the clock and a random source, the honest-persist queue, the honest-observe log, and the network channel, each on its own boundary. The one `runtime` object that bundled those, here and in honest-observe's `emit`, is gone, because a module that does its I/O through an injected object hides every side behind one `any` and a side is declared where it is touched. The open case was `honest-parse`, which read `caller` on `parse_source` and `tree-sitter` on `parse`, and Adam resolved it on 22 October 2026. Both words leave: `caller` is dropped from the set and `tree-sitter` is an in-process library reached by import. Once they go, `parse_source` reads nothing and `parse` reads nothing, so neither is a boundary and the validator says so (`boundary_without_surface` twice). The resolution is that the two functions take honest pure roles rather than sides they do not touch, and honest-parse becomes a pure library with no boundaries. It stays a module, because honest-design, honest-check and honest-test each import it, so the question that asks a no-side module whether it should fold into its one caller (HC-REF010) does not fire on three callers. Each of those three owes a seam naming `honest-parse.parse_source`, which the map draws today as three red dashed arcs.
- A declaration never crosses a module boundary, so the seam is checked where both sides are in view. The caller names the callee's door; the callee never names its callers, which is what lets a library be used by code it has never heard of. `validate` sees one module and reports nothing here. Resolving the named door against the named module is `honest-check`'s, as a reference that resolves or does not, like every other `HC-REF` rule. Two findings, because they call for different repairs: a door the named module does not declare, and a name that module does declare and that is not a `boundary_in`. The second is the world reaching a module's pure core with no door in between.
- **A caller's declaration stops at the door, and the seam is the boundary of responsibility.** A side naming another module, or one of its doors, means exactly this: this function calls there. It does not mean the caller has taken on what happens past the door. What happens there is the callee's declaration and the callee answers for it; the caller answers for having made the call and for what it does with the result. So nothing accumulates across a seam. A caller's surface lists that module as a side of its world and stops, and there is no sum of writes reached through a chain, because no party owns such a sum and nobody can be held to a number nobody owns. A reader may of course trace a path across seams and find it useful; the trace is information and not an obligation on the caller. Ruled 6 October 2026, against a proposal to budget the I/O a chain reaches and flag growth on the far side of a door. A reach count is the information half of that proposal kept and the obligation half dropped: `reach` answers, for each door, which sides of the world its path touches directly and which it touches through a seam. It is asked and it answers. It returns no verdict, it is in no gate, it compares nothing against a previous run, and no threshold exists for it to breach. It also states what it could not see, because a count over declared seams is a count of what has been written down: every answer carries the number of seams it could not follow, so a small number is never read as a small reach. A side naming a module and no door is a seam at module granularity, not a side of the world with a module's name: the door is what a side may add, never what it must, and the surface has listed modules since before the dot existed. `reach` follows such a seam into every door of that module and counts it apart, because an answer gathered from every entrance is wider than one gathered from the entrance actually used, and a reader must be able to see that the width came from the declaration rather than from the code. A bare name is recognised as a seam only where a declaration of that name is in hand, because nothing in the format tells a module's name from a side of the world's, and with nothing in hand the honest answer is that the path touches something of that name. A side carrying a door is a seam either way. That difference is the argument for the dot a reader can act on: it says what the name is, and not only what it is called.
- A boundary discharges the last fault by raising it. The chain carries faults as data and the boundary is the one place an exception is permitted, which the framework spec states in four places: faults travel as data through chains, exceptions only at the boundary. So a `boundary_in` or `boundary_out` whose `raises` clause names what it throws has answered for its callee's fault, and `fault_swallowed` is satisfied. A caller inside the chain, a pure function or an orchestrator, is not: it returns the fault or it has swallowed it, and no `raises` clause excuses that. Some failures cannot be carried by a return at all, because a caller is free to ignore a returned value: a door that must stop a server starting has to raise, and a server that boots on an ignored return serves requests against nothing.
- A fault is never cryptic: it tells the programmer what went wrong and what to do instead. The words cannot be checked; the shape can. A module whose functions can fault and that declares `Fault` declares it as a record with at least two fields to say so in (else `fault_shape`).
- An awaited callee makes its caller awaited, along the edges a fault travels: an `invokes`, each handler of an invoked dispatch table, each chain link to the next, out to the door (else `unawaited_caller`). A pure `fn` may carry the word: it then awaits what it is handed, as honest-type's `execute_chain_async` awaits its links, and waiting touches nothing in the world, so the word says nothing about purity. Whether the root, the function that touches the driver, is marked at all is not decidable from the declaration; honest-check HC-R003 decides it from the code.
- No function in a pure role, `fn` or `edge`, names `handle` or an alias of it in its own signature (else `handle_read`). Carrying a handle inside a record it takes is holding, and is allowed; naming the handle itself is reading, and a handle is held and passed to a boundary, never read. The rule reads the pure roles only, so an `orchestrator` may name a handle and may bundle two of them into a record, which is how a module holds a driver connection and its settings together without a pure function ever opening either.
- The surface is closed. A module with boundaries and no `inputs` or `outputs` block has an open surface (`surface_undeclared`, one fault for the module); an empty block, `inputs = { }`, closes it, and silence does not. Once it declares either, every side a boundary reads is in `inputs` and every side it writes is in `outputs`, a `reads_writes` side in both (else `surface_unknown`); and once it has a boundary, a listed side no boundary touches is stale (`surface_unused`). A door or reader that reads nothing, or a `boundary_out` that writes nothing, is not a boundary (`boundary_without_surface`); a boundary that only reads is a reader. A door does not take a parameter whose declared type a reader in the module returns (`door_takes_readable`), because the module can read that value for itself.
- A `store` holds the answers of a plain `fn` (else `store_of_impure`); every `side_effect` naming `store:<name>` names a declared store (else `unknown_store`); and only an orchestrator reaches one (else `store_not_orchestrator`; a pure fn reaching one is already `impure_pure_function`).
- Nothing inside the module calls a door: no `invokes` names a `boundary_in` and none is a chain link after the first (else `door_called`). A `reader` invokes nothing and heads no chain (else `reader_calls`).
- Every `side_effect reads "env:<NAME>"` names a declared `env` (else `unknown_env`; the configuration dual of `unknown_link`). A read nobody declared is configuration the deployment must supply that the file does not admit to.
- A function in a pure role, `fn` or `edge`, declares no `side_effect` (else `impure_pure_function`). A `boundary_in`, `boundary_out` or `reader` names the side of the world it touches, and an `orchestrator` names `store:<name>`. This rule is written on the pure roles alone, so it is the one place the per-module pass decides who may touch the world; what else an orchestrator may name is left to honest-check, for the reason given below.
- Every door hands its input to exactly one orchestrator (else `door_orchestrator`). A door that reaches none has taken input nobody acts on; a door that reaches two has broken the one-orchestrator-to-many-inputs shape. A door heading a chain to an orchestrator satisfies it, since the chain is the hand-off written another way. This is the rule a boundary-less pure library cannot satisfy and does not have to: with no door declared, nothing is asked to hand anything on, which is why a library publishes its surface with `edge` and `entry` instead.
- Every function carries a `note` (else `missing_note`). The domain description is written once, while the author still holds the context, and every downstream tool reads it rather than re-deriving or guessing it; it is not recoverable later. Only emptiness is checked, never the words, so this is a gate against silence and not against a bad sentence.
- The two public entry points check their own input, because both are boundaries and the caller's type is not something the module may assume. `read_hd` refuses a non-text source (`hd_source_not_text`) rather than failing inside the parse, and `validate` names a document handed over in place of one module (`not_a_module`) rather than raising from whichever check reads a field first. `hd_syntax_error` is the third code the reader emits, for source that parses to an error node.
- Every surface id in a `surfaces` block is unique within it (else `duplicate_surface`), and the block declares at least one (else `empty_surfaces`). Order is not checked here, because the declaration *is* the order. Whether a rendered page matches it is a cross-artifact question, and honest-check answers it by resolving the template's ids against this block, as `HC-REF001` resolves an action target against a mounted route.

- A dispatch entry's `from` names a real field of its caller's input (else `unknown_projection`), and its handler takes exactly one parameter of that field's type (else `projection_mismatch`). The caller is found through `invokes`. Without both checks the projection is a comment, and a signature that overstates what it reads is the defect the notation exists to catch.

Three further checks are deliberately **not** in the per-module pass, each for a stated reason:

- **`unknown_type` and cross-module references** — a type, an `invokes` target, or a `raises` code may resolve in a *sibling* module, so deciding it needs the whole workspace; it belongs to a document-level pass, not one module's IR.
- **`unreachable_role`** — reachability spans dispatch handlers, boundary and orchestrator roots, cross-module invokes, and pure-helper call chains the `.hd` does not name; a per-module check produces false positives on the real corpus, so this stays with honest-check's code-level HC-R001.
- **chain type-flow and the orchestrator/boundary I/O split** — adjacent links routinely change shape (a `list<T>`-producing link feeding a `T`-consuming link is the valid per-element pattern), and the corpus has orchestrators that legitimately declare a `side_effect`; both need semantics beyond a name-level match, so they are left to honest-check's code-level rules rather than asserted here as stated first drafts that the corpus disproves.

The validator's faults are the contract honest-check's **conformance tier** consumes: it reads this IR and this fault set to verify that the *code* matches the *declaration*. The universal tier of honest-check needs only `parse` and fires without any `.hd`; the conformance tier is what `.hd` unlocks.

---

## 7. The static renderer (IR → the 4-column diagram)

`render(module)` is a pure function `Module (IR) → Diagram`. Deterministic: the same IR renders the same diagram every time, with no interaction, no layout randomness, and no external state. It places each function in its derived `column`, marks boundary functions with their declared `side_effect` targets, and draws each chain as directed edges between adjacent links. The `Diagram` is structured data — four columns of placed nodes plus the chain edges — the framework's canonical 4-column picture (input boundary, orchestrators, pure functions, output boundary), the same view the repository's explorer renders and core contributors reason about (framework spec, "Framework-author view"). Serializing a `Diagram` to SVG for display, and overlaying the workspace `flows.hd` as module-to-module runtime lines through the `actor` and module nodes, are thin presentation steps on top of this structured output.

The renderer is the *static* half only. It draws a given `.hd`; it does not let anyone draw *into* `.hd`.

---

## 8. Relationship to other modules

- **honest-parse** hosts the `tree-sitter-honest-hd` grammar as one row in its grammar table, alongside the jinja and css grammars it already owns (§9.1). honest-design reads through `parse`; it is the module's only upstream dependency.
- **honest-check** consumes the reader's IR in its conformance tier to check code-against-declaration. `check` seeds early on `parse` (its universal tier), and its conformance pass lands after `design` exists.
- **honest-type** is itself declared in `.hd`. Its recognizer, vocabulary, and chain concepts are exactly the `set`/`vocabulary`/`type`/`fn`/`chain` primitives; a state machine is expressed as a `type` record plus its transition functions (as honest-state's `.hd` does), not a dedicated primitive. The correspondence is exact, so a module and its `.hd` declaration cannot drift.
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
- **Feature coverage** — at least one gherkin scenario per reader/validator/renderer function, more where it branches.

---

## 11. The build-order decision

honest-design's placement follows from one dependency fact and one architectural fact.

**The dependency fact.** honest-design depends only on `parse` — it needs the tree-sitter machinery and its own `.hd` grammar, and nothing else. It does *not* depend on `type`. So it cannot precede `parse` (the reader has nothing to parse with), but nothing forces `type` ahead of it.

**The architectural fact.** `.hd` is the layer in which every other module — `type` included — declares its architecture, and honest-check's conformance tier checks each module's code against its `.hd` declaration. For that discipline to be available from the first architecture-bearing module onward, the `.hd` layer must exist before those modules.

Together these place honest-design at **position 2, immediately after `parse` and before `type`** — first among the architecture-bearing modules, second only to the one leaf (`parse`) that the reader itself is built on. It is not literally first: `parse`, the shared tree-sitter boundary, is the single artifact that must exist before anything, honest-design included. But the `.hd` *format* and the framework's own `.hd` declarations — hand-authored, hand-checked — are the genuine first design artifact, preceding every line of module code, exactly as the framework's own architecture precedes its implementation.

# honest-state: Architecture Specification

**Date:** June 2026 **Status:** Active **Author:** Adam Zachary Wasserman

---

honest-state is a small module. It does one thing: it states the law that governs every kind of state in the framework, and it names the single mutator and the home module for each kind. The mechanics of each kind live in that home module — honest-state does not re-describe them. What has no other home, and is the reason honest-state exists, is the law itself and the checks that enforce it.

## 1. There Is No "The State"

Two ground truths govern everything.

**1. There is no such thing as "the state."** There are many *kinds* of state, and each kind deserves its own treatment, store, and handling. The DOM is the store for *individual user* state — one kind among many, not "the" store. Login/session state that must be visible to every instance in a horizontally-scaled deployment lives in a shared store. Persisted domain state lives in the database. Conflating these — the mistake every general-purpose "state manager" makes — is the disease.

**2. Freely changeable state is the enemy.** When anything can change state from anywhere, the number of states the program can reach explodes beyond what anyone can follow, and that is exactly what makes software impossible to check — the very thing this framework exists to defeat. Hence the law:

> **Every declared piece of state has exactly one mutator** — one piece of code allowed to change it.

One mutator means one place to look; the set of changes stays small; small is what makes checking every case possible. This is not a rule bolted on — it is the spine that the ordinary boundary write (stored state), the DOM-as-single-store (user state), HC-P016 (closures), and the HC-P004 global-read clause (module state) are each a part of.

### 1.1 The single-mutator law, precisely

The unit of ownership is the **declared piece of state**, not the physical store. A *declaration* (e.g. the DATAOS manifest) carves a store into owned regions — which is what lets more than one writer touch the same physical store without contention.

A second mutator of a store is legitimate **if and only if** it is:

- **honest** — it does not *hide* the state it mutates, and
- **disjoint** — it does not *touch* any state another mutator already owns.

Two honest, disjoint mutators of one store are not a synchronization problem; they never write the same declared state. Two mutators of the *same* declared state always are. And "shared across N instances" never means "N mutators": a shared store with a single authoritative writer keeps the law intact under horizontal scaling — **share the store, keep the writer singular.**

### 1.2 The taxonomy of state kinds

Every piece of state belongs to exactly one kind, and every kind names exactly one mutator:

| Kind of state | Lives in | Single mutator |
|---|---|---|
| Individual user state | manifest-declared regions of the DOM | the user (any user-initiated action) |
| Server (SSE) state | non-declared regions of the DOM (alerts/notifications) | the server / alert source (honest-alerts) |
| Shared session / login | a shared store (scale-out) | the auth provider |
| Persisted domain state | the database | an ordinary boundary write (honest-persist insert/update/delete at the I/O boundary) |
| Cache | at / preferably across an I/O boundary | refresh-from-source (only write) |
| Transient request state | the chain (the manifest), in-memory | a link's return value (functional threading) |
| Static config | process memory, frozen at startup | startup (then read-only) |
| Dynamic config (flags, A/B) | an external flag store | the flag service (app only reads) |
| Contended writes (db write / mutex / flag) | on the other side of a queue | the queue's single consumer |

The acceptance test for a row: **can you name exactly one mutator?** If a candidate kind seems to need two, it is really two kinds — or one is a derived view, not state. (That test is how static and dynamic config separated, and how the non-declared DOM resolved to a side effect rather than state.)

### 1.3 The DOM, fully decomposed

"The DOM is the state store" is imprecise; this is the exact statement. The DOM is not state — *part* of it is:

- **manifest-declared regions** are **user state**; the single mutator is the user. A server round-trip (HTMX swap) and an in-browser JS change are two *mechanisms* of that one mutator, not two mutators.
- **server/SSE-driven regions** are **server state** (honest-alerts); the single mutator is the server/alert source — a legitimate *second* mutator of the DOM because it is honest (non-hiding) and disjoint (it never touches a manifest slot).
- **everything else** is a **side effect** — a derived projection of the two above, with no mutator of its own. It is re-derived, never written (the cache pattern).

So every part of the DOM is either declared state with exactly one mutator, or a pure projection of state. No hidden, unowned, indiscriminately-mutable corner remains.

---

## 2. Where Each Kind Lives

honest-state names each kind's home; the mechanics live there. Two of these homes are **canonical and normative for every language and framework** — they are patterns, not Python or HTMX details:

- **User / on-screen state → DATAOS, in honest-DOM.** The DOM is the store; the user is the single mutator; the state is the manifest-declared subset. The manifest, and the read/apply/observe primitives that operate on it, are specified in `honest-DOM-architecture.md`. DATAOS is the canonical model for user state across all implementations.
- **Domain state → a honest-type state machine.** A piece of domain state that moves through named conditions (an order: pending → paid → shipped) is a `state_machine` in honest-type; its single mutator is `transition()`, a pure function from (state, event) to the next state or a fault. The machine, its data shape, and its transition semantics are specified in `honest-type-architecture.md` §9. The honest-type state machine is the canonical model for domain-state transitions across all implementations. The *stored value* of that state lives in the database and is written by an ordinary honest-persist boundary write.
- **Server (SSE) state → honest-alerts.** The alert source is the single mutator; it writes only non-declared DOM regions (see §1.3).
- **Shared session / login state → a shared store** visible to all instances, with one authoritative writer (the auth provider; see `honest-auth-architecture.md`).
- **Persisted domain value, cache, transient request state, config, contended writes** → as the taxonomy (§1.2) names them; each is written only by its single mutator, in its home module.

honest-state itself defines no primitives. If you are looking for `collect`/`apply`/`observe`, they are honest-DOM; if you are looking for `state_machine`/`transition`, they are honest-type.

---

## 3. honest-check Integration — enforcing one mutator

The single-mutator law is not asserted and hoped for; it is enforced by honest-check rules, each covering one way a second mutator could appear:

| Rule | What it stops |
|---|---|
| HC-P004 (global-read clause) | module-level mutable state read inside a non-boundary function — hidden process-wide state with no declared mutator |
| HC-P016 | a closure that mutates a captured variable via `nonlocal` — hidden state carried across calls |
| HC-ST001 (boundary-write) | a write to persisted state anywhere but an I/O-boundary function; honest-persist is itself the boundary layer and is not policed |
| HC-ST002 (DOM-as-single-store) | a shadow copy of user state outside the manifest-declared DOM |

State machines are honest-type vocabularies, so the HC-SM rules apply to every honest-type `state_machine`:

| Rule | Description |
|---|---|
| HC-SM01 | State referenced in the transition table not in the states vocabulary |
| HC-SM02 | Event referenced in the transition table not in the events vocabulary |
| HC-SM03 | State is unreachable (no transition leads to it and it is not initial) |
| HC-SM04 | Non-terminal state has no outgoing transitions (dead state) |
| HC-SM05 | Initial state not in the states vocabulary |

Because states and events are honest-type vocabularies, these checks reuse the Set-intersection and reachability algorithms in `honest-check-architecture.md`. No new machinery is required.

**The DOM-as-single-store rule is a static check, not a runtime one — do not conclude otherwise.** It is natural to think "a tool can't know which data is *user state* without running the app." That is wrong. User state is declared in the templates: the DATAOS manifest and the elements its selectors point at say exactly which parts of the page hold user state and how each is read. Code generation from the templates is deterministic, so nothing about user state is discovered at runtime — it is fixed by the templates and knowable before the code runs. honest-check reads the templates through the shared parser (the same one it uses for Python and JavaScript), takes the declared user-state keys from the manifest, and flags any second copy kept elsewhere. If you find yourself deferring this rule as "runtime-only," re-read this paragraph: **it is in the templates, and generation is deterministic.**

### 3.1 HC-ST001 detection, precisely

HC-ST001 fires on one shape: a call that writes persisted state, sitting inside a function that is not a boundary. The rule reuses the boundary machinery HC-P004 already uses, so the two questions it answers are the same two HC-P004 answers, with one substitution.

**Which call writes persisted state.** honest-persist owns every write to the database, and it declares its writers: the functions whose declaration carries `side_effect writes "database"`. Today those are `transaction` (a list of queries committed as one unit) and `apply` (a schema migration). A call writes persisted state when its name resolves, through the file's own imports from `honest_persist`, to one of those declared writers. The three import shapes all resolve: `import honest_persist` then `honest_persist.transaction(...)`; `from honest_persist import transaction` then `transaction(...)`; and `from honest_persist import transaction as tx` then `tx(...)`. A bare `transaction` that no `honest_persist` import binds is a different function and does not fire. The writer set is honest-persist's declaration, not a guess: when honest-persist declares a new writer, that writer joins the set. `insert`, `update` and `delete` are not writers — they build a `Query` value and touch nothing, so a call to one of them never fires, wherever it sits.

**Which function is a boundary.** The same test as HC-P004: a function carrying `@boundary` or `@link(boundary=True)` is a boundary, and on the error path the module's `.hd` is consulted — a function the `.hd` marks `boundary_in`, `boundary_out` or `reader` is a boundary too, and the finding is dropped. A write inside such a function is the legitimate boundary write the taxonomy names; a write inside an interior function is the violation. A write at module scope, inside no function, does not fire, exactly as a module-scope I/O call does not fire HC-P004.

**honest-persist is not policed, and this needs no special case.** Inside honest-persist's own package, `transaction` and `apply` are the boundary functions, defined there and declared `boundary_out` in `honest-persist.hd`; a write that reaches the database sits inside one of them, so the boundary test already clears it. honest-persist's interior refers to those functions as local definitions, never as imports from `honest_persist`, so the writer-resolution step finds nothing to flag. The exemption falls out of the two tests above; the rule carries no "skip honest-persist" clause.

### 3.2 HC-ST002 detection, precisely

A shadow copy of user state is hard to recognize in the general case, so HC-ST002 names the one shape that creates it in honest-framework code: a program caches the result of `collect`. honest-dom's `collect(manifest)` reads the current user state fresh off the DOM every time a program calls it, which is what keeps the DOM the single store. A program that calls `collect` once and keeps the result in a lasting place reads from that stale copy afterward, and the page and the copy drift apart — the exact second store DATAOS forbids.

**The one shape that fires.** A JavaScript file binds the result of a `collect` call to a variable at module top level, as in `const state = collect(manifest)` or `export let rows = collect(manifest)`. A module-level binding outlives the call and becomes a store of its own, which is the same violation the client-state rule names when it says user state never lives in a module variable. The rule resolves `collect` through the file's own import from honest-dom — `import { collect } from "honest-dom"`, or an aliased `import { collect as read } from "honest-dom"` — so a `collect` that no honest-dom import binds is a different function and does not fire. The call may sit anywhere inside the bound value: `collect(m)`, `collect(m).filter(keep)`, and `wrap(collect(m))` each cache what `collect` read, so each fires.

**What does not fire.** A `collect` call inside a function, whose result the function hands straight to `send` or `apply` and then drops, keeps no copy and does not fire — that is the honest transient read the primitive is built for. A `collect` bound at module scope that no honest-dom import resolves does not fire, and the rule runs only over JavaScript, because `collect` is a client-side primitive.

**Dormant until honest-dom ships.** No honest-dom package exists yet, so no file imports `collect`, and the rule reports nothing across the framework today, exactly as HC-REF004 reports nothing while no honest-format manifest is configured. The rule is written and tested against planted sources, and it gains teeth the day honest-dom ships `collect` and application code imports it. An adapter that routes `collect`'s result into a host framework's own state, such as React `useState`, commits the same violation, but that check belongs to the adapter, because core honest-check does not model React or Vue.

---

## 4. honest-test Integration

Because states and events are honest-type vocabularies, honest-test generates exhaustive tests for every honest-type state machine automatically: every declared transition is exercised; every (state, event) pair absent from the table is verified to produce a `no_transition` fault; adversarial neighbours of every state and event name are verified to produce `invalid_state` / `invalid_event` faults; and terminal-state enforcement is verified for every declared terminal state. No developer input is required beyond the machine definition. The cross-kind single-mutator law is verified by the honest-check rules in §3.

---

## 5. Conformance

honest-state's own conformance is the law and its enforcement: every declared piece of state names exactly one mutator, and the honest-check rules in §3 fire on each way a second mutator could appear. The mechanics of each kind are conformed in their home modules — DATAOS in `honest-DOM`, the state machine in `honest-type`, server state in `honest-alerts`.

The conformance suite is `python/honest-state/conformance/suite.json`, beside the module and run by its gate. Its cases are language-agnostic data — input and expected output — so a second-language implementation proves conformance by running the same file. Its cases assert: each taxonomy row names exactly one mutator; a second mutator of a declared region is flagged unless it is honest and disjoint; and each §3 honest-check rule fires on a planted violation and stays silent on the honest form.

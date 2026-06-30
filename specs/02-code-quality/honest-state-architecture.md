# honest-state: Architecture Specification

**Date:** June 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

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
- **Domain state → a honest-type state machine.** A piece of domain state that moves through named conditions (an order: pending → paid → shipped) is a `state_machine` in honest-type; its single mutator is `transition()`, a pure function from (state, event) to the next state or a fault. The machine, its data shape, and its transition semantics are specified in `honest-type-architecture.md`. The honest-type state machine is the canonical model for domain-state transitions across all implementations. The *stored value* of that state lives in the database and is written by an ordinary honest-persist boundary write.
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
| boundary-write rule | a write to persisted state anywhere but an I/O-boundary function |
| DOM-as-single-store | a shadow copy of user state outside the manifest-declared DOM |

State machines are honest-type vocabularies, so the HC-SM rules apply to every honest-type `state_machine`:

| Rule | Description |
|---|---|
| HC-SM01 | State referenced in the transition table not in the states vocabulary |
| HC-SM02 | Event referenced in the transition table not in the events vocabulary |
| HC-SM03 | State is unreachable (no transition leads to it and it is not initial) |
| HC-SM04 | Non-terminal state has no outgoing transitions (dead state) |
| HC-SM05 | Initial state not in the states vocabulary |

Because states and events are honest-type vocabularies, these checks reuse the Set-intersection and reachability algorithms in `honest-check-architecture.md`. No new machinery is required.

---

## 4. honest-test Integration

Because states and events are honest-type vocabularies, honest-test generates exhaustive tests for every honest-type state machine automatically: every declared transition is exercised; every (state, event) pair absent from the table is verified to produce a `no_transition` fault; adversarial neighbours of every state and event name are verified to produce `invalid_state` / `invalid_event` faults; and terminal-state enforcement is verified for every declared terminal state. No developer input is required beyond the machine definition. The cross-kind single-mutator law is verified by the honest-check rules in §3.

---

## 5. Conformance

honest-state's own conformance is the law and its enforcement: every declared piece of state names exactly one mutator, and the honest-check rules in §3 fire on each way a second mutator could appear. The mechanics of each kind are conformed in their home modules — DATAOS in `honest-DOM`, the state machine in `honest-type`, server state in `honest-alerts`.

The conformance suite lives in the hub repo at `honest/honest-state-conformance/suite.json`. Its cases assert: each taxonomy row names exactly one mutator; a second mutator of a declared region is flagged unless it is honest and disjoint; and each §3 honest-check rule fires on a planted violation and stays silent on the honest form.

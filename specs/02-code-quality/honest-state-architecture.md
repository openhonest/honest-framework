# honest-state: Architecture Specification

**Version:** 0.2 (Draft)
**Date:** June 18, 2026
**Status:** §1 re-authored as the foundation (taxonomy + single-mutator law); §2 onward is prior-draft mechanical detail under reconciliation
**Author:** Adam Zachary Wasserman

---

## 1. Foundational Law: There Is No "The State"

Two ground truths govern everything in honest-state.

**1. There is no such thing as "the state."** There are many *kinds* of state, and each kind deserves its own treatment, store, and handling. The DOM is the store for *individual user* state — one kind among many, not "the" store. Login/session state that must be visible to every instance in a horizontally-scaled deployment lives in a shared store (Redis). Persisted domain state lives in the database. Conflating these — the mistake every general-purpose "state manager" makes — is the disease.

**2. Freely changeable state is the enemy.** When anything can change state from anywhere, the number of states the program can reach explodes beyond what anyone can follow, and that is exactly what makes software impossible to check — the very thing this framework exists to defeat. Hence the law:

> **Every declared piece of state has exactly one mutator** — one piece of code allowed to change it.

One mutator means one place to look; the set of changes stays small; small is what makes checking every case possible. This is not a rule bolted on — it is the spine that the ordinary boundary write (stored state), the DOM-as-single-store (user state), HC-P016 (closures), and the HC-P004 global-read clause (module state) are each a part of.

### 1.1 The single-mutator law, precisely

The unit of ownership is the **declared piece of state**, not the physical store. A *declaration* (e.g. the DATAOS manifest) carves a store into owned regions — which is what lets more than one writer touch the same physical store without contention.

A second mutator of a store is legitimate **if and only if** it is:

- **honest** — it does not *hide* the state it mutates, and
- **disjoint** — it does not *touch* any state another mutator already owns.

Two honest, disjoint mutators of one store are not a synchronization problem; they never write the same declared state. Two mutators of the *same* declared state always are. And "shared across N instances" never means "N mutators": a shared store with a single authoritative writer (see session/login) keeps the law intact under horizontal scaling — **share the store, keep the writer singular.**

### 1.2 The taxonomy of state kinds

Every piece of state belongs to exactly one kind, and every kind names exactly one mutator:

| Kind of state | Lives in | Single mutator |
|---|---|---|
| Individual user state | manifest-declared regions of the DOM | the user (any user-initiated action) |
| Server (SSE) state | non-declared regions of the DOM (alerts/notifications) | the server / alert source (honest-alerts) |
| Shared session / login | a shared store — Redis (scale-out) | the auth provider |
| Persisted domain state | the database | an ordinary boundary write (honest-persist update/insert/delete executed at the I/O boundary, §7.4) |
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

> **Status of the sections below.** §2 onward (the DATAOS client primitives — manifest / `collect` / `apply` / `observe`; the state-machine execution model) is prior-draft mechanical detail, retained for the mechanisms it documents and **to be reconciled against this foundation.** Where the older text conflicts with §1 it does not govern — in particular the earlier six-category taxonomy (replaced by §1.2), any framing of "one *owner*" rather than one *mutator per declared region*, and the claim that no state is shared across machines (§3.6), which the scale-out session/login row refutes.

---

## 2. User State: DATAOS

### 2.1 The Principle

The browser already has a state store. It is called the DOM.

React builds a virtual DOM, a state store, and a reconciliation engine to keep them synchronized with the real DOM. Three things that must agree. Redux adds a fourth. The entire React ecosystem is an elaborate solution to a problem that DATAOS eliminates by refusing to create it.

DATAOS does not create the problem. The DOM is the only copy of user state. What is in the DOM is what the state is, full stop. There is nothing to synchronize because there is nothing else.

This is not a limitation. It is the point. The browser has been optimized for 25 years to manipulate and query the DOM. `querySelector` is implemented in C++. It is fast. It is directly inspectable. It cannot get out of sync with itself.

### 2.2 The Statelessness Constraint

DATAOS enforces statelessness at two levels:

**Client-side:** No hidden JavaScript variables that shadow what the DOM says. The DOM is the state. If a filter tag is in the filter zone, it is active. If it is not there, it is not active. There is no `currentFilters` array somewhere that claims to know otherwise.

**Server-side:** No session storage of user state. Every request from the client includes the complete current user state, extracted fresh from the DOM immediately before the request is sent. The server processes it as a pure function and returns HTML. It remembers nothing. The next request will include the complete state again.

### 2.3 The State Manifest

A state manifest is a declarative specification of which DOM elements constitute user state and how to read their values. It is the DATAOS equivalent of a vocabulary declaration in honest-type: it names what counts, not how to process it.

```javascript
const manifest = {
    filterTags: {
        selector: '#filter-zone .tag',
        read:     'data:tag'
    },
    columnTags: {
        selector: '#column-zone .tag',
        read:     'data:tag'
    },
    sortOrder: {
        selector: '#sort-control',
        read:     'data:order'
    },
    searchQuery: {
        selector: '#search-input',
        read:     'value'
    }
}
```

**Read shortcuts:**

| Shortcut | Reads |
|---|---|
| `'value'` | `el.value` — form inputs |
| `'checked'` | `el.checked` — checkboxes |
| `'text'` | `el.textContent` |
| `'attr:name'` | `el.getAttribute('name')` |
| `'data:name'` | `el.dataset.name` |
| Function | `(el) => ...` — custom extraction |

A manifest entry with a selector that matches multiple elements produces an array. A manifest entry that matches a single element produces a scalar. A manifest entry that matches nothing produces `null`.

**Write shortcuts** (for `apply()`):

| Shortcut | Writes |
|---|---|
| `'value'` | `el.value = v` |
| `'checked'` | `el.checked = v` |
| `'text'` | `el.textContent = v` |
| `'attr:name'` | `el.setAttribute('name', v)` |
| `'data:name'` | `el.dataset.name = v` |
| Function | `(el, v) => ...` — custom application |

### 2.4 collect()

`collect()` reads the current DOM state using a manifest and returns a plain object.

```
collect(manifest) → state_object
```

`collect()` is a pure function. Same DOM, same manifest, same result. It does not modify the DOM. It does not cache. It reads the current state of the DOM at the moment it is called.

**Algorithm:**

```
FUNCTION collect(manifest):
    state ← {}

    FOR EACH (key, config) IN manifest:
        elements ← querySelectorAll(config.selector)

        IF elements is empty:
            state[key] ← null
            CONTINUE

        IF elements has one member:
            state[key] ← read(elements[0], config.read)
        ELSE:
            state[key] ← [read(el, config.read) FOR el IN elements]

    RETURN state

FUNCTION read(element, read_spec):
    IF read_spec is a Function:
        RETURN read_spec(element)
    IF read_spec = 'value':
        RETURN element.value
    IF read_spec = 'checked':
        RETURN element.checked
    IF read_spec = 'text':
        RETURN element.textContent
    IF read_spec starts with 'attr:':
        RETURN element.getAttribute(read_spec[5:])
    IF read_spec starts with 'data:':
        RETURN element.dataset[read_spec[5:]]
    RETURN null
```

### 2.5 apply()

`apply()` writes a state object back to the DOM using a manifest.

```
apply(manifest, state_object) → void
```

`apply()` is the inverse of `collect()`. It is used for page refresh recovery, multi-tab synchronization, and optimistic UI rollback. It does not add or remove elements; it updates existing elements that match the manifest selectors.

**Algorithm:**

```
FUNCTION apply(manifest, state):
    FOR EACH (key, config) IN manifest:
        IF key NOT IN state:
            CONTINUE
        IF config.write is null:
            CONTINUE

        elements ← querySelectorAll(config.selector)
        value    ← state[key]

        IF elements is empty:
            CONTINUE

        IF value is an Array:
            FOR EACH (element, i) IN zip(elements, value):
                write(element, config.write, value[i])
        ELSE:
            write(elements[0], config.write, value)

FUNCTION write(element, write_spec, value):
    IF write_spec is a Function:
        write_spec(element, value)
        RETURN
    IF write_spec = 'value':
        element.value ← value
    IF write_spec = 'checked':
        element.checked ← value
    IF write_spec = 'text':
        element.textContent ← value
    IF write_spec starts with 'attr:':
        element.setAttribute(write_spec[5:], value)
    IF write_spec starts with 'data:':
        element.dataset[write_spec[5:]] ← value
```

### 2.6 observe()

`observe()` watches the DOM for changes to elements covered by a manifest and calls a callback when state changes.

```
observe(manifest, callback) → unsubscribe_function
```

`observe()` uses a single `MutationObserver` internally. It batches callbacks via `requestAnimationFrame` for performance. It returns an unsubscribe function that stops observation when called.

**Algorithm:**

```
FUNCTION observe(manifest, callback):
    last_state ← collect(manifest)
    pending    ← false

    observer ← MutationObserver(FUNCTION(mutations):
        IF pending: RETURN
        pending ← true
        requestAnimationFrame(FUNCTION():
            current_state ← collect(manifest)
            IF current_state ≠ last_state:
                last_state ← current_state
                callback(current_state)
            pending ← false
        )
    )

    observer.observe(document.body, {
        childList:     true,
        subtree:       true,
        attributes:    true,
        characterData: true,
    })

    RETURN FUNCTION(): observer.disconnect()
```

### 2.7 The Dynamic Extraction Guarantee

This is the core safety guarantee of DATAOS and it is non-negotiable:

**Extract fresh from the DOM immediately before every backend request. Never use cached state for backend calls.**

The moment you assign extracted state to a variable and use that variable later, you have two sources of truth: the DOM (current) and your variable (potentially stale). This is the Redux problem recreated. The solution is not a shorter TTL. The solution is not a smarter cache. The solution is not to cache at all.

```javascript
// CORRECT
async function sendRequest(endpoint) {
    const state = collect(manifest)    // fresh extraction
    return fetch(endpoint, {
        method: 'POST',
        body:   JSON.stringify(state)
    })
}

// WRONG
const state = collect(manifest)        // extracted once
async function sendRequest(endpoint) {
    return fetch(endpoint, {
        method: 'POST',
        body:   JSON.stringify(state)  // stale after first DOM change
    })
}
```

**The only acceptable caching of extracted state** is for high-frequency UI rendering (animations, scroll handlers running at 60 FPS) with a TTL of 100ms maximum, with mandatory invalidation before any backend call. This is a performance optimization for display only. It is never an architectural convenience.

### 2.8 HTMX Integration

HTMX is the preferred transport layer for DATAOS applications. The honest-state HTMX extension collects state automatically before every HTMX request, using the manifest declared on the root element:

```html
<body hx-ext="honest-state" hs-manifest="appManifest">
    <!-- State is auto-collected and sent with every HTMX request -->
    <button hx-post="/api/search">Search</button>
</body>
```

The extension adds the collected state as a JSON body parameter on every outgoing request. The server receives complete, fresh user state on every call without any developer ceremony.

**HTMX extension algorithm:**

```
ON htmx:configRequest:
    manifest ← resolve(event.target.closest('[hs-manifest]').hs-manifest)
    state    ← collect(manifest)
    event.detail.parameters['_state'] ← JSON.stringify(state)
```

### 2.9 Page Refresh Recovery

User state is lost on page refresh unless explicitly persisted. The cache-and-replay pattern preserves state across refreshes without violating DATAOS principles.

**On every backend request, cache the state payload:**

```javascript
async function sendRequest(endpoint) {
    const state = collect(manifest)
    try {
        localStorage.setItem('honest_state_last', JSON.stringify(state))
    } catch (e) { /* storage unavailable — continue */ }

    return fetch(endpoint, {
        method: 'POST',
        body:   JSON.stringify(state)
    })
}
```

**On page load, restore cached state to DOM and replay:**

```javascript
function initialize() {
    try {
        const cached = localStorage.getItem('honest_state_last')
        if (cached) {
            const state = JSON.parse(cached)
            apply(manifest, state)    // restore DOM from cached state
            sendRequest('/api/render') // replay with restored state
            return
        }
    } catch (e) { /* storage unavailable or corrupt — continue */ }

    sendRequest('/api/render')         // fresh render with default state
}
```

This does not violate DATAOS. Cached state from a previous session is used only to reconstruct the DOM. Once the DOM is reconstructed, all subsequent requests extract fresh state from the DOM as normal.

### 2.10 Anti-Patterns

These patterns reintroduce synchronization problems and are forbidden in honest framework applications.

**Hidden state in variables.** Any JavaScript variable that holds a copy of what the DOM says is a second source of truth waiting to diverge.

**Extracting before DOM updates complete.** If HTMX is about to swap new HTML into the DOM, extract after the swap, not before. The honest-state HTMX extension handles this automatically.

**Partial extraction.** Collecting only the part of the manifest you think you need means the backend receives incomplete state. Always collect the complete manifest. Let the server decide what it uses.

**Mixing extract strategies.** Collecting some keys fresh and some from cache in the same request object guarantees inconsistency. Always extract all or nothing.

**Not using a manifest.** Scattering inline `querySelector` calls through business logic means state definition is scattered through code. The manifest is the single declaration of what counts as state. Use it.

---

## 3. Domain State: Pure Function State Machines

### 3.1 The Principle

Domain state is the current condition of a business entity as it moves through a defined lifecycle. It is not user configuration. It is not system health. It is the answer to: "What has happened to this thing, and what can happen next?"

Honest-state represents domain state as a pure function lookup table. States are a vocabulary. Events are a vocabulary. Transitions are a binding from `(state, event)` pairs to next states. The `transition()` function looks up the binding and returns the result. No classes. No mutation. No hidden logic. The machine is data; the executor is a pure function.

### 3.2 Data Structures

#### state_machine

```
state_machine = {
    name:        String           — identifier for honest-check and error messages
    states:      vocabulary       — all valid state names (Set recognizer)
    events:      vocabulary       — all valid event names (Set recognizer)
    transitions: {
        (state, event): next      — a next-state name
    }                             — the complete transition table
    initial:     String           — the starting state
    terminal:    [String]?        — optional terminal states
}
```

States and events are honest-type vocabularies. This means all honest-check HC-SM rules, honest-test exhaustive testing, and honest-type's reserved word validation apply automatically. State and event names cannot collide with framework reserved words. The transition table can only contain states and events declared in the vocabularies.

#### The transition is purely a routing

A transition is `(condition, event) → next condition` and nothing more. It does not carry an action. The target of a transition is always a single thing: a **next-state name**. The machine is plain data, and `transition()` looks up the `(state, event)` pair and returns the next state.

Anything a transition might trigger — a database write, a DOM update, a recorded history row — is not part of the machine. It is composed onto the machine's pure output by the chain that calls `transition()`. The sanctioned way to change stored data after a transition is an ordinary boundary write (honest-persist §7.4): a link that runs after a successful transition builds an update/insert/delete Query and executes it at the I/O boundary. That keeps the state machine free of any dependency on what happens next, so the same machine works whatever the surrounding chain does with its result.

#### transition_result

`transition()` returns a Result, consistent with the chain execution model:

```
ok({ state: next_state })         — valid transition, new state
err({ code: "no_transition",
      category: "client",
      detail: { state, event } }) — no transition defined for this pair
err({ code: "invalid_state",
      category: "client",
      detail: { state } })        — state not in states vocabulary
err({ code: "invalid_event",
      category: "client",
      detail: { event } })        — event not in events vocabulary
```

### 3.3 transition()

```
FUNCTION transition(machine, current_state, event):
    // Validate inputs against vocabularies
    IF current_state NOT IN machine.states:
        RETURN err({
            code:     "invalid_state",
            category: "client",
            message:  f"'{current_state}' is not a valid state for {machine.name}",
            detail:   { state: current_state }
        })

    IF event NOT IN machine.events:
        RETURN err({
            code:     "invalid_event",
            category: "client",
            message:  f"'{event}' is not a valid event for {machine.name}",
            detail:   { event: event }
        })

    key ← (current_state, event)

    IF key NOT IN machine.transitions:
        RETURN err({
            code:     "no_transition",
            category: "client",
            message:  f"No transition from '{current_state}' on '{event}' in {machine.name}",
            detail:   { state: current_state, event: event }
        })

    next ← machine.transitions[key]
    RETURN ok({ state: next })
```

`transition()` is a pure function. It takes the machine definition, the current state, and an event. It returns a Result. It does not store state. It does not read from a database. It does not write anywhere. The caller is responsible for persisting the new state.

### 3.4 Worked Example

```python
from honest_state import state_machine, transition
from honest_type import vocabulary

order_machine = state_machine(
    name    = "order_machine",
    states  = vocabulary({ "order_state": {"pending", "paid", "shipped", "cancelled"} }),
    events  = vocabulary({ "order_event": {"pay", "ship", "cancel", "refund"} }),
    initial = "pending",
    terminal = ["cancelled"],
    transitions = {
        ("pending",  "pay"):    "paid",
        ("pending",  "cancel"): "cancelled",
        ("paid",     "ship"):   "shipped",
        ("paid",     "cancel"): "cancelled",
        ("shipped",  "refund"): "cancelled",
    }
)

# Valid transition
result = transition(order_machine, "pending", "pay")
# ok({ state: "paid" })

# No transition defined
result = transition(order_machine, "pending", "ship")
# err({ code: "no_transition", category: "client", ... })

# Invalid state
result = transition(order_machine, "approved", "pay")
# err({ code: "invalid_state", category: "client", ... })
```

### 3.5 State Machines in Chains

`transition()` returns a Result and is a pure function, so it composes naturally into honest-type chains. A link that advances a state machine is a standard link:

```python
@link(accepts=order_vocab, emits=order_vocab)
def advance_order_state(manifest):
    current_state = manifest["order_state"]
    event         = manifest["order_event"]

    result = transition(order_machine, current_state, event)

    IF "err" IN result:
        RETURN result   // fault propagates up the chain

    RETURN ok({ **manifest, "order_state": result["ok"]["state"] })
```

The chain does not know or care that a state machine was consulted. It sees a link that takes a manifest and returns a Result. The state machine is an implementation detail of the link.

### 3.6 Parallel State Machines

A real application has multiple independent state machines running simultaneously. An order has an order state. Its payment has a payment state. Its shipment has a shipment state. These are separate machines tracking separate concerns.

Each machine operates independently. `transition()` takes one machine, one current state, one event, and returns one next state. Parallel machines are managed by keeping their current states in separate slots in the manifest:

```python
manifest = {
    "order_id":       ...,
    "order_state":    ...,     # order_machine current state
    "payment_state":  ...,     # payment_machine current state
    "shipment_state": ...,     # shipment_machine current state
}
```

Each machine advances independently through separate chain links. No machine reaches into another machine's state.

### 3.7 Cross-Machine Guards

Sometimes one machine's transition is only valid when another machine is in a specific state. A shipment can only be marked as dispatched when the order's payment is confirmed.

This is not a state machine feature. It is a business rule expressed as a link in the chain that runs before the `transition()` call:

```python
@link(accepts=shipment_vocab, emits=shipment_vocab)
def guard_dispatch_requires_payment(manifest):
    IF manifest["payment_state"] ≠ "confirmed":
        RETURN err({
            code:     "payment_not_confirmed",
            category: "client",
            message:  "Shipment cannot be dispatched until payment is confirmed"
        })
    RETURN ok(manifest)

# Chain: guard runs first, transition runs only if guard passes
dispatch_pipeline = chain(
    guard_dispatch_requires_payment,
    advance_shipment_state,
    persist_shipment_state,
)
```

The guard is explicit, named, and testable. The state machine remains pure. The cross-machine dependency is visible in the chain declaration, not buried inside a state machine definition.

### 3.8 Transition History

`transition()` returns the next state. It does not record the history of how the entity got there.

Transition history is a persistence concern, not a state machine concern. If an application needs to know that an order went `pending → paid → shipped`, that record is kept by the link that calls honest-persist after a successful transition:

```python
@link(accepts=order_vocab, emits=order_vocab, boundary=True)
async def persist_order_transition(manifest):
    new_state = manifest["next_order_state"]
    order_id  = manifest["order_id"]
    event     = manifest["order_event"]

    await db_record_transition(
        entity_id  = order_id,
        from_state = manifest["order_state"],
        event      = event,
        to_state   = new_state,
        timestamp  = now()
    )

    await db_update_entity_state(
        entity_id  = order_id,
        state      = new_state
    )

    RETURN ok({ **manifest, "order_state": new_state })
```

The state machine is not responsible for persistence. The chain composes persistence onto the state machine's pure output. The separation is clean: the machine knows valid transitions; the persistence link knows how to record them.

### 3.9 Terminal States

A terminal state is a state from which no further transitions are possible. When `machine.terminal` is declared, `transition()` enforces it:

```
FUNCTION transition(machine, current_state, event):
    ...
    IF current_state IN (machine.terminal OR []):
        RETURN err({
            code:     "terminal_state",
            category: "client",
            message:  f"'{current_state}' is a terminal state in {machine.name}. No further transitions.",
            detail:   { state: current_state }
        })
    ...
```

If `terminal` is not declared, no states are treated as terminal and the validator does not fire.

---

## 4. honest-check Integration

The HC-SM rules owned by honest-check apply to all state machines defined using honest-state:

| Rule | Description |
|---|---|
| HC-SM01 | State referenced in transition table not in states vocabulary |
| HC-SM02 | Event referenced in transition table not in events vocabulary |
| HC-SM03 | State is unreachable (no transition leads to it and it is not initial) |
| HC-SM04 | Non-terminal state has no outgoing transitions (dead state) |
| HC-SM05 | Initial state not in states vocabulary |

Because states and events are honest-type vocabularies, these checks use the same Set intersection and reachability algorithms defined in `honest-check-architecture.md`. No new machinery is required.

---

## 5. honest-test Integration

Because states and events are honest-type vocabularies, honest-test generates exhaustive tests for state machines automatically:

1. Every declared transition is exercised and verified.
2. Every (state, event) pair not in the transition table is verified to produce a `no_transition` fault.
3. Adversarial neighbors of every state and event name are verified to produce `invalid_state` or `invalid_event` faults.
4. Terminal state enforcement is verified for every declared terminal state.

No developer input is required beyond the machine definition itself.

---

## 6. Language Mapping

### 6.1 Client Side (collect, apply, observe)

| Language | Implementation |
|---|---|
| JavaScript | Native — uses DOM APIs directly |
| TypeScript | Same as JavaScript with type annotations |

`collect()`, `apply()`, and `observe()` are JavaScript/TypeScript only. They are DOM primitives. There is no server-side equivalent; user state is a client concern.

### 6.2 Server Side (state_machine, transition)

| Language | Implementation |
|---|---|
| Python | `honest_state.py` — plain dicts, tuple keys for transition table |
| JavaScript | `honest-state.js` — Map with string keys `"state:event"` |
| Ruby | `honest_state.rb` — hash with array keys |
| Go | `honest_state.go` — struct with map keyed by struct `{State, Event}` |

The transition table key format is language-idiomatic. The tuple `(state, event)` in Python becomes a concatenated string key in JavaScript, an array key in Ruby, and a struct key in Go. The spec does not prescribe key format; it prescribes behavior: given a state and an event, return the next state or a fault.

### 6.3 Nothing Sentinel

| Language | Nothing | Used for |
|---|---|---|
| Python | `None` | Terminal states, optional manifest reads |
| JavaScript | `null` | Terminal states, missing manifest elements |
| Ruby | `nil` | Terminal states, missing manifest elements |
| Go | `nil` (pointer) | Terminal states, missing manifest elements |

---

## 7. Conformance

### 7.1 Client-Side Conformance (DATAOS)

| Level | Requirement |
|---|---|
| **Core** | `collect()` correctly implements the manifest read algorithm for all shortcut types |
| **Full** | Core + `apply()` + `observe()` with single MutationObserver and requestAnimationFrame batching |
| **Complete** | Full + HTMX extension + page refresh recovery via cache-and-replay |

### 7.2 Server-Side Conformance (State Machines)

| Level | Requirement |
|---|---|
| **Core** | `transition()` correctly validates states and events against vocabularies and returns correct Results |
| **Full** | Core + terminal state enforcement + correct fault codes and categories |
| **Complete** | Full + honest-check HC-SM rule compliance + honest-test exhaustive test generation |

### 7.3 Conformance Suite

The conformance suite lives in the hub repo at `honest/honest-state-conformance/suite.json`. Test cases cover:

**Client-side:** Manifests with each read shortcut type. Single-element and multi-element selectors. Missing selectors producing null. `apply()` correctly writing to DOM. `observe()` firing on DOM mutations.

**Server-side:** Valid transitions returning correct next states. Missing transitions returning `no_transition`. Invalid states returning `invalid_state`. Invalid events returning `invalid_event`. Terminal states returning `terminal_state`. Order-independent results for the same machine, state, and event.

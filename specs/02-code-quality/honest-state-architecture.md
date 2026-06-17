# honest-state: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** March 15, 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. There Is No Such Thing As "The State"

Every framework that has ever failed you began with a lie: that your application has state, singular, and your job is to manage it.

This is wrong. It is wrong architecturally, wrong philosophically, and wrong in practice. It has produced Redux, MobX, Vuex, NgRx, Zustand, Jotai, and a graveyard of state management libraries whose entire existence is the management of complexity that should never have existed. The complexity was introduced by treating categorically different things as one thing.

Your application does not have state. It has several distinct kinds of state, each with its own scope, lifecycle, ownership, and rules. Conflating them is the disease. Honest-state is the diagnosis and the treatment.

### 1.1 The Taxonomy

Every piece of state in every application belongs to exactly one of these categories:

**User state** is the configuration a user has established in their current session: which filters are active, what the sort order is, which columns are visible, where they are in a multi-step wizard, what they have typed in a search field. User state is owned by the client. It is ephemeral. It lives and dies with the session. It is never the server's concern.

**Domain state** is the current condition of a business entity as it moves through a defined lifecycle: an order that is pending, paid, shipped, or cancelled. A ticket that is open, in-progress, or resolved. Domain state is owned by the server. It is durable. It is governed by explicit transition rules. It lives in the persistence layer.

**Transaction state** is the in-flight condition of an operation in progress: a payment being processed, a file being uploaded, a long-running job executing. Transaction state is transient. It exists only while the operation is active. It is neither user state nor domain state; it is process state.

**Session state** is the authenticated identity and authorization context of a connected user: who they are, what they are allowed to do, when their session expires. Session state spans requests. It is managed by the authentication layer. Honest-auth owns this concern.

**Configuration state** is the operational parameters of the application itself: feature flags, environment settings, rate limits, tenant-specific overrides. Configuration state is set by operators, not users. It is read-only at runtime. It lives in honest-persist as declared records, not in code.

**System state** is the health and operational condition of the running application: database connectivity, queue depth, cache hit rates, circuit breaker status. System state is observed, not managed. Honest-observe owns this concern.

### 1.2 The Universal Rules

Regardless of which kind of state you are dealing with, these rules apply without exception:

**One source of truth.** Every piece of state has exactly one owner. Two owners means a synchronization problem. A synchronization problem means bugs that are structurally guaranteed. There is no "eventual consistency" for state that two things claim to own simultaneously.

**Never synchronize.** Synchronization is what you do when you have two copies of something. The solution is not better synchronization. The solution is one copy. If you are synchronizing, you have already made the mistake.

**Never put your state in someone else's code.** User state does not belong in a Redux store that also holds server data. Domain state does not belong in a React component. Session state does not belong in a URL parameter. Each kind of state lives in the layer that owns it. Mixing ownership mixes concerns and destroys the boundary.

**Make transitions explicit.** State does not change; it transitions. A transition has a source state, an event, and a destination state. Every valid transition is declared. Every undeclared transition is rejected. There are no surprises.

**State changes happen at boundaries.** User state changes when the user acts. Domain state changes when an authenticated, validated request reaches the server. Configuration state changes through an explicit operational act. State changes are not scattered through business logic; they happen at declared, visible boundaries.

### 1.3 What honest-state Owns

Honest-state owns two of the six kinds of state:

**User state** on the client, via the DATAOS pattern: DOM As The Authority On State. The DOM is the owner, the manifest is the declaration, `collect()` is the reader, `apply()` is the writer, `observe()` is the watcher.

**Domain state** on the server, via pure function state machines: a lookup table from `(current_state, event)` to `next_state`. Pure functions in, data out. No classes, no mutation, no hidden transitions.

The other four kinds of state are owned by honest-auth (session), honest-persist (configuration), honest-observe (system), and the application's own business logic (transaction). Honest-state does not reach into their territory.

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
        (state, event): next_state
    }                             — the complete transition table
    initial:     String           — the starting state
    terminal:    [String]?        — optional terminal states
}
```

States and events are honest-type vocabularies. This means all honest-check HC-SM rules, honest-test exhaustive testing, and honest-type's reserved word validation apply automatically. State and event names cannot collide with framework reserved words. The transition table can only contain states and events declared in the vocabularies.

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

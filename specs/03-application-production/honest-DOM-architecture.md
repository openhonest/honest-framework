# honest-DOM: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** March 15, 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-DOM is the client-side DATAOS implementation layer of the Honest Framework. It provides the JavaScript primitives that make the DOM the authority on state in honest-framework applications: `collect()`, `apply()`, `observe()`, `on()`, `send()`, and `replay()`.

honest-DOM is not a framework. It is not a component library. It is a small, pure-function library that implements the DATAOS pattern — DOM As The Authority On State — defined in `honest-state-architecture.md`.

### 1.1 Reference Implementation

honest-DOM has one reference implementation, deliberately dependency-free:

**domx** — the canonical vanilla JavaScript implementation. Under 1KB gzipped. No dependencies. Works with HTMX, vanilla fetch, or any other transport. Available at [domx.software](https://domx.software).

The zero-dependency rule is not incidental: it keeps the framework's test suite a closed system. Nothing external enters the gate, so every branch is reachable and provable from the framework's own code. A reference implementation that pulled in a UI framework (React, Vue, Svelte) would test against unverified third-party code and destroy that closure. Those framework adapters are therefore community contributions (§4), not reference implementations — the Foundation neither ships nor gates them and makes no conformance claim about them. `domx` is the normative reference for the API contract.

### 1.2 What honest-DOM Owns

- The `collect()`, `apply()`, `observe()`, `on()`, `send()`, `replay()` API contract
- The manifest format and read/write shortcut specification
- The HTMX extension for automatic state collection
- The page refresh recovery (cache-and-replay) pattern
- Browser-side event emission via `sendBeacon()` to honest-observe
- `request_id` threading from server responses to browser events
- Conformance requirements for spoke implementations

### 1.3 What honest-DOM Does Not Own

- DATAOS architectural principles — honest-state owns this
- Server-side request handling — honest-py / honest-js
- Theme tokens and CSS custom properties
- Table and component configuration

---

## 2. The API Contract

The complete honest-DOM public API is six functions. All are pure functions or have explicit side effects with documented behavior.

### 2.1 collect(manifest) → state

Reads the current DOM state using a manifest and returns a plain object.

```
collect(manifest) → { [key]: value | [value] | null }
```

**Behavior:**
- For each manifest entry, queries the DOM using the declared selector
- If the selector matches zero elements: the key maps to `null`
- If the selector matches one element: the key maps to the scalar value extracted by `read`
- If the selector matches multiple elements: the key maps to an array of values
- Returns a plain object; never modifies the DOM
- Every call extracts fresh from the current DOM; no caching

The manifest is the **static declaration of user state**: its keys are the user-state fields, and each entry's `selector` says which template elements hold that field. Because the templates are source the shared parser reads, and code generation from them is deterministic, the full set of user-state fields is knowable before the app runs. This is why honest-check can enforce the DOM-as-single-store rule (no second copy of user state outside the page) statically, from the templates — it is never a runtime question (honest-state §3).

**Manifest entry format:**
```javascript
{
    selector: String,        // CSS selector
    read:     String | Function, // read shortcut or custom extractor
    write:    String | Function, // write shortcut or custom writer (for apply())
    watch:    String?,       // explicit event name override for observe()
}
```

**Read shortcuts:**

| Shortcut | Reads |
|---|---|
| `'value'` | `el.value` |
| `'checked'` | `el.checked` |
| `'text'` | `el.textContent` |
| `'attr:name'` | `el.getAttribute('name')` |
| `'data:name'` | `el.dataset.name` |
| Function | `(el) => any` — custom extractor |

### 2.2 apply(manifest, state) → void

Writes a state object back to the DOM using a manifest.

```
apply(manifest, state)
```

**Behavior:**
- For each manifest entry that has a `write` shortcut: writes the corresponding state value to all matching elements
- Entries without a `write` shortcut are skipped
- Does not add or remove elements; only updates existing elements
- Used for page refresh recovery, multi-tab synchronization, and optimistic UI rollback

**Write shortcuts:**

| Shortcut | Writes |
|---|---|
| `'value'` | `el.value = v` |
| `'checked'` | `el.checked = v` |
| `'text'` | `el.textContent = v` |
| `'attr:name'` | `el.setAttribute('name', v)` |
| `'data:name'` | `el.dataset.name = v` |
| Function | `(el, v) => void` — custom writer |

### 2.3 observe(manifest, callback) → unsubscribe

Watches the DOM for changes to elements covered by a manifest and calls a callback when state changes.

```
observe(manifest, callback) → () => void
```

**Behavior:**
- Uses a single shared `MutationObserver` internally; does not create a new observer per call
- Batches callbacks via `requestAnimationFrame` — at most one callback per animation frame regardless of mutation volume
- For `read: 'value'` entries: uses `input` event delegation
- For `read: 'checked'` entries: uses `change` event delegation
- For all other read shortcuts: uses the shared `MutationObserver`
- `watch` override in the manifest entry forces a specific event type
- Returns an unsubscribe function; calling it removes all listeners added by this `observe()` call

**Callback signature:**
```javascript
callback(state)  // called with the result of collect(manifest)
```

### 2.4 on(callback) → unsubscribe

Low-level subscription to raw DOM mutations.

```
on(callback) → () => void
```

**Behavior:**
- Subscribes `callback` to the shared `MutationObserver`
- Callback receives the raw `MutationRecord[]` array
- Returns an unsubscribe function

Use `on()` when you need raw mutation access. Use `observe()` when you want state-level change detection.

### 2.5 send(url, manifest, opts) → Promise\<Response\>

Collects state, caches it to localStorage, and sends it via fetch.

```
send(url, manifest, opts?) → Promise<Response>
```

**Behavior:**
- Calls `collect(manifest)` to get fresh state
- Caches the `{url, state, timestamp}` tuple to `localStorage` under key `domx:lastRequest`
- Sends a POST request with `Content-Type: application/json` and the state as the JSON body
- Returns the fetch `Response` promise

**Security note:** Cached state in localStorage is accessible to any script on the same domain. Do not include passwords, tokens, or sensitive PII in manifests used with `send()`.

### 2.6 replay() → Promise\<Response | null\>

Restores and replays the last cached request on page refresh.

```
replay() → Promise<Response | null>
```

**Behavior:**
- Reads the `domx:lastRequest` entry from localStorage
- If absent, expired (default TTL: 5 minutes), or malformed: returns `null`
- If valid: replays the cached POST request and returns the `Response` promise

**Pattern:**
```javascript
// On page load
const response = await replay()
if (response) {
    // Restore UI from replayed response
} else {
    // Fresh page load — use defaults
}
```

### 2.7 clearCache() → void

Removes the `domx:lastRequest` localStorage entry.

---

## 3. The HTMX Extension

honest-DOM provides an HTMX extension that collects state automatically before every HTMX request. When the extension is active, developers never call `collect()` manually for HTMX interactions.

**Activation:**
```html
<body hx-ext="domx" dx-manifest="appManifest">
    <!-- State is auto-collected and sent with every HTMX request -->
    <button hx-post="/api/search">Search</button>
</body>
```

**Extension behavior:**
1. Intercepts every HTMX `configRequest` event
2. Finds the nearest ancestor with a `dx-manifest` attribute
3. Resolves the manifest by name from the global scope
4. Calls `collect(manifest)` to get fresh state
5. Merges the state into the HTMX request parameters as `_state`

The state is included as a flat JSON string in `_state`. Server-side, honest-py extracts and classifies it via honest-type's `classify()`.

**dx-manifest attribute:**
```html
<!-- Root manifest applied to all HTMX requests -->
<body hx-ext="domx" dx-manifest="appManifest">

<!-- Override manifest for a specific subtree -->
<div dx-manifest="tableManifest">
    <button hx-post="/api/table">Refresh</button>
</div>
```

The nearest ancestor's `dx-manifest` wins. This allows scoped manifests for components that have independent state from the global application state.

---

## 4. Framework Adapters (community)

Adapters that bind `domx` to a UI framework — React, Vue, Svelte — are community contributions, not reference implementations. Each carries its framework as a runtime dependency, so the Foundation ships none of them, gates none of them, and makes no conformance claim about any of them (§1.1). They are listed in §7.

Every adapter obeys one contract, so DATAOS is preserved across frameworks:

- **Re-export, do not reimplement.** Re-export `collect`, `apply`, and `observe` from `domx`; the read/write/observe semantics are `domx`'s, not the adapter's.
- **Read the DOM through the framework's external-store primitive, never a duplicate store.** The DOM stays the single source of truth. A React adapter reads through `useSyncExternalStore` (subscribing via `observe`, snapshotting via `collect`) and never mirrors state into `useState`; an equivalent primitive is used elsewhere (Vue's `shallowRef` + `watchEffect`, Svelte stores). Any adapter that keeps a second copy of user state in framework state violates DATAOS and HC-ST002.
- **No lifecycle hooks.** `useEffect`, `componentDidMount`, `ngOnInit`, and their kin are forbidden (§6, HC-P011). Subscription and teardown go through the external-store primitive's own subscribe/unsubscribe, which returns `observe`'s unsubscribe.

A conventional React adapter surfaces `useDomState(manifest)`, `useDomValue(selector, read)`, `useDomArray(selector, read)`, and `useDomMap(selector, keyRead, valueRead)`, each a thin wrapper over `collect` on the matching manifest. These names are a convention for community adapters, not a framework-gated surface.

---

## 5. Browser Observability

honest-DOM is the browser-side instrumentation layer for honest-observe. It emits events automatically via `navigator.sendBeacon()` to `/api/observe/ingest`. These events land in the same event log as server events and are joined by `request_id`.

No developer code is required. The bootloader and domx instrument everything automatically. Every attribute classification, every DOM state change, every HTMX request and response is recorded.

### 5.1 emitBrowserEvent()

All browser event emission goes through one internal function:

```javascript
function emitBrowserEvent(event_type, payload) {
    const envelope = {
        event_id:      crypto.randomUUID(),
        event_type:    event_type,
        event_version: '1.0',
        timestamp:     new Date(
            performance.timeOrigin + performance.now()
        ).toISOString(),
        source:        'browser',
        session_id:    getSessionId(),    // from honest-auth cookie, read-only
        request_id:    currentRequestId, // see 5.2
        payload:       payload,
    }
    navigator.sendBeacon('/api/observe/ingest', JSON.stringify(envelope))
}
```

`emitBrowserEvent()` is internal. Application code does not call it. The framework calls it automatically.

### 5.2 request_id Threading

domx reads `X-Request-ID` from every HTMX response header and stores it **in the DOM** — a `data-request-id` attribute on `documentElement`. Every browser event reads it fresh from there, so the request_id is attached to all browser events until the next HTMX response overwrites it. It is never held in a module variable: a module-level mutable would be a second, hidden mutator of shared state — rejected by honest-check (HC-P004/HC-P016) and a contradiction of the module's own law that the DOM is the store. The store is the DOM; the single mutator is the response handler.

The read and write route through the domx HTMX extension's `onEvent`, not `document.addEventListener` (a lifecycle hook honest-check flags as HC-P011):

```javascript
// on htmx:afterRequest, inside the domx extension's onEvent:
storeRequestId(document.documentElement, readRequestId((name) => xhr.getResponseHeader(name)))
// and every emit reads it fresh:
currentRequestId(document.documentElement)
```

This means every browser event that follows a server response is traceable back to the server request that caused it: the DOM state change, the new element classifications, the next request triggered by the updated DOM. All linked.

### 5.3 Automatic Events

domx emits four event types automatically. See `honest-observe-architecture.md §8.4` for the full payload schemas.

| Event | Emitted when |
|---|---|
| `hf.browser.classify` | Bootloader classifies `h*-` attribute tokens |
| `hf.browser.request` | HTMX request is sent (`htmx:beforeRequest`) |
| `hf.browser.response` | HTMX response arrives (`htmx:afterRequest`) |
| `hf.dom.changed` | `observe()` detects a manifest state change |

### 5.4 Privacy

In production, browser events carry manifest keys but not values. The event records which slots changed, not what they changed to. Full values are included only in development mode (controlled by server config, communicated to domx via a meta tag).

```html
<!-- Set by server in development mode only -->
<meta name="honest-observe-mode" content="development">
```

domx reads this tag at boot. If absent or not `"development"`, values are omitted from all browser event payloads.

---

## 6. Anti-Patterns

These patterns violate DATAOS and are forbidden in honest-framework applications. honest-check HC-P011 flags client-side lifecycle hooks that indicate these patterns.

**Caching extracted state for backend requests.** Extract fresh immediately before every backend call. Never store extracted state in a variable and reuse it across multiple calls.

**Hidden state in JavaScript variables.** Any variable that holds a copy of what the DOM says is a second source of truth. The DOM is the state.

**Extracting before DOM updates complete.** The HTMX extension handles timing automatically. For manual fetch calls, extract inside the function that sends the request, not before.

**Not using a manifest.** Scattered inline `querySelector` calls through business logic are not honest-DOM. The manifest is the declaration of what constitutes state. Use it.

**Using lifecycle hooks.** `useEffect`, `componentDidMount`, `addEventListener`, `ngOnInit` — these signal imperative DOM manipulation. HTMX attributes and `observe` handle all state synchronization declaratively; a framework adapter (§4) routes through its external-store primitive, never a lifecycle hook.

---

## 7. Language Mapping

honest-DOM is a client-side library. It runs in the browser. The implementation language is always JavaScript or TypeScript.

| Environment | Implementation | Status |
|---|---|---|
| Vanilla JS / HTMX | `domx` | reference implementation |
| React | community adapter | not started |
| Vue | community adapter | not started |
| Svelte | community adapter | not started |

`domx` is the sole reference implementation (§1.1). React, Vue, and Svelte adapters are community contributions, held to the adapter contract in §4: conform to the honest-DOM conformance suite, re-export `collect`, `apply`, and `observe` from `domx` rather than reimplementing them, and read the DOM through the framework's external-store primitive rather than a duplicate store. The Foundation ships and gates none of them.

---

## 8. Conformance

### 8.1 Conformance Levels

| Level | Requirement |
|---|---|
| **Core** | `collect()`, `apply()`, `observe()` pass the conformance suite with all read/write shortcuts |
| **Full** | Core + `on()` + `send()` + `replay()` + HTMX extension |
| **Observable** | Full + `sendBeacon` event emission + `request_id` threading + all four automatic event types |

`Observable` is the top level: it is the whole DATAOS surface the Foundation ships and gates. Framework adapters (§4) add no conformance level of their own — an adapter conforms by re-exporting a conformant `domx`.

### 8.2 Conformance Suite

The conformance suite lives in the hub repo at `honest/honest-dom-conformance/suite.json`. Test cases run in a browser environment (jsdom or real browser) and cover:

- `collect()`: all read shortcuts, multi-element selectors, missing selectors returning null
- `apply()`: all write shortcuts, partial state application, missing write keys skipped
- `observe()`: fires on attribute change, text change, input event, checked event; batches via rAF; unsubscribe stops firing
- `send()`: caches to localStorage before fetching; sends correct Content-Type
- `replay()`: restores from cache; returns null when expired or absent
- HTMX extension: state is merged into HTMX request parameters; nearest `dx-manifest` wins
- Round-trip: `apply(manifest, collect(manifest))` leaves DOM unchanged

### 8.3 Reference Implementation Status

The reference implementation is `domx`. It is at the `Full` level — Core plus `on`, `send`, `replay`, and the HTMX extension — with `Observable` (browser-event emission, `request_id` threading, all four automatic events) in progress.

| Implementation | Core | Full | Observable |
|---|---|---|---|
| `domx` | ✅ | ✅ | in progress |

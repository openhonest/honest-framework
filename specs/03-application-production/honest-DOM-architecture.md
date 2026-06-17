# honest-DOM: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** March 15, 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-DOM is the client-side DATAOS implementation layer of the Honest Framework. It provides the JavaScript primitives that make the DOM the authority on state in honest-framework applications: `collect()`, `apply()`, `observe()`, `on()`, `send()`, and `replay()`.

honest-DOM is not a framework. It is not a component library. It is a small, pure-function library that implements the DATAOS pattern — DOM As The Authority On State — defined in `honest-state-architecture.md`.

### 1.1 Reference Implementations

honest-DOM has two reference implementations, both production-ready:

**domx** — the canonical vanilla JavaScript implementation. Under 1KB gzipped. No dependencies. Works with HTMX, vanilla fetch, or any other transport. Available at [domx.software](https://domx.software).

**stateless** — the React wrapper. Re-exports `domx` primitives as React hooks (`useDomState`, `useDomValue`, `useDomArray`, `useDomMap`) for applications that use React. Available at [stateless.software](https://stateless.software).

Both implementations pass the honest-DOM conformance suite. The `domx` implementation is the normative reference for the API contract.

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

## 4. React Hooks (stateless)

The `stateless` package wraps `domx` primitives as React hooks for applications that use React. It re-exports `collect`, `apply`, and `observe` from `domx` directly.

### 4.1 useDomState(manifest) → state

```typescript
const state = useDomState(manifest)
```

Reads state from the DOM and automatically updates when the DOM changes. Internally calls `collect(manifest)` on mount and re-collects via `observe()` on every DOM change.

### 4.2 useDomValue(selector, read) → value

```typescript
const value = useDomValue('#search-input', 'value')
```

Single-element shortcut for `useDomState`. Returns the scalar value for a single selector.

### 4.3 useDomArray(selector, read) → value[]

```typescript
const tags = useDomArray('#filter-zone .tag', 'data:tag')
```

Returns an array of values from all matching elements. Re-renders when the matched set or any element's value changes.

### 4.4 useDomMap(selector, keyRead, valueRead) → Map

```typescript
const prefs = useDomMap('[data-pref]', 'data:pref', 'data:value')
```

Returns a Map from key to value, one entry per matching element.

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

domx reads `X-Request-ID` from every HTMX response header and stores it as `currentRequestId`. This value is attached to all browser events until the next HTMX response arrives.

```javascript
document.addEventListener('htmx:afterRequest', (e) => {
    const id = e.detail.xhr.getResponseHeader('X-Request-ID')
    if (id) currentRequestId = id
})
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

**Using lifecycle hooks.** `useEffect`, `componentDidMount`, `addEventListener`, `ngOnInit` — these signal imperative DOM manipulation. The honest-DOM hooks and HTMX handle all state synchronization declaratively.

---

## 7. Language Mapping

honest-DOM is a client-side library. It runs in the browser. The implementation language is always JavaScript or TypeScript.

| Environment | Implementation | Status |
|---|---|---|
| Vanilla JS / HTMX | `domx` | ✅ production |
| React | `stateless` | ✅ production |
| Vue | not started | ❌ |
| Svelte | not started | ❌ |

Vue and Svelte implementations are community contributions. They must conform to the honest-DOM conformance suite and re-export `collect`, `apply`, and `observe` from `domx` rather than reimplementing them.

---

## 8. Conformance

### 8.1 Conformance Levels

| Level | Requirement |
|---|---|
| **Core** | `collect()`, `apply()`, `observe()` pass the conformance suite with all read/write shortcuts |
| **Full** | Core + `on()` + `send()` + `replay()` + HTMX extension |
| **Observable** | Full + `sendBeacon` event emission + `request_id` threading + all four automatic event types |
| **Complete** | Observable + React hooks (`useDomState`, `useDomValue`, `useDomArray`, `useDomMap`) |

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

Both reference implementations are conformant at the `Full` level:

| Implementation | Core | Full | Complete |
|---|---|---|---|
| `domx` | ✅ | ✅ | N/A (vanilla JS) |
| `stateless` | ✅ (via domx) | ✅ (via domx) | ✅ |

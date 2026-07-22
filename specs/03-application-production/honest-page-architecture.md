# honest-page: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** March 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-page defines the structural contract for an honest-framework HTML page. It is the layer where honest-type, honest-DOM, honest-alerts, and honest-py visibly connect: the point where a typed server request becomes a rendered page, and a user interaction becomes a typed server request again.

honest-page is not a component. It is not a layout engine. It is a contract: a declared set of surfaces, slots, and wiring conventions that every honest-framework application must provide. Any compliant implementation of this contract can serve as the host for honest-framework modules.

### 1.1 What honest-page Defines

- The required page surfaces: header, main, footer, and three notification zones
- The HTMX and honest-DOM bootstrap sequence
- The application state manifest declaration
- The CSS custom property token contract for base page layout
- The honest-alerts SSE wiring contract
- The server-side context variables the template expects
- The requirement that every reference the rendered surface emits — an `hx-*` action target, a `{% include %}` — resolves to a definition (a mounted route, an existing template), checked statically at the gate, never left to the browser (framework spec, "Every reference resolves, or the gate stops"; enforced by honest-check HC-REF)
- Conformance requirements for spoke implementations

### 1.2 What honest-page Does Not Define

- Visual design, colors, or typography — declared as CSS custom properties, resolved by the host
- Visual assembly of component layout within main — out of scope for this standard; the FOSS layout primitives are defined here
- Dynamic theme authoring and visual token management — out of scope for this standard. FOSS theming is honest-page's `--ht-` base tokens plus `light-dark()` (§7), combined with the component runtime's startup merge of component token defaults (honest-components §6.4)
- Authentication surfaces — honest-auth owns login, session expiry, and access denial rendering
- Navigation structure — application-specific

### 1.3 The Reference Implementation

The reference implementation is in `python/templates/base.html` and `python/templates/page.html`, with supporting files `python/app.py` and `python/static/theme.css`. These files are the normative reference for this spec. When this document and the reference implementation disagree, this document is correct.

---

## 2. Required Surfaces

A conformant honest-page must provide exactly these surfaces, identified by their `id` attributes. No surface may be omitted. Surfaces may be empty; they may not be absent.

### 2.1 Surface Registry

| Surface ID | Element | Purpose |
|---|---|---|
| `honest-header` | `<header>` | Application navigation and identity |
| `honest-main` | `<main>` | Primary page content; HTMX fragment target |
| `honest-footer` | `<footer>` | Secondary navigation and legal text |
| `honest-alerts-banners` | `<div>` | Persistent full-width notification bar; renders `banner` surface messages |
| `honest-alerts-toasts` | `<div>` | Transient overlay notifications; renders `toast` surface messages |
| `honest-alerts-modal` | `<div>` | Blocking overlay; renders `modal` surface messages requiring a reply |

### 2.2 Surface Placement

Surfaces must appear in this document order:

1. `honest-alerts-banners` — immediately after `<body>`, before `honest-header`
2. `honest-header`
3. `honest-alerts-toasts` — immediately after `honest-header`
4. `honest-main`
5. `honest-footer`
6. `honest-alerts-modal` — immediately before `</body>`, after `honest-footer`

The rationale: banners appear above the header because they are page-level alerts that supersede normal chrome. Toasts appear after the header because they float in the lower-right corner and must not occlude navigation. The modal appears last so it renders above all other content in stacking order.

### 2.3 Surface Rendering

`honest-alerts-banners`, `honest-alerts-toasts`, and `honest-alerts-modal` are honest-alerts SSE targets. They must carry the SSE wiring described in section 4. They must not contain static content at page load time; honest-alerts populates them at runtime.

`honest-header`, `honest-main`, and `honest-footer` are template blocks. They must be overridable by child templates.

---

## 3. Bootstrap Sequence

Every honest-page must load its dependencies in this order. Loading out of order produces undefined behavior.

```
1. CSS (in <head>)
   - theme.css (CSS custom properties)
   - Application styles

2. HTML body renders

3. Scripts (end of <body>, before </body>)
   - htmx.js
   - htmx-ext-sse.js       (Server-Sent Events extension)
   - domx.js               (honest-DOM client library)
   - Application manifest  (the appManifest declaration)
   - Application scripts
```

### 3.1 HTMX Version Contract

HTMX 2.x is required. HTMX 1.x is not compatible with this spec. The `hx-ext="sse"` extension is a separate package in HTMX 2.x and must be loaded explicitly.

Pin versions in production. CDN URLs in the reference implementation are for development convenience only.

### 3.2 domx Activation

domx is activated by placing `hx-ext="domx"` on `<body>`. This tells the HTMX extension mechanism to invoke domx's `configRequest` handler before every outgoing HTMX request.

The `dx-manifest` attribute on `<body>` declares the name of the application manifest variable. domx resolves this name from the global scope, calls `collect(manifest)`, and merges the resulting state into every HTMX request body as `_state`.

```html
<body hx-ext="domx" dx-manifest="appManifest">
```

Both attributes are required. `hx-ext="domx"` without `dx-manifest` means no state is collected. `dx-manifest` without `hx-ext="domx"` has no effect.

---

## 4. honest-alerts SSE Wiring

Each notification surface connects to the honest-alerts SSE stream via the HTMX SSE extension. The stream endpoint authenticates via the honest-auth session cookie; no explicit credentials are required in the template.

### 4.1 Connection Contract

All three surfaces connect to the same SSE endpoint: `/api/alerts/stream`. They filter to different event types via `sse-swap`.

```html
<!-- Banners: persistent, full-width, page-level notices -->
<div id="honest-alerts-banners"
     hx-ext="sse"
     sse-connect="/api/alerts/stream"
     sse-swap="alert:banner"
     hx-swap="afterbegin">
</div>

<!-- Toasts: transient, auto-expiring notifications -->
<div id="honest-alerts-toasts"
     hx-ext="sse"
     sse-connect="/api/alerts/stream"
     sse-swap="alert:toast"
     hx-swap="afterbegin"
     aria-live="polite"
     aria-atomic="false">
</div>

<!-- Modal: blocking overlay requiring explicit reply -->
<div id="honest-alerts-modal"
     hx-ext="sse"
     sse-connect="/api/alerts/stream"
     sse-swap="alert:modal"
     hx-swap="innerHTML"
     role="dialog"
     aria-modal="true">
</div>
```

### 4.2 SSE Event Types

The honest-alerts stream emits events of these types. The `sse-swap` value on each surface selects which events it receives.

| Event type | Target surface | `hx-swap` | Behavior |
|---|---|---|---|
| `alert:banner` | `honest-alerts-banners` | `afterbegin` | New banners prepend; existing banners remain until dismissed or expired |
| `alert:toast` | `honest-alerts-toasts` | `afterbegin` | New toasts prepend; they auto-remove after their TTL |
| `alert:modal` | `honest-alerts-modal` | `innerHTML` | Modal content replaces; only one modal is active at a time |
| `alert:clear` | (handled by domx) | — | Removes a specific message by ID from any surface |

### 4.3 SSE Keep-Alive

The `/api/alerts/stream` endpoint must emit a keep-alive comment (`: keep-alive\n\n`) at minimum every 30 seconds to prevent proxy and load balancer timeout. The reference implementation includes this behavior.

### 4.4 Unauthenticated Users

When no valid session exists, `/api/alerts/stream` returns HTTP 204 No Content. The SSE extension treats this as an empty stream; no error is shown. Application-level login prompts are delivered via honest-auth, not via honest-alerts.

---

## 5. Application State Manifest

The application manifest declares which DOM elements constitute user state. domx calls `collect(appManifest)` before every HTMX request and includes the result as `_state` in the request body.

### 5.1 Declaration Contract

The manifest must be declared as a global JavaScript variable named `appManifest` before any HTMX requests fire. The recommended placement is in a template block named `manifest` immediately after the domx client library loads.

```javascript
const appManifest = {
    search:   { selector: '#search-input', read: 'value' },
    filters:  { selector: '.filter-tag',   read: 'data:value' },
    sort:     { selector: '#sort-control', read: 'data:order' },
}
```

An empty manifest is valid and required: `const appManifest = {}`. A missing manifest is an error — domx cannot resolve the variable declared in `dx-manifest`.

### 5.2 Manifest Scope

`dx-manifest="appManifest"` on `<body>` applies to all HTMX requests on the page. A child element may override with its own `dx-manifest` attribute, which applies to all requests originating within that subtree. The nearest ancestor with `dx-manifest` wins.

This allows scoped state collection for components that have independent state from the global application manifest.

### 5.3 Server-Side Manifest Receipt

The server receives the collected manifest as `_state` in the request body (POST) or as a query parameter (GET). The honest-py intake middleware deserializes `_state` and merges its classified slots into `request.state.manifest` alongside the route's own classified parameters.

---

## 6. Server-Side Context Variables

The base template expects these variables from the server. All are optional with defaults; none are required.

| Variable | Type | Default | Description |
|---|---|---|---|
| `app_name` | String | `"Honest App"` | Application name shown in title and header |
| `page_title` | String | `"Page"` | Page-specific title prepended to app_name |
| `lang` | String | `"en"` | BCP 47 language tag for `<html lang="">` |
| `theme` | String | `"auto"` | Initial theme: `"light"`, `"dark"`, or `"auto"` |
| `request_id` | String | `""` | Request correlation ID for `X-Request-ID` header |

Child templates may declare additional context variables for their own blocks. The base template does not validate or reject unknown context variables.

---

## 7. CSS Custom Property Contract

honest-page defines a minimum token set that every conformant implementation must provide. These tokens govern base page layout only: surfaces, spacing, and typography. Component-specific tokens are declared by their respective components.

### 7.1 Required Token Namespaces

All honest-page tokens use the `--ht-` prefix. Tokens are organized by category.

**Color:**
```
--ht-color-bg-primary        Page background
--ht-color-bg-secondary      Surface background (cards, panels)
--ht-color-bg-surface        Elevated surface background

--ht-color-text-primary      Body text
--ht-color-text-secondary    Secondary text
--ht-color-text-muted        Disabled and placeholder text

--ht-color-border            Default border
--ht-color-border-strong     Emphasized border

--ht-color-accent            Interactive element highlight
--ht-color-accent-text       Text on accent background

--ht-color-success           Success state
--ht-color-warning           Warning state
--ht-color-danger            Error and destructive state
--ht-color-info              Informational state
```

**Spacing:**
```
--ht-space-xs    0.25rem
--ht-space-sm    0.5rem
--ht-space-md    1rem
--ht-space-lg    1.5rem
--ht-space-xl    2rem
--ht-space-2xl   3rem
```

**Typography:**
```
--ht-font-sans         System sans-serif stack
--ht-font-mono         System monospace stack

--ht-font-size-sm      0.875rem
--ht-font-size-md      1rem
--ht-font-size-lg      1.125rem
--ht-font-size-xl      1.25rem
--ht-font-size-2xl     1.5rem
```

**Radius:**
```
--ht-radius-sm     0.25rem
--ht-radius-md     0.5rem
--ht-radius-lg     0.75rem
--ht-radius-pill   999px
```

### 7.2 Token Value Contract

Every **colour** token must use `light-dark()` to provide both light and dark values. This is the only mechanism honest-page uses for dark mode. No JavaScript dark mode logic is permitted in the base page layer.

`light-dark()` is a colour function: it resolves to a `<color>`, so it applies to the colour tokens only. The spacing, typography, and radius tokens are plain values and do not vary by colour scheme; wrapping a length in `light-dark()` is invalid CSS and will not resolve.

```css
:root {
    color-scheme: light dark;
    --ht-color-bg-primary: light-dark(#ffffff, #0a0a0c);
}
```

The `color-scheme: light dark` declaration on `:root` is required. Without it, `light-dark()` values do not resolve correctly in all browsers.

### 7.3 Dark Mode Switching

honest-page supports three theme modes, controlled by the `data-theme` attribute on `<html>`:

| `data-theme` value | Behavior |
|---|---|
| absent | Follows OS preference via `@media (prefers-color-scheme)` |
| `"light"` | Forces light mode regardless of OS preference |
| `"dark"` | Forces dark mode regardless of OS preference |

Theme switching requires two CSS rules and eight bytes of JavaScript:

```css
[data-theme="dark"]  { color-scheme: dark; }
[data-theme="light"] { color-scheme: light; }
```

```javascript
// Set theme
document.documentElement.setAttribute('data-theme', 'dark')

// Clear theme (return to auto)
document.documentElement.removeAttribute('data-theme')
```

User theme preference is stored in `localStorage` under the key `honest-theme` and restored on page load. This is the only use of `localStorage` in the base page layer. Restoring preference must happen before first render to avoid a flash of incorrect theme.

```javascript
const saved = localStorage.getItem('honest-theme')
if (saved && saved !== 'auto') {
    document.documentElement.setAttribute('data-theme', saved)
}
```

This snippet must run in `<head>`, before the `<body>` renders.

### 7.4 Page Layout

The base page uses CSS Grid on `<body>` with three named areas:

```css
body {
    display: grid;
    grid-template-rows: auto 1fr auto;
    grid-template-areas:
        "header"
        "main"
        "footer";
}
```

`honest-header` maps to `header`, `honest-main` maps to `main`, `honest-footer` maps to `footer`. The notification surfaces (`banners`, `toasts`, `modal`) are positioned outside the grid flow:

- `honest-alerts-banners`: `position: sticky; top: 0` — stays visible during scroll
- `honest-alerts-toasts`: `position: fixed; bottom: ...; right: ...` — always in corner
- `honest-alerts-modal`: `position: fixed; inset: 0` — covers full viewport

---

## 8. Template Block Contract

A conformant base template must define these blocks. Child templates extend base.html and override blocks as needed.

| Block | Required | Default content | Purpose |
|---|---|---|---|
| `title` | No | `app_name` | `<title>` content |
| `styles` | No | empty | Additional CSS in `<head>` |
| `header` | No | `<nav>` with app_name link | Content of `honest-header` |
| `nav` | No | empty | Navigation links inside the default header nav |
| `content` | Yes | empty | Content of `honest-main` |
| `footer` | No | empty | Content of `honest-footer` |
| `manifest` | No | `const appManifest = {}` | appManifest declaration |
| `scripts` | No | empty | Page-specific scripts |

`content` is the only required override in a child template. A page that does not override `content` renders an empty main area, which is valid but not useful.

---

## 9. Route Map

A chain runs in response to an HTTP request, but the binding between request and chain must be a declaration a tool can read without running the application — not logic buried in a handler body. Every application declares a **route map**: a statically-readable mapping from a `(method, path)` pair to the chain that route runs.

One declaration serves two readers. At runtime, the framework registers a handler per entry: intake classifies the request (§5.3, §10.3) and the named chain receives the manifest. Statically, honest-check follows the route map to derive a chain's boundary vocabulary (honest-check-architecture.md §4.2, HC002): a template's `hx-post`/`hx-get` names a path, the route map names the chain that path runs, and the chain's first link is checked against the fields the templates targeting that path send — the closed-input boundary (honest-framework-spec.md, "The input boundary is closed").

The route map is data, not behaviour: each entry pairs exactly one method and path with one chain, named by a reference a parser can resolve. The realization is the spoke's idiom — a declared mapping value in one language, a routing table in another — but it must be statically inspectable, so a tool reads it by parsing, never by running the app. The honest-py realization is a declared mapping (§10.2).

---

## 10. honest-py Integration

### 10.1 Template Registration

The template directory must be registered with the Jinja2 environment at application startup. The recommended pattern uses FastAPI's `Jinja2Templates`:

```python
from fastapi.templating import Jinja2Templates
from pathlib import Path

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
```

### 10.2 Route Handler Contract

The honest-py realization of the route map (§9) is a declared mapping from `(method, path)` to chain:

```python
ROUTES = {
    ("POST", "/api/orders"): create_order_chain,
    ("GET",  "/api/items"):  fetch_items_chain,
}
```

honest-py registers a handler for each entry — intake classifies the request (§10.3) and the named chain receives the manifest — and honest-check reads the same `ROUTES` declaration to map each path to its chain. Route handlers that return full pages pass the standard context variables:

```python
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("page.html", {
        "request":    request,
        "app_name":   "My App",
        "page_title": "Home",
    })
```

Route handlers that return HTMX fragments do not use honest-page templates. They return minimal HTML fragments that HTMX swaps into `honest-main` or any other target. Fragment templates do not extend base.html.

### 10.3 Intake Middleware and _state

The honest-py intake middleware classifies both route parameters and the `_state` body parameter submitted by domx. The merged manifest is available as `request.state.manifest`.

The intake middleware must be registered before any route handlers:

```python
@app.middleware("http")
async def intake(request: Request, call_next):
    tokens = extract_tokens(request)      # route params + query params + _state
    manifest = classify(tokens, vocab, binding)
    request.state.manifest = manifest
    return await call_next(request)
```

`extract_tokens()` must handle three token sources and merge them without collision:
1. Path parameters: `/items/{id}` where `{id}` is a token
2. Query parameters: `?page=2&filter=active`
3. `_state`: the JSON-encoded manifest submitted by domx

Token priority on collision: `_state` wins over query parameters; query parameters win over path parameters. This ordering reflects the specificity of user intent: explicit state the user established in the DOM is more specific than URL-level parameters.

---

## 11. Conformance

### 11.1 Conformance Levels

| Level | Requirement |
|---|---|
| **Core** | All six surfaces present with correct IDs and document order; HTMX and domx loaded in correct sequence; `appManifest` declared; all required CSS tokens present using `light-dark()` |
| **Full** | Core + honest-alerts SSE wiring on all three notification surfaces; dark mode switching via `data-theme`; localStorage theme preference restoration; template blocks all declared |
| **Complete** | Full + honest-py intake middleware integrating `_state`; `request_id` header forwarding; fragment route handlers returning non-base templates |

### 11.2 Conformance Suite

A conformant implementation passes these checks:

**Structural:**
- All six surface IDs present in the rendered HTML
- Surfaces appear in the declared document order
- `<body>` carries `hx-ext="domx"` and `dx-manifest`
- `<html>` carries `lang` and `data-theme` (or data-theme absent for auto)

**Bootstrap:**
- HTMX script tag precedes SSE extension script tag
- SSE extension script tag precedes domx script tag
- `appManifest` declaration follows domx script tag
- Theme preference restoration script is in `<head>`, before `<body>`

**SSE:**
- Each notification surface carries `sse-connect="/api/alerts/stream"`
- Each surface carries the correct `sse-swap` event type
- Banner and toast surfaces use `afterbegin`; modal surface uses `innerHTML`

**CSS:**
- All required `--ht-*` tokens declared on `:root`
- Every colour token uses `light-dark()`; the spacing, typography, and radius tokens are plain values
- `color-scheme: light dark` declared on `:root`
- `[data-theme="dark"]` and `[data-theme="light"]` rules present

**Server:**
- Route handler passes `request` as first context variable
- All optional context variables use declared defaults when absent
- Fragment routes do not extend base.html

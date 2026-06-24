# honest-components: Architecture Specification

**Version:** 0.2 (Draft)
**Date:** March 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## Orientation: Read This First

Before the formal specification, the mental model. Skip this section and the CSS contract will confuse you.

### Three tiers, two behaviors

Every component belongs to one of three tiers: atom, molecule, or organism. The tier determines two things: how it mounts into the application, and what it is allowed to do.

An **atom** is the smallest thing: a button, an input, a label. It takes primitive values and renders one HTML element. It knows nothing about the application. No routes. No database. Pure presentation.

A **molecule** composes one or more atoms into a single-purpose unit: a form field (label + input + error text), a search bar (input + button). Still pure presentation. No routes. No database. No application knowledge.

An **organism** is a self-contained section of the page that talks to the server. It has a route handler. It queries the database. It receives typed input. It renders a complete HTML fragment. An organism will typically contain more than one molecule. A todo list, a data table, a user profile panel — these are organisms.

The tiers map to two mounting behaviors, not three:

- **Atoms and molecules** mount like static files. They live in `atoms/` and `molecules/` directories at the project root. At startup, the component runtime scans both directories, adds them to the template search path, and emits one `<link>` tag per CSS file found into `<head>`. No manifest. No registration function. They are simply there, available in any template. This also provides tree shaking: the component runtime only loads CSS for components that are actually installed. Add an atom, its CSS loads. Remove one, its CSS disappears. The installed component set IS the stylesheet.
- **Organisms** mount like plugins. They are packages with a `register()` function. Registration mounts their routes and templates. It also enforces their CSS namespace. They are components with a capital C.

### One namespace per component, for life

There is one global stylesheet. Every component owns a unique prefix. A component's CSS never uses any class it does not own.

The `button` atom owns `.button`, `.button__text`, `.button--primary`. No other CSS file on the page uses those classes. The `data-table` organism owns `.data-table`, `.data-table__row`, `.data-table--loading`. When a `data-table` organism renders a `button` atom inside it, the button's classes remain `.button`. The organism's CSS never mentions `.button`. The atom's CSS never mentions `.data-table`. They share the same page. They never overlap.

```html
<!-- The organism's territory -->
<div class="data-table" data-component="data-table">
  <div class="data-table__header">Name</div>
  <div class="data-table__row">

    <!-- The atom's territory: completely independent -->
    <button class="button button--ghost" data-component="button">
      Edit
    </button>

  </div>
</div>
```

Visual integration between components happens through CSS custom properties in `_variables.css`. The button reads `var(--color-primary)`. The data-table reads `var(--color-surface)`. Both tokens are declared once in `_variables.css`, owned by the application. Neither component owns a color value. They only reference tokens.

For organisms, this namespace contract is enforced at mount time. The component runtime scans the organism's CSS file and prefixes any selector that does not already carry the BEM block name. The scan never touches atom or molecule CSS files — those are separate global files.

### `data-component` does three things at once

Every component at every tier stamps its root HTML element with `data-component="<block-name>"`. This attribute is doing three jobs simultaneously:

1. **honest-observe hook.** The bootloader finds every element carrying `data-component` and emits an instrumentation event automatically. Zero developer code required. The observability is free.
2. **BEM anchor.** The `data-component` value is the BEM block name. `data-component="button"` means the CSS block is `.button`. One declaration, two purposes.
3. **Composition identity.** When components nest, `data-component` is how the system tells them apart. Two separate instrumentation events. Two separate CSS namespaces. Composition does not create confusion about ownership.

---

## 1. Purpose and Scope

honest-components defines the pattern for building server-rendered UI components in the Honest Framework. It is a pattern specification, not a runtime library. There is no honest-components package to install. There is no honest-components runtime dependency in production.

The output of honest-components is idiomatic code in the target language. A Python developer gets Jinja2 templates and FastAPI route handlers. A Ruby developer gets ERB partials and Rails controllers. A Go developer gets Go templates and net/http handlers. Each output is code a senior developer in that language would recognise as their own. No lowest common denominator. No abstraction layer in production. No runtime that follows the code into deployment.

This is the same principle that made Neonto extraordinary: a single component specification produces a genuinely native, idiomatic implementation for each target platform. honest-components makes the same guarantee across server-side web frameworks.

### 1.1 What honest-components Defines

- The three-tier hierarchy: atoms, molecules, organisms, and the distinct mounting behavior of each tier
- The CSS namespace contract: how each tier owns its CSS classes and how organism namespaces are enforced at mount time
- The `data-component` instrumentation contract: how honest-observe hooks into rendered organisms automatically
- The honest-type marshalling requirement: what must happen at the organism boundary
- The multi-target implementation structure for organisms: one implementation directory per target language
- The component runtime: discovery, organism mount and `register()` lifecycle, CSS-namespace enforcement, grid assembly, and the startup merge of component token defaults into `:root` (§6.4). The runtime is part of this module's reference implementation, not a separate package.

### 1.2 What honest-components Does Not Define

- The templating syntax for any specific language (Jinja2, ERB, Blade, Go templates — all are valid implementations)
- The HTTP routing mechanism for any specific framework (FastAPI, Rails, Laravel, Gin — all are valid implementations)
- Visual assembly, certification, or a visual design mode — out of scope for this standard; handled by separate tooling
- Dynamic theme management and visual theme editing — out of scope for this standard. FOSS theming is the component runtime's startup merge of component token defaults (§6.4) plus honest-page's `--ht-` base tokens and `light-dark()`
- CSS custom property values — declared as defaults in each component's `style.json`, merged at startup and overridable by the host

---

## 2. The Three-Tier Model

### 2.1 The Mental Model

Every component in honest-components belongs to one of three tiers: atom, molecule, or organism. The tier determines two things: how the component is mounted into the application, and what it is allowed to do.

The key insight is that the tiers have two distinct mounting behaviors, not three:

| Tier | Mounting behavior | Has routes | Has manifest | CSS enforced |
|---|---|---|---|---|
| Atom | Static asset | No | No | Declared by convention |
| Molecule | Static asset | No | No | Declared by convention |
| Organism | Component package | Yes | Yes | Enforced at mount time |

Atoms and molecules are global citizens. They are mounted exactly like CSS and JavaScript: placed in well-known directories, added to the template engine's search path at startup, available everywhere in every template. They have no registration function, no entry point, no discovery mechanism. They are simply there.

Organisms are packaged components. They have a `register()` function, a route handler, a declared namespace, and mount-time namespace enforcement. Each organism is a self-contained unit that owns its URL prefix, its database interactions, and its CSS namespace. The component runtime is the host application that discovers, registers, and enforces all of this.

### 2.2 Why This Separation

An atom like `button` or `form-field` is genuinely reusable across every application and every organism. It has no server interaction, no data dependency, no application-specific logic. Treating it as a packaged component with a manifest and a registration function would add ceremony with no benefit. It is a static asset and should be mounted as one.

An organism like `data-table` or `user-profile` has server routes, database queries, and typed input. It has a specific namespace it owns completely. It requires registration because it is dynamically adding behavior to the application at startup. It is a component and should be mounted as one.

Molecules sit at the boundary. A molecule composes atoms but has no server interaction. It is reusable across organisms. The decision: molecules mount as static assets alongside atoms. A molecule that becomes application-specific enough to need routes and data has become an organism.

### 2.3 Component Sovereignty

Every component at every tier is sovereign over its own CSS namespace. Composition is not ownership.

When an organism renders and includes an atom inside it, the atom's CSS classes remain the atom's. The organism's CSS namespace does not extend into the atom. They coexist on the same page under separate namespaces. The CSS cascade integrates them visually through shared tokens in `_variables.css`. That is the only coupling between them.

This is visible in rendered HTML:

```html
<!-- The organism owns .data-table and .data-table__* -->
<div class="data-table" data-component="data-table">
  <div class="data-table__header">...</div>
  <div class="data-table__row">

    <!-- The atom owns .button and .button__* independently -->
    <button class="button button--ghost" data-component="button">
      Edit
    </button>

  </div>
</div>
```

honest-observe sees two independent instrumentation events: one for `data-component="data-table"` and one for `data-component="button"`. Each component is observable independently, regardless of nesting.

---

## 3. Atoms

An atom is the smallest independently renderable component. It renders one HTML element or a tightly coupled group of elements that have no meaning when separated.

### 3.1 Mounting

Atoms live in the `atoms/` directory at the project root, peer to `static/`. Each atom is a subdirectory named after the atom's BEM block:

```
atoms/
    button/
        button.html     ← Jinja2 template (or ERB, Blade, etc. for other targets)
        button.css      ← CSS using only .button, .button__*, .button--* classes
    input/
        input.html
        input.css
    label/
        label.html
        label.css
```

At application startup, the `atoms/` directory is added to the template engine's search path. No manifest. No registration function. No entry point declaration. The atom is available in any template via `{% include 'button/button.html' %}` from that point forward.

### 3.2 Rules

- Parameters are primitives only: string, boolean, integer, enum, safe_html. No component references. No data from the server.
- An atom imports nothing from other components.
- An atom has no knowledge of the application: no routes, no database queries, no business logic.
- An atom's CSS file uses only classes prefixed with its BEM block name. No exceptions.

### 3.3 CSS Namespace

The atom declares its own namespace by convention. `.button` belongs to the button atom. No framework enforces this at mount time because no enforcement is needed: the atom's CSS file is a static asset and its scope is its own file.

### 3.4 The `data-component` Attribute

Every atom implementation stamps its root HTML element with `data-component="<name>"`. This serves three roles simultaneously:

1. **honest-observe instrumentation.** The bootloader scans for `data-component` and emits `hf.component.rendered` automatically. Zero developer instrumentation code required.
2. **BEM namespace anchor.** The `data-component` value is the BEM block name. If `data-component="button"`, the root CSS class is `.button`. The attribute is the single source of truth connecting HTML identity and CSS namespace.
3. **Identity under composition.** When an atom renders inside an organism, `data-component` identifies it as the atom's own element, not an element belonging to the organism's namespace.

### 3.5 Examples

button, input, label, checkbox, radio, select, textarea, avatar, badge, icon, separator, link, spinner.

---

## 4. Molecules

A molecule combines atoms into a meaningful unit that serves a single, focused purpose.

### 4.1 Mounting

Molecules live in the `molecules/` directory at the project root, peer to `static/` and `atoms/`. Each molecule is a subdirectory named after the molecule's BEM block:

```
molecules/
    form-field/
        form-field.html     ← includes atoms from atoms/
        form-field.css      ← uses only .form-field, .form-field__*, .form-field--*
    card/
        card.html
        card.css
    search-input/
        search-input.html
        search-input.css
```

At application startup, the `molecules/` directory is added to the template engine's search path alongside `atoms/`. No manifest. No registration function.

### 4.2 Rules

- Parameters are primitives plus references to atom templates.
- A molecule imports and composes atoms. It does not import other molecules.
- A molecule has no knowledge of the application: no routes, no database queries, no business logic.
- A molecule's CSS file uses only classes prefixed with its BEM block name.

### 4.3 CSS Namespace

Same as atoms: the molecule declares its namespace by convention. `.form-field` belongs to the form-field molecule. The atom CSS files included within a molecule template remain sovereign: `.input` inside `form-field.html` is the input atom's class, not the form-field molecule's.

### 4.4 The `data-component` Attribute

Same contract as atoms. Every molecule stamps its root element with `data-component="<name>"` for honest-observe instrumentation and namespace identity.

### 4.5 Examples

form-field (label + input + error), card, button-group, search-input, stat-display, breadcrumb, pagination, alert.

---

## 5. Organisms

An organism is a self-contained section of the UI that carries server interaction and receives structured data from the server.

### 5.1 Mounting

Organisms are packaged components discovered and mounted at application startup. Each organism is either an installed Python package (discovered via `entry_points`) or a local package registered explicitly. The component runtime calls the organism's `register()` function at startup, which mounts its routes and templates.

At mount time, the component runtime performs a namespace scan on the organism's CSS file. See section 6 for the enforcement algorithm.

### 5.2 Rules

- Parameters are primitives, atom/molecule template references, and `data` structures from the server.
- An organism may import and compose atoms and molecules.
- An organism may carry HTMX interaction attributes directly.
- An organism is the only tier that may call `classify()` and receive typed input from an HTTP request.
- An organism must have a route handler in the target language.
- An organism must declare a unique BEM block name in its manifest. If the name is already registered by another organism, mounting fails.
- Organisms never import other organisms.

### 5.3 The `data-component` Attribute

Same contract as atoms and molecules, with one addition: because organisms have route handlers, `data-component` also anchors the HTMX request target. The organism's root element carries `data-component`, and honest-observe correlates the rendered event with the route that served it.

### 5.4 Examples

data-table, filter-panel, modal, header, tabs, performance-chart, security-card, user-profile, login-form.

---

## 6. The CSS Namespace Contract

### 6.1 The Core Rule

Every CSS class used by a component must start with that component's BEM block name.

- The `button` atom uses `.button`, `.button__text`, `.button--primary`. It uses no other classes.
- The `form-field` molecule uses `.form-field`, `.form-field__label`, `.form-field--error`. It uses no other classes.
- The `data-table` organism uses `.data-table`, `.data-table__row`, `.data-table--loading`. It uses no other classes.

When a molecule's template includes a button atom, the button's classes remain `.button__*`. The molecule's CSS file never touches `.button`. The button atom's CSS file is a separate file that declares `.button` globally, and is not subject to any namespace enforcement by the molecule.

### 6.2 Enforcement

**Atoms and molecules:** namespace is declared by convention, not enforced. The CSS file is a static asset. A well-named component author writes only namespaced classes. The convention is simple enough to follow without tooling.

**Organisms:** namespace is enforced at mount time by the component runtime. The algorithm:

```
scan_css(css_text, block_name):
    for each selector in css_text:
        if selector starts with "." + block_name:
            leave it alone                    ← already namespaced
        if selector is a global element (html, body, :root, *, @media):
            leave it alone                    ← intentionally global
        else:
            prepend "." + block_name + " "    ← scope to this organism
```

The rewriting is automatic. An organism author who writes `.row` inside `data-table.css` gets `.data-table .row` after the scan. An atom author who writes `.button` inside their own `button.css` is never scanned by the organism — the atom's CSS file is separate and mounted globally before any organism mounts.

This means an organism can use atom and molecule classes inside its templates freely. The CSS files are separate. The scan only touches the organism's own CSS file.

### 6.3 Token Values Are Never Namespaced

CSS custom properties (`--color-primary`, `--button-height`, etc.) are global by definition. The namespace scan never touches custom property declarations or references. The organism's `var(--data-table-bg)` references a token declared in `_variables.css`, which is global. The scan does not prefix it.

### 6.4 The Token File and Token Resolution

Components never declare their own CSS custom property values. They only reference tokens via `var(--...)`. The values come from the installed components' declared defaults, resolved at startup.

**Normative (FOSS) path.** At startup, the component runtime reads the style manifest (`style.json`) from every installed component, collects every declared token across all components, and merges their declared default values into a single `:root {}` CSS block served to the browser. The installed component set determines the token set, exactly as it determines the stylesheet. Dark mode is honest-page's `light-dark()` mechanism (honest-page §7), not server-side mode resolution; the component runtime emits the declared defaults and the browser resolves light/dark. This static startup merge, combined with honest-page's `--ht-` base tokens, is the complete FOSS theming story. A conformant application themes fully with nothing more.

**Out of scope for this standard.** Dynamic theme management — resolving token values against a theme record stored in honest-persist at serve time, regenerating the CSS when a theme record changes, and a visual token editor — is provided by separate tooling and is not part of the FOSS standard. Such tooling consumes the same `style.json` contract the FOSS component runtime does; the FOSS runtime never depends on it.

### 6.5 style.json: The CSS Token Contract

Every organism ships a `style.json` file declaring every CSS custom property its CSS file references. It is the organism's public CSS API: every key is a supported customization point, nothing more and nothing less.

```json
{
  "block": "data-table",
  "tokens": {
    "--data-table-bg":          "Table background",
    "--data-table-border":      "Row and container borders",
    "--data-table-header-bg":   "Header row background",
    "--data-table-row-hover":   "Row hover highlight",
    "--data-table-accent":      "Sort indicator and selection highlight"
  }
}
```

`block` must match `data-component` on the organism's root element and the BEM block prefix used in its CSS file. All three are the same value.

`tokens` maps every CSS custom property the organism uses to a human-readable description. Every property declared here must appear in the CSS file via `var(--...)`. Every property used in the CSS file must be declared here. No exceptions in either direction.

Token values are absent by design. A token's value comes from the installed components' declared defaults — merged by the component runtime at startup (§6.4) and overridable by the host. The component declares only what it needs.

`style.json` serves two normative (FOSS) roles:

1. **Source for the startup token block.** The component runtime reads every installed component's `style.json` to assemble the single `:root {}` default-merge block (§6.4). The installed set determines the token set.
2. **Override documentation for the host.** A host application reads `style.json` to know exactly what it can override. Every key is a supported customization point.

Separate tooling outside this standard (visual token editors, assembly-time namespace-compatibility checkers) may also read `style.json`, but the standard does not require those tools, and `style.json` is fully meaningful without them.

Atoms and molecules have no `style.json`. Their CSS uses tokens from the application's `_variables.css` directly. Their token surface is implicit in their CSS files, not declared separately. Only organisms carry an explicit token contract because only organisms are packaged components with a declared external interface.

---

## 7. The honest-type Marshalling Requirement

At the organism boundary, every input arriving from an HTTP request must pass through `classify()` before the organism renders. The organism receives a typed manifest. Atoms and molecules receive only what the organism passes down to them as parameters. No raw string from an HTTP request may reach an atom or molecule.

```python
# Python example — same logic in all target languages
manifest = classify(
    tokens = [*path_params.values(), *query_params.values()],
    vocab  = table_vocab,
    bind   = table_binding,
)
# manifest: {"page": "2", "sort": "name", "order": "asc", "filter": "active"}
# The organism template receives manifest, not raw query strings.
```

Atoms and molecules never call `classify()`. They receive only typed values passed down from the organism that composes them.

---

## 8. The Multi-Target Structure for Organisms

An organism package contains one implementation per supported target language, plus the CSS file, plus `manifest.json`.

```
honest-organism-data-table/
    manifest.json               ← interface contract, tier, BEM block name
    css/
        data-table.css          ← shared across all target languages
    python/
        data-table.html         ← Jinja2 template
        routes.py               ← FastAPI route handler
        vocab.py                ← honest-type vocabulary
    ruby/
        _data-table.html.erb    ← ERB partial
        data_table_controller.rb
        vocab.rb
    go/
        data-table.html         ← Go template
        handler.go
        vocab.go
    php/
        data-table.blade.php    ← Blade component
        DataTableController.php
        vocab.php
    javascript/
        data-table.html         ← Nunjucks template
        routes.js
        vocab.js
```

Atoms and molecules have no `manifest.json` and no `routes.*` files. Their structure is flat:

```
atoms/button/
    button.html     ← template only
    button.css      ← CSS only
```

---

## 9. The `data-component` Attribute: Three Roles

Every component at every tier must stamp its root HTML element with `data-component="<block-name>"`.

**Role 1: honest-observe instrumentation hook.** The bootloader scans every DOM element carrying `data-component` and emits `hf.component.rendered` automatically. No developer instrumentation code is required at any tier.

**Role 2: BEM namespace anchor.** The `data-component` value IS the BEM block name. `data-component="button"` means the root CSS class is `.button`. The attribute connects HTML identity to CSS namespace without any separate declaration.

**Role 3: Composition identity.** When components nest, `data-component` identifies which elements belong to which component. The organism's root element carries the organism's `data-component`. The atom's root element inside it carries the atom's `data-component`. honest-observe fires separate events for each. CSS namespaces remain separate. Composition does not create confusion about ownership.

---

## 10. Composition Rules Summary

| Rule | Atom | Molecule | Organism |
|---|---|---|---|
| Mounting behavior | Static asset | Static asset | Component package |
| Has manifest.json | No | No | Yes |
| Has route handler | No | No | Yes |
| May include atoms | No | Yes | Yes |
| May include molecules | No | No | Yes |
| May include organisms | No | No | No |
| May receive server data | No | No | Yes |
| May call classify() | No | No | Yes |
| CSS namespace enforced | Convention | Convention | Mount-time scan |
| data-component required | Yes | Yes | Yes |

---

## 11. Relationship to Other Specs

**honest-page:** defines host page structure. Organisms render into honest-page's `honest-main` via HTMX fragment swaps.

**honest-type:** provides `classify()`. Used only at the organism boundary. Atoms and molecules never call it.

**honest-observe:** instruments all components automatically via `data-component`. No component at any tier calls honest-observe directly.

---

## 12. Conformance

A conformant implementation satisfies all of the following:

**Atoms and molecules:**
- HTML file and CSS file in the correct directory (`atoms/` or `molecules/`)
- Root element carries `data-component="<block-name>"`
- CSS file uses only classes under the BEM block namespace
- No hardcoded values in CSS; every value references a token via `var(--...)`
- Atom parameters contain no server data types
- Molecule parameters contain no server data types

**Organisms:**
- `manifest.json` declares name, tier, BEM block, all parameters with types and defaults
- Root element carries `data-component="<block-name>"`
- BEM block name is unique across all mounted organisms; duplicate names fail at mount
- CSS file passes namespace scan at mount time
- Route handler calls `classify()` before rendering
- No raw HTTP request strings reach the template

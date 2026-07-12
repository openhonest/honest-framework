# honest-format: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** July 12, 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-format renders a raw value to a display string from a declarative attribute. A rendered element carries the value and names the format; the module supplies the formatter. No imperative call site formats a value by hand, and no two call sites format the same kind of value two different ways.

honest-format is the spec-captured successor to genX's `fmtx` (FormatX) and `smartx` (SmartX). **genX is the reference of record.** Where this spec and the genX implementation disagree on an observable result, genX's proven behaviour is authoritative and this spec is corrected — the library is mature and field-tested; the spec documents it. The two exceptions are the two defects recorded in Section 9, which the reference implementation fixes.

### 1.1 What honest-format Owns

- The closed **format vocabulary** — the set of format names (`currency`, `date`, `phone`, …) an element may request, and the input-conversion names (`cents`, `unix`, …) it may declare (Section 5).
- The **pure formatter contract**: `format(type, value, opts) → string`, total over the vocabulary (Section 6).
- The **attribute grammar**: `hf-format` and its sibling option attributes, and `hf-raw` as the processed marker and source of truth (Section 4).
- The **auto-detection** behaviour (`hf-format="smart"`): value → detected type by a confidence-scored pattern table (Section 7).
- The **DOM binding contract**: scan, format, unformat, and the re-scan predicate that makes swapped-in content format correctly (Section 8).
- The **declared vocabulary manifest** the static checker resolves attribute values against (Section 5.4, HC-REF004).

### 1.2 What honest-format Does Not Own

- State authority — honest-DOM owns `collect`/`apply`/`observe`; honest-format is invoked by the scan, it does not hold state.
- The MutationObserver itself — honest-format subscribes to honest-DOM's shared observer bridge; it does not open its own.
- Telemetry transport — a low-confidence auto-detection is an event emitted to honest-observe, not an HTTP client inside the formatter (Section 7.3).
- Locale data — honest-format passes a locale string to the platform `Intl` API; it ships no locale tables.
- UI structure or styling — that is honest-components.

### 1.3 Reference Implementation

The reference implementation is JavaScript, rebranded from genX's `fmtx.js` and `smartx.js` and rebuilt to pass the five gates (honest-check clean, 100 % line+branch coverage, mutation-adequate, portable value oracle, feature bijection). The genX source at `~/dev/genX/src/fmtx.js` and `~/dev/genX/src/smartx.js` is the read-only behavioural reference; no genX file is copied in unrebuilt. The `switch` dispatch of the reference becomes dict-dispatch tables (Section 6.1) — a discriminant `switch`/`if-elif` chain is an HC-P001 violation the module may not ship.

---

## 2. The bug class this eliminates

A value formatted by imperative code is formatted wherever a developer remembered to call the formatter, with whatever options they remembered to pass. The failures are silent: a value renders raw because no call was wired to it; the same currency renders `$1,234.5` in one table and `$1,234.50` in another because two call sites disagreed; a swapped-in row shows `31210137967` because the post-swap formatting hook was forgotten. Declaring the format on the element — `hf-format="currency"` — removes the call site, and with it the class of "the value is displayed, but unformatted or inconsistently formatted, because the imperative wiring was missed." The element that carries a value **declares** how it reads; there is nowhere left to forget.

The declaration then becomes statically checkable. An `hf-format="curency"` typo names no formatter, so the element would render raw — a dead reference in the sense of the framework's reference-resolution rule. honest-check resolves every `hf-format` value against the declared vocabulary (Section 5.4, HC-REF004) and stops the gate before such an element ever renders. This is the same poka-yoke as every other honest module: the declarative surface eliminates the imperative-wiring bug, and the closed vocabulary makes the surface checkable.

---

## 3. Design shape

honest-format is a pure core wrapped by a thin DOM boundary.

- **Pure core** — `format(type, value, opts)` and `detect(value)` are pure functions of their inputs. Same value and options, same string, no DOM, no clock read except where a format is defined against "now" (Section 6.4).
- **Dispatch tables, not branches** — the format name selects a formatter from a table; the input-conversion name selects a converter from a table. No discriminant `switch`.
- **DOM boundary** — reading an element's attributes, writing its text, subscribing to the observer: the only impure surface, isolated in the binding layer (Section 8).

---

## 4. The Attribute Grammar

An element opts in by carrying `hf-format`. Its value is the format name; sibling `hf-*` attributes carry the options; `hf-raw` carries (and after first format, records) the source value.

```html
<span hf-format="currency" hf-currency="USD" hf-decimals="2">1299.99</span>
<!-- renders: $1,299.99 -->
```

### 4.1 The single canonical notation

The format and its options are sibling attributes: `hf-format` names the type, and each option is its own `hf-<option>` attribute (`hf-decimals`, `hf-currency`, `hf-phone-format`). This is genX's `fx-format` grammar, rebranded `fx-` → `hf-`. It is **type-in-value** (`hf-format="currency"`), the mature genX design — not the type-in-name form (`hf-money`, `hf-percent`) sketched in the framework spec §116, which is superseded here (§116 is corrected to match). One notation only: honest-format does not carry genX's alternative colon / JSON / CSS-class notations. A single grammar is what HC-REF004 resolves and what a reader reads.

### 4.2 The source value

The value to format is read, in order: `hf-raw`, then `hf-value`, then the element's text content (or an input's `value`). On first format the element's resolved source is written back to `hf-raw`, and the display replaces the text (or input value). Re-reads format from `hf-raw`, never from the already-formatted display — formatting is idempotent (Section 8.2).

### 4.3 The option attributes

Option attribute values are read as strings and coerced per the option's declared kind (integer for `hf-decimals`, boolean for `hf-binary`/`hf-thousands`, string otherwise). Kebab-case attribute names map to the formatter's option keys (`hf-phone-format` → `phoneFormat`). The option set per format type is Section 5.3.

### 4.4 `hf-raw` is the processed marker

An element is **unprocessed** when it carries `hf-format` and lacks `hf-raw`; it is **processed** once `hf-raw` is present. This DOM-visible predicate — not an in-memory "seen" set — is the source of truth for whether formatting is owed (Section 8.3). It is what makes swapped-in content correct: a node HTMX inserts has no `hf-raw`, so it is unprocessed by construction.

---

## 5. The Format Vocabulary

The vocabulary is closed. Every name below is a member; every other name is a dead reference (Section 2).

### 5.1 Format types

**Numeric** (require a parseable number; a non-number value renders as itself):

| Name | Renders |
|---|---|
| `number` | grouped decimal, `hf-decimals` places, `hf-thousands` grouping |
| `currency` | `Intl` currency in `hf-currency` (default USD), `hf-decimals` places |
| `percent` | value × 100 (unless input already a percentage), `hf-decimals` places (default 0), `%` suffix |
| `scientific` | exponential notation, `hf-decimals` places (default 2) |
| `accounting` | currency; negatives parenthesised `($1,234.00)` |
| `abbreviated` | magnitude-bucketed `K`/`M`/`B`/`T`, `hf-decimals` (default 1), `hf-prefix`/`hf-suffix`, `hf-threshold` |
| `compact` | `Intl` compact notation, long form under `hf-long`; falls back to `abbreviated` where unsupported |
| `millions` / `billions` / `trillions` | value scaled to that unit, unit letter suffix |
| `filesize` | `B`/`KB`/`MB`/… (decimal) or `B`/`KiB`/`MiB`/… under `hf-binary` |
| `duration` | seconds → `hf-duration-format` (`short`/`human`/`medium`/`long`/`compact`/`clock`) |
| `fraction` | nearest fraction, `hf-denominator` or best power-of-two denominator |

**Temporal** (require a parseable date; a non-date value renders as itself):

| Name | Renders |
|---|---|
| `date` | `hf-date-format` (`short`/`medium`/`long`/`full`/`iso`/`custom` with `hf-pattern`) |
| `time` | `hf-time-format` (`short`/`medium`/`long` and their `-24` variants); accepts a bare `HH:MM[:SS]` string |
| `datetime` | locale date-and-time |
| `relative` | "just now", "3 hours ago", "in 2 days" against the current instant |

**Text** (operate on the string form):

| Name | Renders |
|---|---|
| `uppercase` / `lowercase` / `capitalize` | case transforms |
| `trim` | surrounding whitespace removed |
| `truncate` | clipped to `hf-length` (default 50) with `hf-suffix` (default `…`) |

**Structured** (operate on the string form, with a masking default):

| Name | Renders |
|---|---|
| `phone` | `hf-phone-format` (`us`/`us-dash`/`us-dot`/`intl`); US 10-digit and `+1` 11-digit recognised, international normalised |
| `ssn` | masked `***-**-1234` by default; full form under `hf-mask="false"` |
| `creditcard` | masked `****-****-****-1234` by default; grouped full form under `hf-mask="false"` |

**Delegating**:

| Name | Renders |
|---|---|
| `smart` | type auto-detected from the value, then formatted (Section 7) |

A value that fails its family's parse guard (a numeric format on non-numeric text, a temporal format on an unparseable date) renders **as its own string form** — never as `NaN`, `Invalid Date`, `null`, or a thrown error. This total-fallback rule is normative.

### 5.2 Input-conversion names (`hf-type`)

`hf-type` converts the source value before formatting — cents to dollars, a Unix timestamp to a date, kilobytes to bytes. It is a closed vocabulary of its own:

| Group | Names | Converts |
|---|---|---|
| Currency | `cents`, `pennies` | integer minor units → major (÷100) |
| Percentage | `decimal`, `fraction`, `percentage`, `percent` | pass through (the `percent` formatter reads the scale) |
| Date | `date`, `iso`, `iso8601` | string → Date |
| | `unix`, `timestamp`, `epoch` | seconds → Date (×1000) |
| | `milliseconds`, `ms` | millis → Date |
| Duration | `seconds`/`sec`, `minutes`/`min`, `hours`/`hr` | → seconds |
| Filesize | `bytes`/`b`, `kilobytes`/`kb`, `megabytes`/`mb`, `gigabytes`/`gb` | → bytes |
| Number | `number`/`float`/`double`, `integer`/`int` | parse (int floors) |
| Text | `string`/`text`/`str` | identity string |
| Boolean | `boolean`/`bool` | truthy-word recognition (`true`/`1`/`yes`/`on`) |
| Structured | `object`/`obj`/`json`, `array`/`arr` | JSON parse (invalid → original value, event emitted) |
| Empty | `null`, `undefined` | the null / undefined value |
| Identity | `auto` (or absent) | no conversion |

An unknown `hf-type` renders the value unconverted and emits a diagnostic event (Section 7.3) — the same total-fallback discipline.

### 5.3 Options per type

Each option is read only by the formatters that declare it; an option irrelevant to the active type is ignored. The complete per-type option list (attribute name, key, coercion, default, owning types) is enumerated in the reference `README` and is the source the manifest (5.4) is generated from. The cross-cutting options are `hf-locale` (default `en-US`) and `hf-decimals` (default 2, overridden per type as noted in 5.1).

### 5.4 The declared vocabulary manifest

honest-format **declares** its vocabulary as data — the format-type set, the input-type set, and, per type, its allowed option attributes and any enumerated option values (the `hf-phone-format` set, the `hf-date-format` set). The manifest is emitted from the implementation as a build artifact, never scraped from source at check time. honest-check reads it and resolves every authored `hf-*` attribute value against it (HC-REF004): an `hf-format` naming no type, an `hf-type` naming no converter, or an enumerated option (`hf-phone-format="uk"`) naming no member is a dead reference and stops the gate. "Declared, never inferred": the manifest is the contract; the `switch` labels are an implementation detail the check never reads.

---

## 6. The Formatter Contract

### 6.1 Dispatch

`format(type, value, opts)` selects a formatter from a table keyed by format name, and `convert(value, inputType)` selects a converter from a table keyed by input-type name. Both tables are total in use because an absent key resolves to the fallback formatter (returns the string form) / identity converter, each emitting a diagnostic event. There is no discriminant branch; adding a format type is adding a table entry.

### 6.2 Purity

Every formatter is a pure function `(value, opts) → string`. No formatter reads the DOM, mutates its arguments, or performs I/O. The numeric and temporal parse guards are pure predicates applied before dispatch.

### 6.3 Totality

`format` returns a string for every input. Parse failure returns the string form of the (converted) value; unknown type returns the string form and emits a diagnostic. No path returns `null`/`undefined` or throws.

### 6.4 The one clock read

`relative` and any "now"-relative default are defined against the current instant. The instant is an **injected** input to the formatter, defaulting to the platform clock only at the DOM boundary — the pure core receives it as a parameter so its output is a pure function of (value, options, now). This keeps the formatter testable by the value oracle without stubbing a global clock.

---

## 7. Auto-detection (`hf-format="smart"`)

### 7.1 Detection

`detect(value) → { type, confidence }` matches the value against a table of typed patterns — `currency`, `percentage`, `phone`, `date`, `email`, `url`, `number` — each a regular expression plus a confidence score in 0–100. The highest-confidence match above the threshold wins. Detection is pure: same value, same result. The pattern table is data, extended by adding an entry.

### 7.2 Delegation

A detected type delegates to `format` (Section 6) — `smart` adds detection, not a second formatting path. `email` and `url` detection resolve to link/verbatim rendering defined in the reference; every other detected type is an existing format name.

### 7.3 Low confidence is an event, not an HTTP call

When the best match falls below the confidence threshold, honest-format **emits a diagnostic event** (the detected type, the confidence, the element's location) to honest-observe. It does not open an HTTP client, hold a request queue, or rate-limit — the telemetry transport genX's `smartx` carried inline is honest-observe's boundary, reached by emitting an event, exactly as every other module reports through observe. The detection core stays pure.

---

## 8. The DOM Binding Contract

### 8.1 Surfaces

The binding layer exposes: `scan(root)` — format every unprocessed element under `root`; `formatElement(el)` — format one element; `unformatElement(el)` — restore an element to its `hf-raw` source. These are the only functions that touch the DOM.

### 8.2 Idempotency

`formatElement` reads the source per Section 4.2, formats, and writes the display only if it differs from the current text — so re-formatting an already-correct element is a no-op and cannot loop. `hf-raw` preserves the source across re-formats; `unformatElement` restores it.

### 8.3 The re-scan predicate (normative)

`scan(root)` formats exactly the elements under `root` that are **unprocessed** by the Section 4.4 predicate — carry `hf-format`, lack `hf-raw`. It MUST NOT consult any in-memory "already seen" set to decide whether an element needs work. Consequence: content inserted after initial load (an HTMX swap, a manual `insertAdjacentHTML`) formats on the next scan, because the new nodes carry no `hf-raw`. A stale in-memory marker that survives node replacement is the defect of Section 9.2 and is prohibited by this predicate.

### 8.4 Observation

The binding subscribes to honest-DOM's shared observer bridge for added nodes and for `hf-*` attribute mutations, re-formatting the affected element. It does not construct its own `MutationObserver`. On subscription it performs one initial `scan(document)`.

---

## 9. Known-defect regressions

These two defects are recorded against the genX reference. The honest reference implementation fixes both, and each fix ships with the regression test named here (every bug fix requires a regression test).

### 9.1 `abbreviated` must honour explicit `hf-decimals`

`abbreviated` MUST format to the caller's `hf-decimals` when set (distinguishing an explicit `0` from an omitted option), defaulting to 1 only when omitted — consistent with `millions`/`billions`/`trillions`. Regression: `format('abbreviated', 915166064277, {decimals: 2, prefix: '$'}) === '$915.17B'`, and `{decimals: 0}` → `'$915B'`, and omitted → `'$915.2B'`. (Fixed in the genX source; encoded here so the rebuild cannot regress it.)

### 9.2 `scan` must process content added after initial load

Per Section 8.3, `scan` MUST re-process unprocessed nodes regardless of when they entered the DOM. Regression: after an initial `scan` completes, inserting `<span hf-format="abbreviated" hf-prefix="$" hf-decimals="2">31210137967</span>` and calling `scan` again MUST render `$31.21B` and set `hf-raw`; a second element outside the scanned subtree MUST remain unprocessed (subtree scoping holds).

---

## 10. Conformance

### 10.1 Conformance Levels

- **Level 1 — Formatter core.** `format` and `convert` are total over the declared vocabulary, pure, dispatch-table based, and match the reference-of-record outputs across the value oracle. `detect` is pure and threshold-correct.
- **Level 2 — Declared manifest.** The vocabulary manifest (5.4) is emitted as data and is complete: every format name, input-type name, and enumerated option value the formatters accept appears in it, and nothing else does. HC-REF004 resolves against it.
- **Level 3 — DOM binding.** The scan/format/unformat surfaces honour the processed-marker predicate (8.3), are idempotent (8.2), subscribe to the honest-DOM bridge (8.4), and pass both Section 9 regressions.

### 10.2 Conformance Suite

The cross-language test-of-record lives in the reference implementation and is registered in `specs/honest-conformance-suite.md`. It enumerates: every format type against representative and boundary values (including each family's parse-failure fallback), every input-type conversion, the enumerated option sets, the two Section 9 regressions, and the manifest completeness check (every accepted name is declared, every declared name is accepted).

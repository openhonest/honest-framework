# Honest Code principles → honest-check rule coverage

Maps each of the 20 principles in `specs/02-code-quality/honest-code-principles.md` to the rule(s) that enforce it. Keep this current when a principle or rule changes — it is the guard against a principle silently losing enforcement.

| # | Principle | Enforced by | Coverage |
|---|---|---|---|
| 1 | Dict-Lookup Polymorphism | HC-P001 | ✅ honest-check |
| 2 | Typed Dicts Over Classes | HC-P003, HC-P007, HC-P010 | ✅ honest-check |
| 3 | Pure Functions Over Methods | HC-P003, HC-P004 | ✅ honest-check |
| 4 | I/O at the Boundary | HC-P004, HC008 | ✅ honest-check |
| 5 | Flat Composition Over Inheritance | HC-P003, HC-OR001 | ✅ honest-check |
| 6 | DOM as State (DATAOS) | `localStorage` etc. via IO watch list (HC-P004); Redux/Zustand/MobX | ◐ client-side — full enforcement belongs to the JS impl / honest-DOM |
| 7 | HTML Attributes Over Imperative DOM Manipulation | `addEventListener` via HC-P011; querySelector/innerHTML | ◐ client-side — full enforcement belongs to the JS impl / honest-DOM |
| 8 | **Typed Exceptions at the Boundary** | **HC-P002** | ✅ honest-check (gap closed 2026-06-18) |
| 9 | SQL Over Application Caches | HC-P006 | ✅ honest-check |
| 10 | Pure Function Assertions Over Mocks | HC-P012 | ◑ honest-test (test-time) |
| 11 | Type Declarations Over Imperative Validation | HC-P005 | ✅ honest-check |
| 12 | Context Managers Over Instance State | HC-P007 | ✅ honest-check |
| 13 | Configuration as Parameters | HC-P007, HC-P004 (global-read) | ✅ honest-check |
| 14 | No Implicit Defaults | — | ✗ unenforced — no rule flags a parameter default |
| 15 | Simple Gherkin Steps Signal Honest Architecture | HC-P008 | ◑ honest-test (test-time) |
| 16 | Declarative Equivalents Over Framework Lifecycle Hooks | HC-P011 | ✅ honest-check |
| 17 | Strangler Pattern for Migration | — | n/a — migration process, not a code property |
| 18 | Dispatch Tables Close Open Input | HC-P001, HC-P018 | ✅ honest-check |
| 19 | Atomic Test-and-Set Over Check-Then-Act | — | ✗ unenforced — honest-persist §3 states the store criterion; no static rule reads a guard |
| 20 | References Resolve Statically | HC-REF001 to HC-REF005 | ✅ honest-check |

## Legend / notes

- **✅ honest-check** — enforced by a static rule in this module.
- **◑ honest-test** — enforced, but by a test-time rule honest-test owns (HC-P008/P012); present in the spec, pending that module.
- **◐ client-side** — a JavaScript/DOM concern. The Python server-side checker catches the parts that surface as I/O (`localStorage`) or lifecycle hooks (`addEventListener`); full enforcement (Redux/Zustand/MobX imports, querySelector/innerHTML) belongs to the JS implementation and honest-DOM, not the Python checker.
- **n/a** — principle 17 is a migration methodology, not a structural property of a single file; correctly has no rule.
- **✗ unenforced** — the principle is stated and no rule reads it. Principle 14 and principle 19 are both static properties of source, so both are candidates for a rule rather than permanent gaps.

## Status

Fifteen of the twenty principles are enforced: thirteen by honest-check, two by honest-test (mocks, gherkin). Two are owned by the JS and DOM layer (DATAOS, imperative DOM) and one is process guidance (strangler).

Two principles are stated and unenforced, and both are in scope. **No Implicit Defaults** (14) is decidable from the AST: a parameter with a default value in a non-boundary function. **Atomic Test-and-Set Over Check-Then-Act** (19) needs a rule that spots a read of a shared value followed by a write to it inside one function. Neither has a rule number yet. Until they do, this document is the only record that the gate does not cover them.

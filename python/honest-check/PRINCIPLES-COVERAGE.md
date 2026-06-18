# Honest Code principles → honest-check rule coverage

Maps each of the 16 principles in `principles/honest-code-principles.md` to the
rule(s) that enforce it. Keep this current when a principle or rule changes — it is
the guard against a principle silently losing enforcement.

| # | Principle | Enforced by | Coverage |
|---|---|---|---|
| 1 | Dict-Lookup Polymorphism | HC-P001 | ✅ honest-check |
| 2 | Typed Dicts Over Classes | HC-P003, HC-P007, HC-P010 | ✅ honest-check |
| 3 | Pure Functions Over Methods | HC-P003, HC-P004 | ✅ honest-check |
| 4 | I/O at the Boundary | HC-P004, HC008 | ✅ honest-check |
| 5 | Flat Composition Over Inheritance | HC-P003, HC-OR001 | ✅ honest-check |
| 6 | DOM as State (DATAOS) | `localStorage` etc. via IO watch list (HC-P004); Redux/Zustand/MobX | ◐ client-side — full enforcement belongs to the JS impl / honest-DOM |
| 7 | HTML Attributes over Imperative DOM | `addEventListener` via HC-P011; querySelector/innerHTML | ◐ client-side — full enforcement belongs to the JS impl / honest-DOM |
| 8 | **Typed Exceptions at the Boundary** | **HC-P002** | ✅ honest-check (gap closed 2026-06-18) |
| 9 | SQL Over Application Caches | HC-P006 | ✅ honest-check |
| 10 | Pure Function Assertions Over Mocks | HC-P012 | ◑ honest-test (test-time) |
| 11 | Type Declarations Over Imperative Validation | HC-P005 | ✅ honest-check |
| 12 | Context Managers Over Instance State | HC-P007 | ✅ honest-check |
| 13 | Configuration as Parameters | HC-P007, HC-P004 (global-read) | ✅ honest-check |
| 14 | Simple Gherkin Steps Signal Honest Architecture | HC-P008 | ◑ honest-test (test-time) |
| 15 | Declarative Equivalents over Lifecycle Hooks | HC-P011 | ✅ honest-check |
| 16 | Strangler Pattern for Migration | — | n/a — migration process, not a code property |

## Legend / notes

- **✅ honest-check** — enforced by a static rule in this module.
- **◑ honest-test** — enforced, but by a test-time rule honest-test owns (HC-P008/P012); present in the spec, pending that module.
- **◐ client-side** — a JavaScript/DOM concern. The Python server-side linter catches the parts that surface as I/O (`localStorage`) or lifecycle hooks (`addEventListener`); full enforcement (Redux/Zustand/MobX imports, querySelector/innerHTML) belongs to the JS implementation and honest-DOM, not the Python linter.
- **n/a** — principle 16 is a migration methodology, not a structural property of a single file; correctly has no rule.

## Status

Every principle that is a *static property of server-side Python code* is enforced
by honest-check. The remaining principles are owned by honest-test (mocks, gherkin)
or the JS/DOM layer (DATAOS, imperative DOM), or are process guidance (strangler).
There is no longer an unenforced, in-scope principle.

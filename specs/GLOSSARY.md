# Glossary — the Honest Framework standard

The specifications prefer plain language. A technical term appears in them only where a plain
phrase would lose needed precision, and **every such term is defined here, in plain words.**
If a term is not in this list, it should not be in the specs; if it is in the specs, it must be
here. This is the standard's register of earned vocabulary, maintained as the specs change.

Two kinds of term earn a place: words the framework coins for its own concepts (which a plain
phrase cannot replace without losing the concept), and the few general computing terms that are
genuinely shorter and clearer than their plain paraphrase. Everything else is written out in
plain language in the text itself.

---

## Words the framework coins

| Term | Plain meaning |
|---|---|
| **manifest** | The flat bag of named values that flows through a request — `{name: value}`. The typed input every step receives and passes on. |
| **recognizer** | A rule that looks at one input value and says which named kind it is, or says it matches nothing. |
| **vocabulary** | The named set of kinds an application declares — its list of recognizers. The application's set of allowed shapes. |
| **link** | One step in handling a request: a function that takes the manifest and returns it changed, or returns a fault. Marked as a boundary step when it is allowed to touch the outside world. |
| **chain** | An ordered list of steps the manifest flows through, stopping at the first fault. A chain is itself a step, so chains nest. |
| **guard** | A yes/no condition checked at the moment of a write, written as data (not code), that must hold for the write to happen. |
| **guarded mutation** | A write that checks its guard and changes the data in one all-or-nothing step, so the condition cannot become false between the check and the write. The only sanctioned way to change stored data. |
| **fault** | A reported problem, carried as plain data `{code, message, who-is-at-fault, detail}` — never thrown as an exception except at the outer edge. |
| **rejection** | An input that could not be recognized or placed, carried as data in the manifest — not an error that stops the program. |
| **slot** | The name a recognized value is stored under in the manifest. |
| **binding** | The table that says which recognized kind goes into which slot. |
| **boundary** | The edge of the program, and the only place a step may touch the outside world (read input, write output, read the clock, use the database). Everything inside is pure. |
| **pure (function/step)** | Same input always gives the same output; it reads and writes nothing outside what it is handed. |
| **mutator** | The one piece of code allowed to change a given piece of state. The rule: every declared piece of state has exactly one. |
| **event log** | The append-only record of everything that happened — the single source of truth that projections are built from. |
| **projection** | A derived view computed from the event log by a pure function (a dashboard, a count, a timeline). Recomputed from events, never stored as primary data. |
| **aggregate** | The single thing a stream of events is grouped under (one order, one account); events for the same aggregate are numbered in order. |
| **orphan** | A function with no declared role that nothing with a role can reach — so the test generator cannot reach it either (flagged HC-R001). |
| **poka-yoke** | The guiding rule: every framework decision must make some named kind of bug impossible to even write, or it does not earn its place. |
| **Set** | A finite, written-out list of allowed values for a kind — so every value can be listed and tested in full. (Capitalized to mark the framework concept, distinct from a general set.) |
| **state machine** | A lookup table that says, for each current condition and each event, what the next condition is. Plain data; looking up the next condition is a pure step. |
| **transition** | One row of a state machine: a (condition, event) pair and the condition it leads to. |
| **Verification First** | The build order rule: the checker is built and turned on before the code it governs, so no code that fails the framework's own gate ever enters the repository. |
| **conformance** | Meeting the standard. A conformance suite is the shared set of input/output cases an implementation must pass to count as correct. |
| **Big State** (the thing the framework refuses) | Hidden state, undifferentiated state, and more than one source of truth — the failure modes the framework will not let you express. |
| **DATAOS** | "DOM As The Authority On State" — the page itself holds the user's state; there is no separate copy of it in client-side code. |

## General computing terms kept for brevity

| Term | Plain meaning |
|---|---|
| **idempotent** | Doing it a second time changes nothing more than doing it once. |
| **serializable isolation** | The database runs overlapping transactions as if they had happened one at a time, in some order — no half-mixed results. |
| **TOCTOU** | "Time of check to time of use" — the gap between checking a condition and acting on it, during which the condition can change and the action become wrong. |
| **small-scope hypothesis** | Almost every bug of this kind already shows up in very small cases, so testing small cases finds it. |
| **deterministic** | Always gives the same result for the same inputs — no randomness, no dependence on the time or outside state. |
| **fold** | The pure function at the heart of a projection: it takes the running result and one event and returns the new running result (also the name of that field). |
| **monotonic** | Only ever increases, never goes back down. |
| **heuristic** | Best-effort, a rule of thumb — catches the common cases but is not guaranteed to catch every one. |
| **enumerate** | List out every case, one by one (used when a set of values is finite, so the full list is possible). |
| **exhaustive** | Covering every case, not a sample. |
| **adversarial neighbours** | The near-miss inputs around a valid value (one character changed, a look-alike letter, an added control character) that a correct recognizer must reject. |
| **atomic / all-or-nothing** | A step that either happens completely or not at all; no other transaction ever sees it half-done. |
| **provenance** | Where a value in a guard comes from — read inside the same all-or-nothing write, or earlier. The guard model uses this to rule out a stale-read class of bug (a value true when checked but false when used). |
| **write-skew** | Two transactions each read the same data and each make a change that is fine on its own, but together break a rule. Possible under weak isolation; prevented by serializable isolation. |

# Honest Framework: Conformance Suite Specification

**Version:** 0.1 (Draft)
**Date:** March 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## Purpose

This document specifies the conformance properties that every honest framework implementation must satisfy, regardless of language. The properties are stated as formal laws expressible in any property-based testing framework: QuickCheck (Haskell), PropEr (Erlang), Hypothesis (Python), fast-check (TypeScript), PropCheck (Elixir), or equivalent.

An implementation that satisfies all properties in this suite is conformant by definition. An implementation that fails any property is non-conformant regardless of how closely it follows the prose specification.

This document is the primary reference for the **FP Implementor persona**. It is also the authoritative source for the honest-check conformance rules enforced by `honest-check --conformance`.

---

## How to Read This Document

Each section covers one honest framework module. Within each section:

- **Laws** are formal properties. They must hold for all valid inputs.
- **Preconditions** are assumptions the property requires to be valid. If the precondition does not hold, the property is vacuously satisfied.
- **Implementation-defined** marks properties where the spec allows latitude. The property constrains the outcome, not the mechanism.
- **Mandatory** marks properties where no implementation latitude exists.

Laws are written in a pseudo-typed pseudo-code readable by any practitioner familiar with typed functional programming. The notation:

```
f : A → B         -- f takes A, returns B
∀ x : A           -- for all x of type A
∃ x : A           -- there exists x of type A
x ∈ S             -- x is a member of set S
x ∉ S             -- x is not a member of set S
f = g             -- f and g return equal values for all inputs
⊥                 -- bottom: error, exception, or undefined behavior
|S|               -- cardinality of set S
```

---

## Module 1: honest-type

### Background

honest-type is a runtime classification system. A vocabulary is a named set of recognizers. Each recognizer maps tokens (untyped strings or values) to typed names. The system classifies an incoming token by running it through the vocabulary's recognizers and returning the first match.

### Core Types

```
Token       -- an untyped input value (string, int, etc.)
TypeName    -- a declared name within a vocabulary
Vocabulary  -- a named collection of recognizers
Recognizer  -- Token → Maybe TypeName
Manifest    -- TypeName × Token  (a classified result)
Rejection   -- Token × Reason   (a failed classification)
```

### Laws

**Law HT-1: Classification membership**
If classify returns a result, that result is a declared name in the vocabulary.

```
∀ vocab : Vocabulary, token : Token
  classify(vocab, token) = Some(name) → name ∈ vocab_names(vocab)
```

*Mandatory.*

**Law HT-2: Classification exclusivity**
No token can be classified as two different types simultaneously.

```
∀ vocab : Vocabulary, token : Token
  classify(vocab, token) = Some(n) →
    ¬∃ m : TypeName, m ≠ n ∧ m ∈ all_matches(vocab, token)
```

*Mandatory. Vocabulary construction must detect and reject overlapping recognizers.*

**Law HT-3: Zero-drift**
The classification function is identical at static analysis time, test generation time, and runtime. There is no separate "test mode" or "strict mode."

```
classify_static  = classify_test  = classify_runtime
```

*Mandatory. This law cannot be tested by property-based testing — it must be verified by inspection of the implementation. An implementation that uses different code paths for different invocation contexts is non-conformant.*

**Law HT-4: Reserved word rejection**
Vocabulary construction must reject any member that collides with a framework reserved word.

```
∀ vocab : Vocabulary, name : TypeName
  name ∈ RESERVED_WORDS → vocab_construction(name) = ⊥
```

*Mandatory.*

**Law HT-5: Empty vocabulary rejection**
A vocabulary with no recognizers is non-conformant.

```
∀ vocab : Vocabulary
  |vocab_names(vocab)| = 0 → vocab_construction(vocab) = ⊥
```

*Mandatory.*

**Law HT-6: Unrecognized token behavior**
A token that matches no recognizer produces a Rejection, not a silent default or null.

```
∀ vocab : Vocabulary, token : Token
  all_matches(vocab, token) = ∅ →
    classify(vocab, token) = Rejection(token, "unrecognized")
```

*Mandatory. Silent defaults are non-conformant.*

**Law HT-7: Set recognizer totality**
For a vocabulary declared as a Set (a finite, listable set of values), every declared member must be recognizable.

```
∀ vocab : SetVocabulary, name : TypeName
  name ∈ vocab_names(vocab) →
    ∃ token : Token, classify(vocab, token) = Some(name)
```

*Mandatory. A declared type that no token can match is a dead type and must be detected at construction.*

**Law HT-8: Predicate recognizer purity**
Custom predicate recognizers must be pure functions. Same token, same result, always.

```
∀ pred : Recognizer, token : Token
  pred(token) = pred(token)   -- same input, same result
```

*Mandatory. The implementation cannot enforce this at construction time for arbitrary predicates, but conformance tests must document that impure predicates produce undefined behavior.*

---

## Module 2: honest-persist

### Background

honest-persist is a schema-first migration system. The developer declares the schema they want. The system computes the diff between the declared schema and the live database and produces a migration plan. There are no migration files, no migration history, no version chain.

### Core Types

```
Schema        -- a declared database structure (tables, columns, constraints)
LiveDB        -- the current state of a running database
MigrationPlan -- a sequence of operations transforming LiveDB toward Schema
Operation     -- a single atomic database change
```

### Laws

**Law HP-1: Convergence**
Applying a migration plan produced from a schema and a live database produces a database that conforms to the schema.

```
∀ schema : Schema, db : LiveDB
  apply(migrate(schema, db), db) conforms_to schema
```

*Mandatory.*

**Law HP-2: Idempotency**
Applying a migration plan to the resulting database produces an empty plan.

```
∀ schema : Schema, db : LiveDB
  let db' = apply(migrate(schema, db), db)
  migrate(schema, db') = empty_plan
```

*Mandatory. Running migration twice must be safe.*

**Law HP-3: History independence**
The migration plan depends only on the declared schema and the live database state. It does not depend on how the database reached its current state.

```
∀ schema : Schema, db1 db2 : LiveDB
  db1 conforms_to db2 → migrate(schema, db1) = migrate(schema, db2)
```

*Mandatory. This is the definitive break from migration file chains. An implementation that reads or writes migration history files is non-conformant.*

**Law HP-4: Empty plan on conformance**
If the live database already conforms to the declared schema, the migration plan is empty.

```
∀ schema : Schema, db : LiveDB
  db conforms_to schema → migrate(schema, db) = empty_plan
```

*Mandatory. Follows from HP-2 and HP-1 but stated explicitly for clarity.*

**Law HP-5: Non-destructive default**
The migration plan must not produce destructive operations (DROP COLUMN, DROP TABLE, DELETE) unless the implementation is explicitly configured to permit them.

```
∀ schema : Schema, db : LiveDB
  migrate(schema, db) contains destructive_operation →
    implementation is configured for destructive migrations
```

*Mandatory. Default behavior is additive only. Destructive migrations require explicit opt-in.*

**Law HP-6: Query purity**
Query functions are pure: same inputs, same outputs. No hidden state, no caching that changes observable results.

```
∀ query : Query, db : LiveDB
  execute(query, db) = execute(query, db)
```

*Mandatory. I/O is permitted (the function reads the database) but the result is determined entirely by the query and the database state.*

---

## Module 3: honest-features

### Background

honest-features is a runtime feature flag system. Flags are declared in a vocabulary dict with a finite set of valid states. Current state is ephemeral in-memory data. State changes happen via a signed API call. Downstream code dispatches on flag state via handler tables, never via conditionals.

### Core Types

```
FlagName      -- a declared feature flag identifier
State         -- a valid state for a flag (member of the flag's states set)
FlagVocab     -- FlagName → {states: Set[State], default: State}
FlagStore     -- FlagName → State  (current in-memory state)
HandlerTable  -- State → (Manifest → Manifest)
HMACRequest   -- {flag, state, timestamp, signature}
```

### Laws

**Law HF-1: State membership**
The current state of any flag is always a member of that flag's declared states set.

```
∀ store : FlagStore, vocab : FlagVocab, flag : FlagName
  flag ∈ vocab → store[flag] ∈ vocab[flag].states
```

*Mandatory. This must hold at all times, including immediately after startup and immediately after a state change.*

**Law HF-2: Default validity**
Every flag's default state is a member of its declared states set.

```
∀ vocab : FlagVocab, flag : FlagName
  vocab[flag].default ∈ vocab[flag].states
```

*Mandatory. Vocabulary construction must reject a default that is not in the states set.*

**Law HF-3: Initialization from defaults**
At startup, the flag store is initialized from the vocabulary defaults. No I/O is performed during initialization.

```
∀ vocab : FlagVocab, flag : FlagName
  initial_store[flag] = vocab[flag].default
```

*Mandatory. An implementation that reads environment variables, config files, or databases during flag store initialization is non-conformant.*

**Law HF-4: feature_state purity**
feature_state is a pure lookup. No I/O, no side effects, no logging.

```
∀ store : FlagStore, flag : FlagName
  feature_state(flag) = store[flag]   -- pure dict lookup
```

*Mandatory.*

**Law HF-5: Undeclared flag rejection**
feature_state raises an error (KeyError, panic, exception) for undeclared flag names. It does not return a default.

```
∀ store : FlagStore, vocab : FlagVocab, flag : FlagName
  flag ∉ vocab → feature_state(flag) = ⊥
```

*Mandatory. Silent defaults for undeclared flags are non-conformant.*

**Law HF-6: Handler table totality**
A handler table keyed on a flag's state must be defined for every state in that flag's declared states set.

```
∀ vocab : FlagVocab, flag : FlagName, table : HandlerTable
  (∀ state : State, state ∈ vocab[flag].states → state ∈ table)
```

*Mandatory. A handler table with a missing state produces ⊥ at dispatch time. honest-check rule HF002 enforces this statically.*

**Law HF-7: HMAC signature coverage**
The HMAC signature covers flag name, state, and timestamp jointly. A signature over any subset of these fields is non-conformant.

```
signature = HMAC(secret, concat(flag, ":", state, ":", timestamp))
```

*Mandatory.*

**Law HF-8: Replay window enforcement**
A toggle request with a timestamp outside the configured replay window must be rejected regardless of signature validity.

```
∀ req : HMACRequest
  |now() - req.timestamp| > REPLAY_WINDOW → reject(req)
```

*Mandatory. The replay window is configurable but must have a finite, positive value.*

**Law HF-9: Constant-time signature comparison**
Signature verification must use constant-time comparison. String equality comparison is non-conformant.

```
verify(expected, actual) = constant_time_compare(expected, actual)
```

*Mandatory. Timing attacks against string equality are a known vulnerability.*

---

## Module 4: honest-observe

### Background

honest-observe is the observability layer. It maintains an append-only event log. Events are emitted at boundaries automatically. The log is the source of truth for all observability data. Projections are pure functions that fold the log into derived read models.

### Core Types

```
Event         -- an immutable record of something that happened
EventLog      -- an append-only sequence of Events
Projection    -- EventLog → ReadModel
Boundary      -- a function decorated with @link or @catch_at_boundary
RequestId     -- a unique identifier correlating all events within one request
```

### Laws

**Law HO-1: Log immutability**
Events are never modified or deleted after being appended. The log is append-only.

```
∀ log : EventLog, event : Event
  append(log, event) = log ++ [event]
  -- no operation removes or modifies an existing event
```

*Mandatory.*

**Law HO-2: Projection purity**
Projections are pure functions. The same log produces the same read model.

```
∀ proj : Projection, log : EventLog
  proj(log) = proj(log)   -- same input, same result
```

*Mandatory. A projection that reads external state (database, clock, random) is non-conformant. Time-windowed projections must receive the window bounds as parameters.*

**Law HO-3: Projection composability**
Any projection can be derived from any subset of the event log without reading events outside that subset.

```
∀ proj : Projection, log : EventLog, sub : EventLog
  sub ⊆ log → proj(sub) is well-defined
```

*Mandatory. Projections must not assume they receive the complete log.*

**Law HO-4: Request correlation**
Every event emitted within the scope of a request carries the same request_id. Events from different requests carry different request_ids.

```
∀ e1 e2 : Event
  same_request(e1, e2) ↔ e1.request_id = e2.request_id
```

*Mandatory.*

**Law HO-5: Boundary emission**
Every boundary function (decorated with @link or @catch_at_boundary) emits at minimum one event: the boundary invocation event. This emission is automatic and does not require developer code.

```
∀ boundary : Boundary, invocation : Invocation
  execute(boundary, invocation) → event_emitted(boundary_invocation_event)
```

*Mandatory. An implementation that requires developer code to emit boundary events is non-conformant.*

**Law HO-6: Browser/server log unification**
Browser events and server events land in the same event log and share the same request_id namespace. No separate log exists for browser events.

```
∀ event : Event
  event.origin ∈ {"browser", "server"} ∧
  event.log = THE_EVENT_LOG
```

*Mandatory. An implementation that maintains separate browser and server logs is non-conformant.*

**Law HO-7: OTel as projection**
OpenTelemetry export is a projection of the event log. The projection produces OTel-formatted traces, metrics, and logs. The event log is not modified by OTel export.

```
otel_export : EventLog → OTelPayload
-- is a pure projection, not a side-effecting sink
```

*Mandatory. An implementation that writes directly to an OTel collector without going through the event log is non-conformant for framework events.*

---

## Module 5: honest-test

### Background

honest-test generates test cases from type declarations rather than making developers list them out by hand. For finite Sets (vocabularies), it generates a test case for every member. For predicates, it generates boundary and edge cases. The result is a test suite that is complete by construction for all finite type domains.

### Core Types

```
TestCase      -- a (input, expected_output) pair
TestSuite     -- a collection of TestCases
Vocabulary    -- the honest-type vocabulary used as the generation source
Coverage      -- the fraction of declared types exercised by a test suite
```

### Laws

**Law HTest-1: Exhaustive coverage for Set vocabularies**
For a vocabulary declared as a finite Set, honest-test generates at least one test case per declared member.

```
∀ vocab : SetVocabulary
  ∀ name : TypeName, name ∈ vocab_names(vocab) →
    ∃ tc : TestCase ∈ generate(vocab), tc.expected = name
```

*Mandatory. A generated test suite that fails to exercise any declared member is non-conformant.*

**Law HTest-2: No test case exercises an undeclared type**
Generated test cases only assert outcomes that are declared in the vocabulary.

```
∀ vocab : Vocabulary, tc : TestCase ∈ generate(vocab)
  tc.expected ∈ vocab_names(vocab) ∪ {Rejection}
```

*Mandatory.*

**Law HTest-3: Test isolation**
Each generated test case is independent. The outcome of one test case does not affect the outcome of another.

```
∀ tc1 tc2 : TestCase ∈ generate(vocab)
  run(tc1) has no side effect observable by run(tc2)
```

*Mandatory. An implementation that shares mutable state between test cases is non-conformant.*

**Law HTest-4: Determinism**
Given the same vocabulary, honest-test generates the same test suite on every invocation.

```
∀ vocab : Vocabulary
  generate(vocab) = generate(vocab)
```

*Mandatory. Random or timestamp-seeded test generation is non-conformant for the core suite. Property-based supplemental tests may use seeds.*

**Law HTest-5: Rejection coverage**
honest-test generates at least one test case asserting that an unrecognized token produces a Rejection.

```
∀ vocab : Vocabulary
  ∃ tc : TestCase ∈ generate(vocab),
    tc.expected = Rejection
```

*Mandatory.*

**Law HTest-6: Handler table coverage (honest-features integration)**
For every handler table keyed on a feature flag's states, honest-test generates one test case per state.

```
∀ vocab : FlagVocab, flag : FlagName, table : HandlerTable
  ∀ state : State, state ∈ vocab[flag].states →
    ∃ tc : TestCase ∈ generate_for_flag(flag, table),
      tc.flag_state = state
```

*Mandatory.*

---

## Module 6: honest-check

### Background

honest-check is the static verification layer. It reads source files, walks abstract syntax trees, and reports violations of honest framework structural rules without executing application code.

### Core Types

```
Diagnostic    -- {rule_id, severity, file, line, message}
Severity      -- Error | Warning | Info
RuleSet       -- a collection of rules to enforce
```

### Laws

**Law HC-1: No execution**
honest-check never executes application code. All analysis is static.

```
∀ rule : Rule, source : SourceFile
  apply(rule, source) requires no execution of source
```

*Mandatory.*

**Law HC-2: Determinism**
Given the same source file and rule set, honest-check produces the same diagnostics on every invocation.

```
∀ rules : RuleSet, source : SourceFile
  check(rules, source) = check(rules, source)
```

*Mandatory. An implementation that produces different diagnostics for the same input is non-conformant.*

**Law HC-3: Severity monotonicity**
If a file produces an Error diagnostic, it also produces all Warning and Info diagnostics for the same violation. Diagnostics are not suppressed by higher-severity findings.

```
∀ source : SourceFile, rule : Rule
  produces_error(source, rule) →
    all diagnostics for source are reported
```

*Mandatory.*

**Law HC-4: No false negatives on mandatory rules**
For every mandatory rule, if a violation exists in the source, honest-check reports it. Mandatory rules may not be suppressed by configuration.

```
∀ source : SourceFile, rule : MandatoryRule
  violation_exists(source, rule) → rule ∈ check(rules, source).diagnostics
```

*Mandatory.*

**Law HC-5: Cross-language rule equivalence**
The rule algorithms defined in this spec produce equivalent diagnostics regardless of the target language implementation. A Python source file and an equivalent Ruby source file violating the same rule produce diagnostically equivalent results.

```
∀ rule : CrossLanguageRule, py_source ruby_source : SourceFile
  semantically_equivalent(py_source, ruby_source) →
    equivalent_diagnostics(check(rule, py_source), check(rule, ruby_source))
```

*Mandatory for cross-language minimum rules. Language-specific rules are exempt.*

---

## Module 7: I/O Without the Ick

### Background

Every experienced developer knows the feeling. You are three functions deep into what should be a pure computation and you find a database call. Or a clock read. Or an HTTP request. The ick: I/O where it does not belong, invisible until it causes a problem.

Every experienced FP developer knows I/O belongs at the boundary. In every codebase they have built, this is discipline: they decide to put I/O at the edges. Nothing stops them from putting it anywhere else.

Honest framework eliminates the ick structurally. I/O at the boundary is not a convention. It is an architectural constraint enforced by the framework itself. Putting I/O inside a pure function is not bad practice. It is a static error.

The boundary is the only place where:
- HTTP requests enter and responses leave
- Database queries execute
- Events are emitted to honest-observe
- External services are called
- Time is read
- Random values are generated

Everything inside the boundary is a pure function. It takes data in. It returns data out. It has no access to I/O primitives. Not by convention. By construction.

### How this is achieved

The `@link` decorator is the boundary marker. A function decorated with `@link` is permitted to perform I/O. A function not decorated with `@link` is not. honest-check enforces this statically: any I/O call (database query, HTTP call, file read, clock read) inside a non-linked function is a violation.

The chain is the unit of boundary-scoped execution. A chain is a sequence of links. The chain executes at the boundary. Its inputs are the request manifest (pure data). Its output is the response manifest (pure data). Inside the chain, pure functions compose freely. I/O happens only in links.

```
Request → [Boundary: @link → pure → pure → @link] → Response
                ↑                                ↑
              I/O permitted              I/O permitted
                         ↑
                  pure functions only
```

### Why this is foreign to FP practitioners

In Haskell, the IO monad makes I/O explicit in the type system. But it does not prevent you from threading IO through your entire call stack. A function that returns `IO a` can call anything. The type system tells you I/O is happening; it does not tell you it is in the wrong place.

In Erlang, processes are the boundary. I/O happens in process message handlers. But nothing stops you from calling a database from inside a pure computation.

Honest framework's boundary enforcement is stronger than either: it is positional (I/O belongs in links, not functions), structural (the chain architecture makes the position explicit), and statically verified (honest-check flags violations before the code runs).

The FP practitioner's instinct — IO monad, effect system, free monad — is the right instinct. Honest framework makes that instinct into a hard architectural rule.

### Formal laws

**Law IO-1: Boundary containment**
All I/O operations occur inside functions decorated as boundary links. No I/O operation occurs inside a pure function.

```
∀ f : PureFunction
  execute(f) performs no I/O
```

*Mandatory. Verified statically by honest-check. An implementation that permits I/O inside pure functions is non-conformant.*

**Law IO-2: Link purity of output**
A link function's output is determined entirely by its input manifest and the results of its I/O operations. It has no hidden dependencies on global mutable state.

```
∀ link : Link, manifest : Manifest, world : WorldState
  execute(link, manifest, world) = f(manifest, world)
  -- no hidden state beyond manifest and world
```

*Mandatory.*

**Law IO-3: Chain boundary scope**
I/O performed inside a chain is scoped to that chain's execution. No I/O result leaks into the pure function layer as mutable state.

```
∀ chain : Chain
  I/O results from chain are returned as manifest data, not stored as side effects
```

*Mandatory.*

**Law IO-4: Time and randomness at the boundary**
Clock reads and random value generation are I/O operations and must occur in link functions. Pure functions that require time or randomness must receive them as parameters.

```
∀ f : PureFunction
  f does not call now() or random()
  -- these are passed in as parameters from a link
```

*Mandatory. A pure function that reads the clock internally is non-conformant.*

### Property-based test skeleton

**IO-1: Boundary containment (static verification)**
```
property "pure functions perform no I/O" {
  -- This law requires static analysis, not runtime testing.
  -- The test is: does honest-check flag I/O calls inside
  -- non-link functions?
  source = arbitrary(SourceFile containing PureFunctions with I/O calls)
  diagnostics = honest_check(source)
  assert HC-IO001 ∈ diagnostics
}
```

**IO-4: Time as parameter**
```
property "pure function with time parameter is deterministic" {
  f    = arbitrary(PureFunction accepting timestamp : DateTime)
  t    = arbitrary(DateTime)
  args = arbitrary(Manifest)
  assert f(args, t) = f(args, t)
}
```

### Implementation note for FP languages

In Haskell, Law IO-1 can be enforced at the type level: link functions return `IO a`, pure functions return `a`. honest-check for Haskell verifies that no `IO` action appears in the return type of a non-link function.

In Erlang, link functions are message handler callbacks. Pure functions are plain functions called from handlers. The boundary is the process boundary.

In Clojure, link functions are wrapped with a `deflink` macro that registers them as boundary-permitted. honest-check walks the namespace and flags `io!` calls outside registered links.

The mechanism is implementation-defined. The outcome — I/O only at boundaries — is mandatory.

---

## Conformance Levels

An implementation declares a conformance level by asserting that all laws at that level and below hold.

| Level | Laws required |
|---|---|
| **Core** | HT-1, HT-3, HT-4, HT-5, HT-6, HP-1, HP-2, HP-3, HP-4, HP-5, HF-1, HF-2, HF-3, HF-4, HF-5, HF-7, HF-8, HF-9, IO-1, IO-2, IO-4 |
| **Full** | Core + HT-2, HT-7, HT-8, HP-6, HF-6, HO-1, HO-2, HO-4, HO-5, HO-6, HTest-1, HTest-2, HTest-3, HTest-4, HTest-5, IO-3 |
| **Complete** | Full + HO-3, HO-7, HTest-6, HC-1, HC-2, HC-3, HC-4, HC-5 |

---

## Property-Based Test Skeletons

The following skeletons are provided to help implementors translate the laws into property-based tests in their framework of choice. The skeletons use a language-neutral pseudo-code. Translate to QuickCheck, PropEr, Hypothesis, fast-check, or equivalent.

### HT-1: Classification membership

```
property "classify result is always a declared name" {
  vocab  = arbitrary(Vocabulary)
  token  = arbitrary(Token)
  result = classify(vocab, token)
  if result is Some(name):
    assert name ∈ vocab_names(vocab)
}
```

### HT-2: Classification exclusivity

```
property "no token classified as two types" {
  vocab  = arbitrary(Vocabulary)
  token  = arbitrary(Token)
  matches = all_matches(vocab, token)
  assert |matches| ≤ 1
}
```

### HP-1: Convergence

```
property "apply(migrate(schema, db)) conforms to schema" {
  schema = arbitrary(Schema)
  db     = arbitrary(LiveDB)
  plan   = migrate(schema, db)
  db'    = apply(plan, db)
  assert db' conforms_to schema
}
```

### HP-2: Idempotency

```
property "migrate after apply produces empty plan" {
  schema = arbitrary(Schema)
  db     = arbitrary(LiveDB)
  db'    = apply(migrate(schema, db), db)
  assert migrate(schema, db') = empty_plan
}
```

### HF-1: State membership

```
property "flag state is always in declared states" {
  vocab = arbitrary(FlagVocab)
  store = initialize(vocab)
  flag  = arbitrary_element(vocab.keys)
  assert store[flag] ∈ vocab[flag].states
}
```

### HF-5: Undeclared flag rejection

```
property "undeclared flag raises error" {
  vocab      = arbitrary(FlagVocab)
  store      = initialize(vocab)
  undeclared = arbitrary(FlagName) where undeclared ∉ vocab
  assert feature_state(undeclared) = ⊥
}
```

### HO-2: Projection purity

```
property "same log produces same projection" {
  proj = arbitrary(Projection)
  log  = arbitrary(EventLog)
  assert proj(log) = proj(log)
}
```

### HTest-1: Exhaustive Set coverage

```
property "every declared type is exercised by at least one test case" {
  vocab = arbitrary(SetVocabulary)
  suite = generate(vocab)
  ∀ name ∈ vocab_names(vocab):
    assert ∃ tc ∈ suite, tc.expected = name
}
```

---

## Appendix: Laws Not Testable by Property-Based Testing

The following laws must be verified by code inspection rather than property-based testing. They are stated here for completeness and are mandatory regardless.

| Law | Reason not property-testable |
|---|---|
| HT-3 (zero-drift) | Requires comparing code paths across invocation contexts, not observable from outputs alone |
| HC-1 (no execution) | Requires inspecting the implementation mechanism, not observable from outputs |
| HO-6 (unified log) | Requires inspecting log destinations, not observable from event content alone |

These laws must be part of the implementation review checklist submitted with any conformance claim.

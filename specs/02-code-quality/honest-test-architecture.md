# honest-test: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** March 15, 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-test is the **auto-generated verification layer** of the Honest Framework. It runs the complete test suite that honest-check has confirmed is generatable from the code's declarations.

The pipeline is two-stage and unidirectional:

1. **honest-check** asks *can the complete auto-generated test suite be generated from this code?* If no, the code is dishonest and rejected at pre-commit. No suite exists to run.
2. **honest-test** runs the auto-generated suite. If any test fails, the code is buggy and rejected.

Developers write **no test code** — the vocabulary, link, recognizer, state machine, invariant, and BDD-feature declarations are the test specification. Auto-generation derives every test case, every property check, every invariant assertion, every permutation. *Defining is testing.*

honest-test has three distinct responsibilities, all auto-generated from declarations:

1. **Classification and chain tests** — every vocabulary member is fed through every chain that consumes it. Every valid output of link N is fed to link N+1 and confirmed accepted. Exhaustive for bounded vocabularies; boundary-sampled for predicates (Fibonacci, length enumeration).

2. **Honesty properties** — for every `@link`, the harness verifies purity (same input, same output, twice), mutation isolation (manifest unchanged), idempotency (same chain, same result), and boundary isolation (no I/O or non-determinism outside declared boundaries). Every `@recognizer` is adversarially probed (edit-distance-1, Unicode confusables, control characters, length-extension). Every `@helper` is exercised transitively.

3. **State machine enumeration** — every (state, event) pair is exercised; every declared invariant is checked on every reachable post-state; every K-step event sequence (default K=4) is enumerated with invariant checks at every intermediate state.

4. **BDD features** — developer-authored Gherkin `.feature` files at the system-requirement level. Scaffolding is auto-generated from `@link` declarations; the developer writes only the `.feature` files themselves. BDD covers semantic correctness of multi-step user journeys — what auto-generation of properties alone cannot cover.

All four share one runner and one coverage model. Coverage is **structural, not audited**: HC-R001 (enforced in honest-check) guarantees every function has a declared role or is reachable from one, which guarantees the auto-generated suite reaches every function. If auto-generation completes, coverage is complete by construction.

### 1.1 Relationship to Other Specs

The test generation algorithms in this document were originally specified in `honest-type-architecture.md` section 13. That document now defers to this one as the canonical reference. `honest-type-architecture.md` section 14 (conformance suite) remains in that document; it is the cross-language contract for implementing `classify()` and is not honest-test's concern.

honest-test depends on honest-check's declaration graph. It reads the same vocabulary, binding, link, and chain declarations that honest-check analyzes statically, and exercises them dynamically.

### 1.2 What honest-test Covers

- Auto-generated classification tests derived from vocabulary declarations
- Auto-generated chain contract tests derived from link declarations
- Honesty tests: purity, mutation detection, idempotency, boundary isolation
- State machine exhaustive testing
- honest-persist query contract tests
- component isolation tests
- Developer-authored BDD tests via Gherkin

### 1.3 What honest-test Does Not Cover

- Static structure: vocabulary overlap, chain type mismatches, unreachable states — these belong in honest-check
- Performance benchmarking — use language-native profiling tools
- Security — honest-auth handles security verification
- UI correctness — component rendering correctness is a separate concern

---

## 2. Predicate Classification

Before generating test cases, honest-test classifies each predicate by analyzing its AST. The classification determines the generation strategy.

| Class | Detection (AST) | Strategy |
|---|---|---|
| **Numeric** | Contains `int(s)`, `float(s)`, numeric comparison | Fibonacci sequence |
| **Length-bounded** | Contains `len(s) ==` or `len(s) <` fixed value | Enumerate valid lengths |
| **Character-class** | Contains `s.isdigit()`, `s.isalpha()`, `s.isupper()` | Enumerate character classes |
| **External lookup** | Calls function not in codebase | Programmer-supplied via `honest-test.yaml` |
| **Composite** | Calls function defined in codebase | Recurse into callee AST |
| **Catch-all** | Accepts nearly all inputs | Rejected at vocabulary construction (HC011) |

External library calls are the programmer's responsibility. honest-test emits a warning and skips generation for that predicate unless test values are supplied in `honest-test.yaml`. Using external library functions in recognizers is strongly discouraged.

Composite predicates that call codebase-defined functions are followed recursively. The AST walk descends into the callee at any depth within the codebase.

---

## 3. Auto-Generated Tests

### 3.1 Principle

The vocabulary declaration is the test specification. The programmer has already declared exactly what valid input looks like. honest-test reads that declaration and generates every valid combination automatically. No additional developer input is required.

This is the same relationship Swagger has to API testing: the API description generates the test cases. The declaration is the source of truth for both the runtime behavior and the test suite.

### 3.2 Set Enumeration

For Set-based recognizers, honest-test enumerates every member. For a vocabulary with multiple Sets, it generates the full cartesian product.

```
FUNCTION enumerate_sets(vocabulary):
    set_types ← { name: list(members)
                  FOR (name, recog) IN vocabulary.base_types
                  IF recog is a Set }

    RETURN product(set_types.values())
```

For `format_name(5) × currency_code(150) × style_name(4)` = 3,000 test cases. All run. No sampling.

Maybe slots add one case: `Nothing`. A maybe Set of 4 members = 5 test cases.

### 3.3 Numeric Predicate Generation

For predicates classified as Numeric, generate values from the Fibonacci sequence in both directions from zero, up to a configurable limit.

```
FUNCTION fibonacci_sequence(limit):
    seq ← [0, 1]
    WHILE seq[-1] < limit:
        seq.APPEND(seq[-2] + seq[-1])

    positive ← seq
    negative ← [-x FOR x IN seq IF x > 0]
    RETURN negative + positive

DEFAULT_LIMIT = 1_000_000
```

The Fibonacci sequence provides logarithmically distributed values with natural density at small numbers and increasing spacing at large numbers. This distribution probes boundary conditions effectively without exhaustive enumeration.

For floats, divide each Fibonacci number by 100: `0.0, 0.01, 0.01, 0.02, 0.03, 0.05, 0.08...`

**Configurable via `honest-test.yaml`:**

```yaml
predicates:
  order_amount:
    strategy: fibonacci
    limit: 1_000_000_000
    negative: false
  tax_rate:
    strategy: fibonacci
    float: true
    limit: 1.0
```

### 3.4 Length-Bounded Predicate Generation

For predicates that constrain string length, generate a string at every valid length, plus the boundary lengths just outside the valid range — which must be rejected. Boundary testing is symmetric: probe one under the minimum and one over the maximum, not only one over.

The constraint is read from the comparison **operator**, not just a bound, so `==` (a single exact length) is distinguished from `<=` (a range up to a maximum):

| Predicate | (min, max) | Valid lengths | Invalid (boundary) |
|---|---|---|---|
| `len(s) == 5` | (5, 5) | 5 | 4, 6 |
| `len(s) <= 8` | (1, 8) | 1..8 | 9 |
| `len(s) < 8` | (1, 7) | 1..7 | 8 |
| `len(s) >= 3` (no max) | (3, ∞) | unbounded — falls to supplied-values |
| `3 <= len(s) <= 8` | (3, 8) | 3..8 | 2, 9 |

```
FUNCTION enumerate_lengths(predicate_ast):
    min_len, max_len ← extract_length_bounds(predicate_ast)   // from the operator(s)
    chars            ← "abcdefghijklmnopqrstuvwxyz0123456789"

    valid   ← [string_of_length(n, chars) FOR n IN range(min_len, max_len + 1)]

    invalid ← [string_of_length(max_len + 1, chars)]          // one over — must be rejected
    IF min_len > 1:                                           // one under, when it is non-empty
        invalid ← invalid + [string_of_length(min_len - 1, chars)]
    // min_len == 1 -> one under is the empty string, already an empty_token rejection (section 9.3)

    RETURN valid, invalid
```

A pure lower bound with no maximum (`len(s) >= 3` alone) is unbounded above and not finitely enumerable; it falls to supplied-values (section 3.6), like any predicate this strategy cannot fully generate. `string_of_length(n, chars)` produces a length-`n` string by repeating `chars` as needed, so lengths beyond `len(chars)` are still generated.

### 3.5 Adversarial Input Generation

For every Set member, honest-test generates adversarial neighbors across five classes. Every neighbor must produce a rejection. A neighbor that is accepted represents a vocabulary overlap, a case-sensitivity bug, a normalization flaw, or an encoding vulnerability. The adversarial set is **conformance-tested** — every neighbor class below must be exercised by a conformant implementation.

```
FUNCTION adversarial_neighbors(value):
    RETURN deduplicate(
        edit_distance_1(value) +
        unicode_confusables(value) +
        control_characters(value) +
        length_extensions(value) +
        encoding_variants(value)
    ) - {value}
```

**Class 1: Edit-distance-1 neighbors.** Deletions, insertions, substitutions, case variations, whitespace variations.

```
FUNCTION edit_distance_1(value):
    results ← []
    chars   ← list(value)
    alpha   ← "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    // Deletions
    FOR i IN range(len(chars)):
        results.APPEND(join(chars[:i] + chars[i+1:]))

    // Insertions
    FOR i IN range(len(chars) + 1):
        FOR c IN alpha:
            results.APPEND(join(chars[:i] + [c] + chars[i:]))

    // Substitutions
    FOR i IN range(len(chars)):
        FOR c IN alpha:
            IF c ≠ chars[i]:
                results.APPEND(join(chars[:i] + [c] + chars[i+1:]))

    // Case variations
    results.APPEND(value.lower())
    results.APPEND(value.upper())
    results.APPEND(value.title())

    // Whitespace variations
    results.APPEND(" " + value)
    results.APPEND(value + " ")
    IF len(value) >= 2:
        results.APPEND(value[0] + " " + value[1:])

    RETURN results
```

**Class 2: Unicode confusables.** Visually-similar characters from different Unicode blocks that an unwary string comparison treats as distinct but a reader (or an OCR-augmented attacker) reads as the original. Every ASCII character in `value` is substituted, one position at a time, with a known confusable.

```
FUNCTION unicode_confusables(value):
    // Source: Unicode Confusables (Technical Standard #39), curated subset
    confusable_map ← {
        'a': ['а' (Cyrillic), 'ɑ' (IPA), 'ａ' (fullwidth), '𝐚' (mathematical)],
        'e': ['е' (Cyrillic), 'ē' (macron), 'ｅ' (fullwidth)],
        'o': ['о' (Cyrillic), '0' (digit), 'ο' (Greek omicron), 'ｏ' (fullwidth)],
        'i': ['і' (Cyrillic), 'ӏ' (Cyrillic palochka), '1' (digit), 'l' (lowercase L)],
        // ... full list in honest-test-conformance/confusables.json
    }

    results ← []
    FOR i IN range(len(value)):
        c ← value[i]
        IF c IN confusable_map:
            FOR replacement IN confusable_map[c]:
                results.APPEND(value[:i] + replacement + value[i+1:])

    // Also: full homoglyph replacement (every replaceable char at once)
    full_replacement ← value
    FOR i IN range(len(value)):
        IF value[i] IN confusable_map:
            full_replacement ← replace(full_replacement, value[i], confusable_map[value[i]][0])
    IF full_replacement ≠ value:
        results.APPEND(full_replacement)

    RETURN results
```

**Class 3: Control characters.** Injection of C0/C1 control codes that reveal parsers that strip or mishandle them instead of rejecting.

```
FUNCTION control_characters(value):
    // C0 controls (0x00-0x1F) + DEL (0x7F) + C1 controls (0x80-0x9F)
    // Plus bidirectional overrides that hide content visually
    injection_set ← {
        '\x00',      // NULL — many C-backed parsers truncate here
        '\x08',      // BACKSPACE
        '\x09',      // TAB
        '\x0a',      // LINE FEED
        '\x0d',      // CARRIAGE RETURN
        '\x1b',      // ESC — start of ANSI escape sequences
        '\x7f',      // DEL
        '\u200b',    // ZERO WIDTH SPACE — invisible
        '\u200e',    // LEFT-TO-RIGHT MARK
        '\u200f',    // RIGHT-TO-LEFT MARK
        '\u202a',    // LEFT-TO-RIGHT EMBEDDING
        '\u202b',    // RIGHT-TO-LEFT EMBEDDING
        '\u202c',    // POP DIRECTIONAL FORMATTING
        '\u202d',    // LEFT-TO-RIGHT OVERRIDE
        '\u202e',    // RIGHT-TO-LEFT OVERRIDE — hides appended content
        '\ufeff',    // ZERO WIDTH NO-BREAK SPACE (BOM)
    }

    results ← []
    FOR c IN injection_set:
        // Prepend
        results.APPEND(c + value)
        // Append
        results.APPEND(value + c)
        // Insert at midpoint
        mid ← len(value) // 2
        results.APPEND(value[:mid] + c + value[mid:])

    RETURN results
```

**Class 4: Length extensions.** Inputs padded to sizes that expose fixed-buffer assumptions, field-length confusion, and downstream truncation.

```
FUNCTION length_extensions(value):
    RETURN [
        value * 10,                    // 10x
        value * 100,                   // 100x
        value * 1000,                  // 1000x — shake out any O(n²)
        value + ("A" * 65535),         // near-uint16 boundary
        value + ("A" * 65536),         // at uint16 boundary
        value + ("A" * 1048575),       // near-1MB
    ]
```

**Class 5: Encoding variants.** Values re-encoded or mis-encoded at the byte level. Targets recognizers that accept after normalization rather than rejecting malformed inputs.

```
FUNCTION encoding_variants(value):
    results ← []
    // UTF-16 byte-order-mark prefix
    results.APPEND("\ufeff" + value)
    // Overlong UTF-8 encoding of ASCII — e.g., 'A' as C1 81 — rejectable
    // (implementation emits the raw bytes; the classifier decodes)
    results.APPEND(overlong_utf8(value))
    // Double-encoded (%25 → %, then the literal %)
    results.APPEND(percent_encode(percent_encode(value)))
    // Mixed encoding: half UTF-8, half latin-1
    results.APPEND(mixed_encoding(value))
    // Whitespace normalization attacks
    results.APPEND(value.replace(' ', '\xa0'))   // non-breaking space
    results.APPEND(value.replace(' ', '\u2028')) // LINE SEPARATOR
    RETURN results
```

**Conformance.** The reference vocabulary for each class is published in the hub repository at `honest/honest-test-conformance/adversarial/{class}.json`. A conformant implementation must exercise every entry in the reference vocabulary; failing to reject any listed neighbor is a recognizer bug and a conformance failure.

### 3.6 Programmer-Supplied Test Values

For predicates that cannot be analyzed (external lookups, context-dependent), programmers supply test values in `honest-test.yaml`:

```yaml
predicates:
  customer_id:
    valid:
      - "CUST-00001"
      - "CUST-99999"
    invalid:
      - "CUST-0"
      - "cust-00001"
      - "CUST-AAAAA"
    strategy: supplied_only
```

honest-test runs supplied valid values and confirms they are accepted. Runs supplied invalid values and confirms they are rejected. Reports missing YAML for external-lookup predicates as a warning.

---

## 4. Honesty Tests

Honesty tests verify that code behaves according to Honest Code principles at runtime. They are derived entirely from `@link` declarations and first principles. The developer writes nothing additional.

### 4.1 Purity Verification

A pure function must return the same output for the same input, always.

```
FUNCTION verify_purity(link, test_manifest):
    result_1 ← link(test_manifest)
    result_2 ← link(test_manifest)

    IF result_1 ≠ result_2:
        EMIT failure("non_deterministic",
            f"Link '{link.name}' produced different results on identical input")
```

Links declared `boundary=True` are exempt. I/O at a declared boundary is expected to have side effects.

### 4.2 Mutation Detection

A pure function must not modify its input manifest.

```
FUNCTION detect_mutation(link, test_manifest):
    snapshot_before ← deep_copy(test_manifest)
    result          ← link(test_manifest)
    snapshot_after  ← test_manifest

    IF snapshot_before ≠ snapshot_after:
        diff ← diff(snapshot_before, snapshot_after)
        EMIT failure("manifest_mutated",
            f"Link '{link.name}' modified its input manifest: {diff}")
```

### 4.3 Idempotency

The same chain run twice with the same manifest must produce the same result.

```
FUNCTION test_idempotency(chain, test_manifest):
    result_1 ← execute_chain(chain, test_manifest)
    result_2 ← execute_chain(chain, deep_copy(test_manifest))

    IF result_1 ≠ result_2:
        EMIT failure("not_idempotent",
            f"Chain '{chain.name}' produced different results on identical input")
```

Chains containing `boundary=True` links are exempt from idempotency testing.

### 4.4 Boundary Isolation

Links not declared `boundary=True` must not perform I/O. honest-test instruments known I/O calls for detection.

```
FUNCTION verify_boundary_isolation(link, test_manifest):
    WITH io_monitor():
        result ← link(test_manifest)

    IF io_monitor.detected_io AND NOT link.boundary:
        EMIT warning("io_detected",
            f"Link '{link.name}' performed I/O. Add boundary=True if intentional.")
```

`io_monitor()` patches known I/O functions to detect calls without executing them.

### 4.5 Non-Determinism Detection

Links not declared `boundary=True` must not access non-deterministic sources. The watch list is the same exhaustive, conformance-tested list published in honest-check (HC008 section) — `NONDETERMINISTIC_WATCH_LIST` per language. Both tools trap the same entries; both are verified by the same conformance fixtures.

```
FUNCTION verify_determinism(link, test_manifest):
    // Reference the published list from honest-check HC008.
    // Implementations MUST load this list from the hub at
    //   honest/honest-check-conformance/watch-lists/{language}.json
    // and trap every entry at runtime.

    WITH call_monitor(NONDETERMINISTIC_WATCH_LIST):
        result ← link(test_manifest)

    IF call_monitor.detected_calls AND NOT link.boundary:
        EMIT warning("nondeterminism_detected",
            f"Link '{link.name}' called {call_monitor.calls}. "
            "Non-deterministic calls belong at boundaries.")
```

**The runtime trap is stricter than the static check.** honest-check HC008 is AST-based and cannot detect non-determinism that enters through an attribute chain or dynamic dispatch (e.g., `getattr(time, "time")()`). honest-test's `call_monitor` patches the target symbols at import time, catching dynamic paths that slip through static analysis. Any source in `NONDETERMINISTIC_WATCH_LIST` called by a non-boundary link fails this check regardless of how it was invoked.

**Conformance.** An implementation fails the honest-test conformance suite if any symbol in the published watch list is NOT trapped at runtime. The conformance fixture calls each symbol from inside a supposedly-pure link and verifies that honest-test emits the non-determinism warning for each.

### 4.6 Chain Contract Testing

For each adjacent pair of links in a chain, every valid output of link N must be accepted as valid input by link N+1.

```
FUNCTION test_chain_contracts(chain, vocabulary, binding):
    FOR i FROM 0 TO len(chain.links) - 2:
        link_n   ← chain.links[i]
        link_n1  ← chain.links[i+1]

        test_cases ← enumerate_test_cases(link_n.accepts, binding)

        FOR EACH test_manifest IN test_cases:
            result ← link_n(test_manifest)

            IF "ok" IN result:
                result2 ← link_n1(result["ok"])
                IF "err" IN result2:
                    IF result2["err"].category = "server":
                        EMIT failure("chain_contract",
                            f"Link '{link_n1.name}' rejected valid output "
                            f"from '{link_n.name}': {result2}")
```

Client faults from link N+1 are not contract failures. Only server faults indicate a contract violation.

### 4.7 Auth Honesty Test

For every `@link` declared `authorizes=True`, honest-test auto-generates an auth honesty test using the registered `AuthProvider`'s `test_token_generator` (see `honest-auth-architecture.md §2.4`). The test exercises seven token classes and asserts the outcome against the provider's `fault_mapping`.

```
FUNCTION test_auth_honesty(link):
    provider ← get_registered_auth_provider()
    IF provider IS NONE: RETURN   // HC-A001 warning covers this case

    IF link.authorizes = False: RETURN

    test_classes ← {
        "valid_authorized",
        "valid_unauthorized",
        "revoked",
        "expired",
        "malformed",
        "missing",
        "forged",
    }

    FOR EACH class_name IN test_classes:
        context ← build_test_context_for_link(link)
        token   ← provider.test_token_generator.generate(class_name, context)
        manifest ← build_manifest_with_token(link, token, context)

        result ← execute_chain(link.chain, manifest)

        expected_http_status ← compute_expected_status(class_name, provider.fault_mapping)

        IF class_name = "valid_authorized":
            IF "ok" NOT IN result:
                EMIT failure("auth_honesty",
                    f"Link '{link.name}' rejected valid authorized token: {result}")
        ELSE:
            IF "err" NOT IN result OR map_to_http(result.err) ≠ expected_http_status:
                EMIT failure("auth_honesty",
                    f"Link '{link.name}' did not fault correctly for token class "
                    f"'{class_name}': expected {expected_http_status}, got "
                    f"{result}.")
```

**Class-to-fault mapping (default, overridable by provider):**

| Token class | Expected outcome |
|---|---|
| `valid_authorized` | `ok` |
| `valid_unauthorized` | `guard_failed` categorized as `forbidden` → 403 |
| `revoked` | `guard_failed` categorized as `unauthenticated` → 401 |
| `expired` | `guard_failed` categorized as `unauthenticated` → 401 |
| `malformed` | Rejection at `actor_recognizer` → 400 (or 401 if provider prefers) |
| `missing` | `guard_failed` categorized as `unauthenticated` → 401 |
| `forged` | `guard_failed` categorized as `unauthenticated` → 401 |

**Rationale.** A provider's correctness claim is only as strong as the behaviors its contract covers. The seven-class probe is the minimal set that exercises the contract. A challenger who modifies an authorizing link such that, for example, expired tokens are accepted, fails this test even though the chain's output shape is unchanged. Without auth honesty testing, expired-token acceptance would require an integration test running against the deployed application.

**Conformance requirement.** Every honest-test implementation must run the auth honesty test on every authorizing link, using the registered provider's generator. An implementation that reports no failures on a link whose authorization is broken (verified against the conformance probe suite in `honest/honest-auth-conformance/`) fails honest-test conformance.

---

## 5. State Machine Testing

honest-test generates exhaustive tests for state machines using the vocabulary enumeration machinery from section 3.

### 5.1 Valid Transition Testing

```
FUNCTION test_valid_transitions(machine):
    FOR EACH (state, event), next_state IN machine.transitions:
        result ← transition(machine, state, event)
        ASSERT result = ok({ state: next_state })
            OR EMIT failure("transition_incorrect",
                f"({state}, {event}) → expected {next_state}, got {result}")
```

### 5.2 Invalid Transition Testing

```
FUNCTION test_invalid_transitions(machine):
    FOR EACH state IN machine.states:
        FOR EACH event IN machine.events:
            IF (state, event) NOT IN machine.transitions:
                result ← transition(machine, state, event)
                ASSERT result = err({ code: "no_transition" })
                    OR EMIT failure("invalid_transition_accepted",
                        f"({state}, {event}) should produce no_transition fault")
```

### 5.3 Adversarial State and Event Testing

```
FUNCTION test_adversarial_state_machine(machine):
    FOR EACH state IN machine.states:
        FOR EACH adversarial IN adversarial_neighbors(state):
            result ← transition(machine, adversarial, first_valid_event(machine))
            ASSERT result = err({ code: "invalid_state" })

    FOR EACH event IN machine.events:
        FOR EACH adversarial IN adversarial_neighbors(event):
            result ← transition(machine, first_valid_state(machine), adversarial)
            ASSERT result = err({ code: "invalid_event" })
```

---

### 5.4 State Invariants

A state machine may declare **invariants** — predicates over the state tuple that must hold in every reachable state, not just in specific transitions. honest-test checks every declared invariant on every post-state produced by exhaustive transition enumeration.

**Declaration form (illustrative; exact syntax is per-spoke):**

```
task_permission_machine = state_machine(
    states       = {"active", "archived", "deleted"},
    events       = {"promote", "demote", "transfer", "revoke"},
    state_fields = {"owners", "rw", "ro", "status"},
    initial      = "active",
    invariants   = [
        invariant("at_least_one_owner", lambda s: len(s.owners) >= 1),
        invariant("no_user_in_multiple_roles",
                   lambda s: (s.owners & s.rw) == set()
                         and (s.owners & s.ro) == set()
                         and (s.rw & s.ro)     == set()),
        invariant("deleted_is_terminal",
                   lambda s: s.status != "deleted" or (s.owners | s.rw | s.ro) == set()),
    ],
    transitions  = { ... }
)
```

**Harness algorithm:**

```
FUNCTION check_state_invariants(machine):
    FOR EACH initial_state IN enumerate_initial_states(machine):
        FOR EACH (state, event), transition_fn IN machine.transitions:
            // Exercise the transition from this initial state
            start_state ← reach(initial_state, path_to(state))
            IF start_state IS reachable:
                result ← transition_fn(start_state, event)
                IF result is ok:
                    post_state ← result.ok.state
                    FOR EACH invariant IN machine.invariants:
                        IF NOT invariant.predicate(post_state):
                            EMIT failure("invariant_violation",
                                f"Invariant '{invariant.name}' violated after "
                                f"transition ({state}, {event}) from "
                                f"{start_state}. Post-state: {post_state}.")
```

**Relationship to transition correctness testing (§5.1).** §5.1 checks that `(state, event) → expected_next_state` matches the declared transition table. §5.4 checks that the post-state, whatever it is, satisfies declared invariants. Both run on the same enumeration pass.

**Rationale for the challenge:** a challenger can introduce a transition that produces a valid-looking next state, passes §5.1 (it matches the transition table entry), but violates an aggregate invariant like "every task has ≥1 owner." Without invariant checking, only an integration test catches the orphaned task. With §5.4, the harness finds the violation during enumeration and rejects the code.

### 5.5 TOCTOU Detection — Runtime Analog of HC-P015

honest-check HC-P015 forbids guards in `guarded_mutation` from referencing manifest slots whose provenance is a prior `persist.read()` within the same chain. honest-test verifies this at runtime for cases the static analyzer cannot resolve (dynamic call paths, indirect references).

```
FUNCTION verify_toctou_isolation(chain, test_manifest):
    // Instrument persist.read and persist.execute to tag returned values
    // with a provenance marker. Run the chain with the instrumented persist.

    WITH persist_provenance_tracker():
        result ← execute_chain(chain, test_manifest)

    // Inspect every guard expression executed during the chain run.
    // For each reference in each guard, check the provenance tag.

    FOR EACH guard_invocation IN tracker.guard_invocations:
        FOR EACH referenced_value IN guard_invocation.references:
            IF referenced_value.provenance IS persist.read:
                EMIT failure("toctou_vulnerable",
                    f"Chain '{chain.name}' executed a guard that references "
                    f"value read from persist earlier in the chain. "
                    f"Guard location: {guard_invocation.location}. "
                    f"Source read: {referenced_value.provenance.location}. "
                    f"This is a cross-chain TOCTOU vulnerability. "
                    f"Use a persist-side lookup expression in the guard instead.")
```

Runtime detection complements static HC-P015: every call path that HC-P015 can see is already flagged pre-commit; any path that dynamic dispatch hides from the static analyzer is caught here. Together the two checks leave no escape.

### 5.6 K-Step Sequence Enumeration

Single-transition invariant checking (§5.4) catches violations introduced by one event. Many semantic aggregate bugs only manifest after a sequence of events — e.g., `grant → revoke → grant → demote` leaves a state that single-step enumeration cannot reach from any initial state in one hop.

honest-test enumerates every event sequence of length ≤ K from every initial state, checking every declared invariant at every intermediate and final state.

```
FUNCTION enumerate_k_step_sequences(machine, K):
    initial_states ← enumerate_initial_states(machine)

    FOR EACH start IN initial_states:
        FOR EACH sequence IN all_event_sequences(machine.events, length ≤ K):
            current_state ← start
            FOR i, event IN enumerate(sequence):
                result ← transition(machine, current_state, event)
                IF result is fault:
                    BREAK   // sequence diverges from reachable space here
                next_state ← result.ok.state

                FOR EACH invariant IN machine.invariants:
                    IF NOT invariant.predicate(next_state):
                        EMIT failure("invariant_violation_at_depth",
                            f"Invariant '{invariant.name}' violated at step {i+1} "
                            f"of sequence {sequence[:i+1]} from {start}. "
                            f"Intermediate state: {next_state}.")

                current_state ← next_state
```

**Configuration.** K is declared per state machine, default K=4. K is capped by state-space size: `|events|^K` sequences per initial state. For `|events| = 8, K = 4`, that is 4,096 sequences per initial state, tractable in seconds.

**Why K=4 by default.** The majority of real-world aggregate bugs require 2–3 events; K=4 gives one step of safety margin. Implementations may raise K for high-assurance domains (authorization state machines, financial workflows). K=1 reduces the check to single-transition invariant testing (§5.4).

**Bounded by construction.** If events are a bounded Set (HC-SM02) and states are a bounded Set (HC-SM01), the sequence space is finite. The enumeration is deterministic, reproducible, and exhaustive within K.

**Rationale for the challenge:** a challenger can introduce a transition that produces a correct next state for every single (state, event) pair — passing §5.1 and §5.4 — but corrupts state after N events. §5.6 catches such mutations whenever N ≤ K. Without K-step enumeration, only an integration test running the full multi-step user flow catches the bug.

## 6. honest-persist Tests

honest-test generates contract tests for honest-persist query functions. These verify that queries behave correctly against the declared schema without requiring a production database.

### 6.1 Schema Contract Tests

For every query function declared against a `TableConfig`, honest-test verifies:

1. The query accepts a manifest conforming to the declared vocabulary
2. The query returns rows conforming to the declared column schema
3. The query rejects manifests with missing required fields
4. The query handles empty result sets without faulting

```
FUNCTION test_persist_contract(query_fn, table_config, db_connection):
    // Generate valid manifest from table_config's vocabulary
    valid_manifest ← enumerate_test_cases(table_config.vocab)[0]

    result ← query_fn(valid_manifest, db_connection)

    ASSERT "ok" IN result OR "err" IN result
    IF "ok" IN result:
        ASSERT result["ok"] is list
        IF len(result["ok"]) > 0:
            ASSERT conforms_to_schema(result["ok"][0], table_config.columns)
```

### 6.2 Mock Data Integration

When `data_mode = "mock"`, honest-test uses honest-persist's mock data generator to produce schema-conformant test rows. This guarantees every conditional formatting rule in a `TableConfig` fires at least once.

```
FUNCTION test_mock_coverage(table_config):
    mock_rows ← generate_mock_data(table_config, coverage_spec=table_config.formatting_rules)

    FOR EACH rule IN table_config.formatting_rules:
        matching_rows ← [row FOR row IN mock_rows IF rule.condition(row)]
        IF len(matching_rows) = 0:
            EMIT failure("formatting_rule_never_fires",
                f"Conditional formatting rule '{rule.name}' never fires in mock data. "
                "Add an explicit coverage case to honest-test.yaml.")
```

---

## 7. Component Isolation Tests

honest-test verifies that components are genuinely isolated. No component may affect another's state, CSS namespace, or JavaScript scope.

### 7.1 CSS Namespace Isolation

```
FUNCTION test_css_isolation(component_a, component_b):
    classes_a ← extract_css_classes(component_a.template)
    classes_b ← extract_css_classes(component_b.template)

    collision ← classes_a ∩ classes_b

    IF collision not empty:
        EMIT failure("css_namespace_collision",
            f"Components '{component_a.name}' and '{component_b.name}' "
            f"share CSS class names: {collision}. "
            "Each component must namespace under its own BEM block.")
```

### 7.2 Route Isolation

```
FUNCTION test_route_isolation(components):
    all_routes ← {}

    FOR EACH component IN components:
        FOR EACH route IN component.routes:
            IF route.path IN all_routes:
                EMIT failure("route_collision",
                    f"Route '{route.path}' defined by both "
                    f"'{all_routes[route.path]}' and '{component.name}'.")
            all_routes[route.path] ← component.name
```

### 7.3 Startup Fault Isolation

```
FUNCTION test_startup_isolation(components):
    FOR EACH component IN components:
        TRY:
            load_component(component)
        CATCH exception:
            // Component fails to load — verify others still load
            remaining ← [c FOR c IN components IF c ≠ component]
            FOR EACH other IN remaining:
                TRY:
                    load_component(other)
                CATCH:
                    EMIT failure("startup_cascade",
                        f"Failure in '{component.name}' caused failure in '{other.name}'. "
                        "Components must be independently loadable.")
```

---

## 8. BDD Tests

### 8.1 Principle

Developer-authored Gherkin `.feature` files describe application behavior in business language. honest-test connects Gherkin steps to chain links via step scaffolding generated from link declarations.

The BDD engine under the hood is **honest-gherkin**, specified in `honest-gherkin-architecture.md`. Earlier drafts of this section deferred the engine to each spoke ("wrap an existing Python BDD framework"). That deferral is withdrawn: wrapping behave / pytest-bdd / cucumber-js imports a mutable shared `context`, global decorator registration, and exceptions-for-control-flow — the three things the framework forbids everywhere else — into the one layer meant to prove their absence. honest-gherkin specifies one honest-code-conformant execution model (pure fold over an immutable context, registry-as-data, faults-as-data) that every spoke implements. This section defines only the contract between Gherkin steps and honest-framework primitives; the engine semantics live in honest-gherkin.

### 8.2 Step Scaffolding

honest-test generates step scaffolding from `@link` declarations. The scaffolding conforms to honest-gherkin's step-module contract (honest-gherkin-architecture.md §8.2): handlers are pure functions that take the immutable context plus bound captures and **return a new context**; they are wired through `register(registry) -> registry`, never via decorators or a mutable shared `context` object. For a chain named `create_user_pipeline`, it generates:

```python
# auto-generated scaffolding — do not edit

def step_user_manifest(ctx, email, role):
    return {**ctx, "manifest": classify([email, role], user_vocab, user_binding)}

def step_run_pipeline(ctx):
    return {**ctx, "result": execute_chain(create_user_pipeline, ctx["manifest"])}

def step_result_ok(ctx):
    assert "ok" in ctx["result"]
    return ctx

def step_result_fault(ctx, code):
    assert "err" in ctx["result"]
    assert ctx["result"]["err"]["code"] == code
    return ctx

def register(registry):
    registry = register_step(registry, "given",
        r'a user manifest with email "{email}" and role "{role}"', step_user_manifest)
    registry = register_step(registry, "when",
        r"the create user pipeline runs", step_run_pipeline)
    registry = register_step(registry, "then",
        r"the result is ok", step_result_ok)
    registry = register_step(registry, "then",
        r'the result has a fault code "{code}"', step_result_fault)
    return registry
```

The developer writes `.feature` files against this scaffolding:

```gherkin
Feature: Create user

  Scenario: Valid user is created
    Given a user manifest with email "adam@example.com" and role "admin"
    When the create user pipeline runs
    Then the result is ok

  Scenario: Invalid role is rejected
    Given a user manifest with email "adam@example.com" and role "superuser"
    When the create user pipeline runs
    Then the result has a fault code "unrecognized"
```

### 8.3 Convention: universal gherkin coverage

A gherkin is not reserved for chains. **Every roled function — `@link`, `@recognizer`, `@boundary`, `@helper` — carries exactly one gherkin scenario** stating its behavior. A pure internal helper is specified by a gherkin just as a top-level chain is. The chains-only rule of earlier drafts is withdrawn; the governing model is honest-gherkin-architecture.md §9.

Chain-level gherkins are filed one `.feature` file per chain, named after the chain; function-level gherkins are filed alongside their function (a spoke fixes the exact layout). Either way the mapping is one function, one gherkin.

```
features/
  create_user_pipeline.feature
  format_pipeline.feature
  reset_password_pipeline.feature
```

A roled function without a gherkin produces an **HC-P009** diagnostic from honest-check, generalized from "chain without `.feature`" to "roled function without a gherkin." This makes coverage one-to-one, which is what lets the gherkin count serve as a direct function-point count (honest-gherkin-architecture.md §9.2) and lets real FP be triangulated against the conformance-law and feature/screen counts (research-protocol.md §3.4).

### 8.4 Standard Protocol-Level Assertion Library

Auto-generated tests cover chain behavior at the manifest level. They do not cover the HTTP protocol surface — status codes, headers, Content-Type, cookies, body bytes — unless the developer's Gherkin scenarios include assertions at that layer.

Because HTTP-level bugs (wrong Content-Type, mis-encoded response body, cookie attribute missing, off-by-one routing) are exactly the class integration tests have traditionally caught, the BDD step library must provide standard protocol-level assertion steps. Every implementation of honest-test ships these steps; developers use them in their `.feature` files without additional scaffolding.

**Required standard steps (every spoke ships these):**

```gherkin
Then the response status is {integer}
Then the response status is in {status_class}        # "2xx", "3xx", "4xx", "5xx"
Then the response Content-Type is "{mime_type}"
Then the response charset is "{charset}"
Then the response header "{name}" equals "{value}"
Then the response has no header "{name}"
Then the response body bytes equal "{literal}"
Then the response body is JSON conforming to {schema_name}
Then the response body is HTML containing the selector "{css_selector}"
Then the response sets cookie "{name}" with value "{value}"
Then the response cookie "{name}" has attribute "{attribute}"
Then the response cookie "{name}" has Max-Age {integer}
Then the response location is "{url}"
```

**Request-side steps:**

```gherkin
Given a request with header "{name}" = "{value}"
Given a request with cookie "{name}" = "{value}"
Given a request with body "{content}"
Given a request with Content-Type "{mime_type}"
When a POST request is sent to "{path}" with body "{content}"
When a GET request is sent to "{path}"
When a DELETE request is sent to "{path}"
```

**Multi-request sequence steps (for sequences that test stateful user journeys):**

```gherkin
When the previous response's Set-Cookie is used as the next request's Cookie
When the session from the previous response is reused
Then the response and the previous response share the same session cookie value
```

**Rationale.** A challenger who modifies a serializer to emit `Content-Type: text/plain` instead of `text/html; charset=utf-8` produces output that passes chain contract testing (the link's manifest output is unchanged), passes honesty checks (still pure), but breaks every client that dispatches on Content-Type. The standard library gives feature authors a vocabulary to assert on exactly those properties. With a feature scenario that says `Then the response Content-Type is "text/html; charset=utf-8"`, the mutation fails in the auto-run. Without such a scenario (and without the step library making it easy to write), the mutation passes.

**Requirement for the challenge.** The published reference application ships BDD feature files covering all HTTP endpoints with standard protocol-level assertions on status, Content-Type, charset, and body shape. Any mutation that changes an HTTP-level property captured by the standard library is caught at pre-commit. Integration-test-catchable HTTP bugs are thereby auto-generated-test-catchable.

---

## 9. Coverage

Coverage in honest-test has four dimensions. How they are reported is an implementation detail per spoke.

### 9.1 Vocabulary Coverage

What percentage of Set members appeared in at least one test case?

```
vocabulary_coverage(vocab) =
    members_exercised / total_members × 100
```

honest-test's exhaustive Set enumeration drives this to 100% automatically for bounded types. Predicate coverage is reported as "boundary + adversarial" since exhaustive enumeration is not possible.

### 9.2 Chain Coverage

What percentage of fault exit points in a chain are exercised?

```
chain_coverage(chain) =
    fault_paths_exercised / total_fault_paths × 100
```

A chain of N links has up to N fault exit points. honest-test exercises each by generating inputs that trigger each link's failure conditions.

### 9.3 Honesty Coverage

What percentage of links have passed all honesty tests (purity, mutation, idempotency, boundary isolation)?

```
honesty_coverage(chain) =
    honest_links / total_links × 100
```

Links declared `boundary=True` are reported separately, not as coverage failures.

### 9.4 State Machine Coverage

What percentage of declared transitions were exercised?

```
state_machine_coverage(machine) =
    transitions_exercised / total_transitions × 100
```

Exhaustive transition testing drives this to 100%.

### 9.5 Coverage Data Format

honest-test writes `coverage.json` that honest-check reads for HC-P009 (chain missing .feature file) and other cross-tool checks:

```json
{
    "version": "1.0",
    "timestamp": "2026-03-15T...",
    "vocabularies": {
        "format_vocab": { "total": 5, "exercised": 5, "pct": 100 }
    },
    "chains": {
        "format_pipeline": { "fault_paths": 3, "exercised": 3, "pct": 100 }
    },
    "honesty": {
        "format_pipeline": {
            "total": 3,
            "honest": 3,
            "boundary": 1,
            "pct": 100
        }
    },
    "state_machines": {
        "order_machine": { "transitions": 5, "exercised": 5, "pct": 100 }
    }
}
```

---

## 10. Configuration

```yaml
# honest-test.yaml

runner:
  parallel: true
  timeout_seconds: 30

predicates:
  # Programmer-supplied values for external-lookup predicates
  customer_id:
    valid: ["CUST-00001", "CUST-99999"]
    invalid: ["CUST-0", "cust-00001"]
    strategy: supplied_only

  order_amount:
    strategy: fibonacci
    limit: 1_000_000_000
    negative: false

coverage:
  minimum_vocabulary: 100    # fail if any Set member goes untested
  minimum_chain: 80          # warn if fault paths < 80% exercised
  minimum_honesty: 100       # fail if any link fails honesty test

bdd:
  features_dir: features/
  scaffolding_dir: test_scaffolding/
  auto_generate_scaffolding: true
```

---

## 11. Output Format

```
honest-test v0.1.0
Scanning src/ for chains...

Found 4 chains, 12 links, 6 vocabularies

format_pipeline (3 links)
  Vocabulary: format_name(5) × currency_code(150) × style_name(4)
  Permutations: 3,000
  Running.............. 3,000/3,000 PASS
  Adversarial: 847 near-miss inputs, 847 rejected
  Honesty: purity ✓  mutation ✓  idempotency ✓
  Chain contracts: all outputs accepted by downstream links
  State machines: N/A

create_user_pipeline (5 links)
  Vocabulary: action(3) × role(4) × boolean(2)
  Permutations: 24
  Running... 24/24 PASS
  Adversarial: 156 near-miss inputs, 156 rejected
  Honesty: purity ✓  mutation ✓  idempotency ✓  boundary: insert_user (expected)
  Chain contracts: all outputs accepted by downstream links
  BDD: features/create_user_pipeline.feature — 3/3 scenarios PASS

order_machine (state machine)
  States: 4, Events: 4, Transitions: 5
  Valid transitions: 5/5 PASS
  Invalid transitions: 11/11 correctly rejected
  Adversarial: 240 near-miss state/event tokens, 240 rejected

Total: 3,024 permutations tested, 0 failures
       1,003 adversarial inputs, 1,003 rejected
       11/12 links verified honest (1 declared boundary)
       3/3 BDD scenarios PASS
```

---

## 12. Conformance

### 12.1 Conformance Levels

| Level | Requirement |
|---|---|
| **Core** | Auto-generated tests for Set enumeration and adversarial neighbors pass the conformance suite |
| **Full** | Core + honesty tests (purity, mutation, idempotency, boundary isolation) + chain contract testing |
| **Complete** | Full + state machine testing + honest-persist contract tests + component isolation tests + BDD runner |

### 12.2 Conformance Suite

The conformance suite lives in the hub repo at `honest/honest-test-conformance/suite.json`. Each test case provides a vocabulary or chain definition and the expected test generation output or pass/fail result.

Implementations declare their conformance level in their README and package metadata.

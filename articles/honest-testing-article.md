# The Testing Harness That Writes Itself

## Why bounded vocabularies make exhaustive verification trivial, and why the "compile time vs. runtime" argument was always a red herring

There is a belief in software engineering that has survived for thirty years without serious challenge:

*It is better to catch an error at compile time than at runtime.*

This belief underpins the entire case for static typing. It's why TypeScript exists. It's why Java's verbosity is tolerated. It's why every conference talk about dynamic languages includes the obligatory slide showing a `TypeError` in production, followed by "this would have been caught by the compiler."

The belief is not wrong. It's incomplete. And the incompleteness hides an assumption that, once exposed, collapses the entire argument.

---

## The assumption nobody examines

The argument "catch it at compile time" assumes there are only two options:

1. A compiler analyzes your code before it runs and catches type errors statically.
2. You ship the code and find out at runtime when it crashes.

This framing treats "before you run" and "a compiler" as synonyms. They aren't. A compiler is one mechanism for checking code before it runs. It is not the only one.

The reason compilers became the default mechanism is that class-based type systems made any other mechanism impractical. When your type space includes inheritance hierarchies, generic constraints, interface implementations, wildcard types, and method overloading: the number of possible type states is effectively unbounded. You need a compiler because only a compiler can reason about an open, unbounded type algebra.

But what if the type algebra wasn't unbounded?

---

## Bounded vocabularies change the math

The Honest Framework's type system, `honest-type`, doesn't use classes. Types are pure function tables: Sets of known values and predicate functions.

```python
format_vocab = vocabulary({
    "format_name":   {"currency", "number", "percent", "date", "phone"},
    "currency_code": {"USD", "EUR", "GBP", "JPY", "CAD"},
    "style_name":    {"short", "medium", "long", "full"},
})
```

`format_name` has 5 members. `currency_code` has 5 members in this example (150 in production). `style_name` has 4 members.

The total permutation space is `5 * 5 * 4 = 100`.

That's a `for` loop.

You don't need a compiler to check 100 combinations. You don't need static analysis, type inference, constraint solving, or a PhD in type theory. You need three nested loops and a few milliseconds.

And this isn't sampling. This isn't property-based testing that randomly generates inputs and hopes to find bugs. This is **exhaustive enumeration of every possible valid input.** Every combination. Every permutation. Every time.

---

## The vocabulary is the spec

Swagger (now OpenAPI) transformed API development by recognizing a simple principle: if you've already defined your API's inputs and outputs as a schema, you can generate everything else from that schema. Documentation. Test interfaces. Client SDKs. Mock servers. The schema is the single source of truth, and everything derives from it.

`honest-test` applies the same principle to type systems.

You've already defined your vocabularies, the Sets and predicates that classify tokens. You've already defined your bindings, the tables that map types to slots. You've already defined your chains, the pipelines that compose functions.

From those definitions, `honest-test` generates:

**Every valid input.** Not a sample. Not a representative subset. Every single permutation of every bounded vocabulary, fed through every chain.

**Every invalid input.** Near-misses, off-by-one strings, type confusions, empty strings, tokens that almost match a recognizer but don't. All generated automatically. All confirmed to produce rejections.

**Purity proofs.** Every function in a chain is called twice with the same input. Outputs must be identical. The function is instrumented for global reads, mutations, file I/O, network calls. If it claims to be a pure link in an honest chain, the harness proves it.

**Chain contract verification.** Every valid output of link N is fed through link N+1. Not type-checking that they're compatible, but actually running the data through and confirming nothing crashes, nothing is silently dropped, nothing mutates.

**Idempotency proofs.** Every chain is run twice with the same manifest. Results must be identical. This catches hidden state that static analysis cannot detect.

The vocabulary is the spec. Everything else is generated.

---

## Three checkpoints, one mechanism

Here's what the Honest Framework's verification story actually looks like:

**Checkpoint 1: Pre-commit (honest-check)**

Static analysis. Walks the code, collects vocabulary declarations, performs set intersection to verify that chain links are type-compatible. Runs in milliseconds. Catches structural errors before you commit.

Set math is the mechanism. If link A outputs types `{currency_code, integer}` and link B accepts types `{currency_code, style_name}`, the intersection is `{currency_code}`. The `integer` output has nowhere to go. Error.

**Checkpoint 2: Test suite (honest-test)**

Exhaustive runtime verification. Enumerates every permutation, runs them through the actual code, verifies purity, idempotency, chain contracts, and rejection boundaries.

```
format_pipeline (3 links)
  Vocabulary: format_name(5) × currency_code(150) × style_name(4)
  Permutations: 3,000
  Running.............. 3,000/3,000 PASS
  Purity: 3/3 links verified pure
  Idempotency: PASS
  Rejections: 847 adversarial inputs, 847 rejected
```

The guarantee is absolute. Enumeration, not sampling: every permutation runs, every time.

**Checkpoint 3: Production (honest-type)**

The same predicate tables run at every boundary in the live application. HTTP parameters, DOM attributes, function chain inputs. Every token is classified or rejected. The same code that ran at pre-commit and in the test suite runs here.

All three checkpoints use the same vocabulary definitions. The same predicate functions. The same binding tables. There is no drift between what the linter thinks, what the tests cover, and what production enforces.

A compiler gives you checkpoint 1. Maybe. If your type system is expressive enough and your codebase is small enough for the type checker to finish in reasonable time.

The Honest Framework gives you all three, from the same source of truth, with the same code. The sample output later in this article shows 4,678 test cases running in 18ms: that is what exhaustive enumeration of a bounded space costs.

---

## Why guess when you can count?

A compiler operates on an open type algebra. Java has generics (`List<T>` where T is unconstrained), wildcards (`List<? extends Foo>`), inheritance chains, interface implementations, reflection, and runtime casting. TypeScript has conditional types, mapped types, template literal types, and discriminated unions. These features make the type system expressive but also make the space of possible type states effectively infinite.

You cannot enumerate an infinite space. You can only reason about it symbolically, which is what a compiler's type checker does. And symbolic reasoning has limits. TypeScript's type checker is one of the most complex pieces of software in the JavaScript ecosystem, and it still misses things.

Bounded vocabularies are finite by construction. A Set with 150 members has exactly 150 members. A pipeline with three Set-based inputs has exactly `N * M * K` permutations. You don't reason about this space symbolically. You run every member through the code and observe what happens.

This is why the compile-time argument doesn't apply. The argument assumes that static symbolic reasoning (compilation) is the only way to check types before runtime. It isn't. Exhaustive enumeration works too, but only if the space is bounded. Classes made the space unbounded. Honest Code made it bounded again.

---

## What about predicates?

Sharp readers will have noticed that not all recognizers are Sets. Some are predicates:

```python
"integer": predicate(lambda s: s.isdigit())
```

The set of all strings matching `isdigit()` is infinite. You can't enumerate it.

But you can enumerate the boundary systematically. For integer predicates, `honest-test` generates a Fibonacci sequence starting at 0, running upward to a limit: either the framework default or a programmer-defined ceiling. Fibonacci is the right choice because it covers small values densely, then grows rapidly, hitting the inflection points where overflow, truncation, and formatting bugs live. For float predicates, each Fibonacci number is passed through a function that generates the corresponding real: `0`, `0.1`, `0.2`, `0.3`, `0.5`, `0.8`, `1.3`, and so on. The sequence is deterministic and reproducible, not random.

Beyond valid inputs, the harness generates adversarial cases: near-misses (`"12.5"`, `"12a"`, `"-1"`, `" 3"`), empty strings, type confusions (`"USD"` is valid in another recognizer but must be rejected here), and very long strings that expose buffer assumptions. Every rejection is confirmed: a near-miss that passes is a bug in the recognizer, caught before commit.

For predicate-based recognizers, the guarantee is boundary coverage rather than exhaustive enumeration. This is clearly documented: the harness tells you which recognizers are Set-based (exhaustive) and which are predicate-based (boundary-tested).

The honest move is to prefer bounded vocabularies wherever the domain is finite. If you only accept integers 0-10, declare that bound explicitly: either as a hand-enumerated Set or as a bounded generator, a function that produces the finite set deterministically. Either way, `honest-test` knows the space is closed and enumerates every member. The framework rewards bounded vocabularies with exhaustive guarantees; predicates get boundary coverage. The distinction is always visible in the report.

---

## Confidence vs. proof

The case for static typing was never really about *when* errors are caught. It was about *whether* they're caught. A compiler catches type errors. No compiler means no type checking. Errors reach production.

That syllogism has a hidden premise: *the only mechanism for type checking is a compiler.*

The Honest Framework removes that premise. Bounded vocabularies make type checking a `for` loop, not a constraint solver. The pre-commit linter catches structural errors. The test harness proves behavioral correctness exhaustively. The runtime enforces the same rules in production. All three use the same code.

The compile-time advantage was real, but it was a consequence of a specific architectural choice (classes and unbounded type spaces), not a fundamental law of computing. Change the architecture, and the advantage transfers to a simpler mechanism that provides stronger guarantees.

A compiler reasons symbolically about an infinite space and gives you confidence.

`honest-test` enumerates a finite space and gives you proof.

---

## What the output looks like

```
uv run python honest_test.py src/ --report

honest-test v0.1.0
Scanning src/ for chains...
Found 4 chains, 14 links, 8 vocabularies
Total bounded permutations: 4,248
Predicate recognizers: 3 (boundary-tested)

format_pipeline ............................. 3,000/3,000  PASS
create_user_pipeline ........................    24/24     PASS
search_pipeline .............................   720/720    PASS
admin_pipeline ..............................   504/504    PASS

Purity verification:
  12/14 links verified pure
  2 boundary functions (I/O detected, expected):
    → insert_user (database write)
    → send_notification (HTTP call)

Chain contracts:
  All outputs of link N accepted by link N+1 .... PASS

Rejection boundary:
  412 adversarial inputs generated
  412 correctly rejected ...................... PASS

Idempotency:
  All chains produce identical results on
  repeated invocation ........................... PASS

Mutation detection:
  No input manifests modified by any link ....... PASS

Coverage: 4,248 bounded + 18 boundary + 412 adversarial = 4,678 test cases
Time: 18ms
```

4,678 test cases. Generated from vocabulary definitions. Run in 18ms on a three-year-old Mac Mini. Every valid input tested. Every invalid input rejected. Every function proven pure or explicitly marked as a boundary.

No developer wrote those tests. The vocabularies wrote them.

---

## Defining them is the same as testing them

You declare your vocabularies: Sets of valid values, predicates for open patterns. From those declarations, `honest-check` statically verifies your chains are compatible, `honest-test` exhaustively runs every permutation through your code, and `honest-type` enforces the same rules in production. Three checkpoints, one source of truth, zero drift. The compiler was never the point. The bounded type space was the point. We just skipped the compiler and went straight to proof.

The Honest Framework doesn't catch errors at compile time or at runtime. It catches them at definition time, because when your types are bounded, defining them is the same as testing them.

---

*The companion article, "The Type System That Nobody Designed," describes how removing dishonest code revealed a latent type system. These ideas are developed at length in [Honest Code](https://honestcode.software).*

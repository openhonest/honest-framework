# The Type System That Nobody Designed

## How removing classes revealed that pure functions were types all along

I didn't set out to invent a type system. I set out to keep my code honest.

Honest Code has one demand: every function should be transparent about what it does. What goes in, what comes out, what it touches, what it changes. No hidden state. No action at a distance. No method on an object that silently mutates three fields and triggers a cascade through an observer chain that nobody can trace.

When you follow that demand rigorously, classes become difficult to justify. Classes make dishonesty easy. A class is a bag of state with methods that can reach into that bag at any time, from any method, in any order. The state is hidden behind `self`. The mutations are implicit. The interactions between methods are invisible. You have to read every method to understand any method. That's not transparent. That's not honest.

So I stopped reaching for classes — not as a dogmatic stance, but because every time I tried to write honest code inside a class, the class fought me. Pure functions, typed dictionaries, flat composition, I/O at the boundary. The code became easier to write, easier to read, easier to test, easier to trust. Not because I'd adopted a methodology, but because honesty has structural consequences.

What I didn't expect was what happened next: a type system fell out of the honest architecture. Not one I designed. One that was already there, hidden behind the dishonesty I'd removed.

---

## The problem that revealed it

The Honest Framework has a browser library that adds behavior to HTML through attributes. You write `hf-format="currency"` and `hf-currency="USD"` on a `<span>`, and the framework formats the number inside it as US dollars. No JavaScript to write. The attribute declares the intent; the library handles the mechanism.

This works cleanly when each attribute has its own name: `hf-format`, `hf-currency`, `hf-decimals`. The attribute name tells you the slot. The value tells you the content. Straightforward parsing.

But I kept running into cases where a single attribute would be cleaner:

```html
<span hf="currency USD 2">1299.99</span>
```

Three tokens. No attribute names to separate them. Just a space-delimited string. The question becomes: which token means what?

In a statically typed language, this is easy. The compiler knows that `"currency"` is a format name, `"USD"` is a currency code, and `"2"` is an integer. It resolves them to parameters based on their types. Java's Manifold project does exactly this: adjacent expressions bind based on compile-time type information.

But I don't have a compiler. I have a browser. Everything is a string. There are no types.

The standard solutions are:

**Positional parsing.** Token 1 is the format, token 2 is the currency, token 3 is the decimal count. Rigid, fragile, breaks the moment you want to skip a parameter or add a new one. Also dishonest: the meaning is determined by memorized order, not by the data itself.

**Heuristic detection.** Run each token through a series of regex patterns, assign confidence scores, pick the best match. `"100"` is *probably* a number (85% confidence), *maybe* a year (40%). Ambiguous, non-deterministic, and requires fallback logic for low-confidence matches. The opposite of honest.

Neither option was acceptable. Positional parsing is too brittle. Heuristic detection is too uncertain. And both violate the core Honest Code principle: **the data should say what it is, not rely on position or guessing.**

---

## The insight that was already there

I was staring at the problem when I noticed something I'd been doing all along without naming it.

In the formatting library, I already had sets of known values:

```javascript
const FORMAT_NAMES   = new Set(['currency', 'number', 'percent', 'date', 'phone'])
const CURRENCY_CODES = new Set(['USD', 'EUR', 'GBP', 'JPY', 'CAD'])
const STYLE_NAMES    = new Set(['short', 'medium', 'long', 'full'])
```

And I already had predicate functions for open patterns:

```javascript
const isInteger = (s) => /^\d+$/.test(s)
const isBoolean = (s) => s === 'true' || s === 'false'
```

These were just validation helpers. I'd written them as utilities without thinking about what they actually were. But when I looked at them through the lens of the binding problem, I saw it:

**Each of those functions is a type.**

`FORMAT_NAMES` is a type declaration. It says: "a token is of type *format_name* if and only if it is a member of this set." That's the same thing `class FormatName` says in Java: it defines membership in a category. The mechanism differs (set lookup vs. class instantiation), but the logical structure is identical.

A type system does three things:

1. Classifies values into categories
2. Defines legal operations between categories
3. Rejects invalid combinations

A pure function that returns a boolean does all three:

1. **Classification:** `CURRENCY_CODES.has("USD")` returns `true`. "USD" is classified as a currency code.
2. **Operations:** A binding table says "if a token is classified as *currency_code*, it fills the *currency* slot." That's a legal operation between a type and a semantic role.
3. **Rejection:** `CURRENCY_CODES.has("banana")` returns `false`. "banana" is not a currency code. It's not approximately a currency code. It's not a currency code with 12% confidence. It's rejected. Deterministically. Every time.

I didn't need a compiler. I didn't need type annotations. I didn't need Pydantic or Zod or TypeScript. The sets and predicates I'd already written for validation *were* the type system. I just hadn't called them that.

---

## From insight to architecture

Once I saw it, the rest followed quickly.

**Layer 1: Vocabulary.** Every pure function from `String → Boolean` is a type predicate. A collection of them is a vocabulary. Sets handle closed domains; predicates handle open ones.

```python
format_vocab = vocabulary({
    "format_name":   {"currency", "number", "percent", "date"},
    "currency_code": {"USD", "EUR", "GBP", "JPY", "CAD"},
    "style_name":    {"short", "medium", "long", "full"},
    "integer":       predicate(lambda s: s.isdigit()),
})
```

**Layer 2: Binding.** A flat table that maps resolved type names to semantic slot names in the manifest. This is all the binding machinery that exists: a dict lookup.

```python
format_binding = binding({
    "format_name":   "format",
    "currency_code": "currency",
    "style_name":    "style",
    "integer":       "precision",
})
```

`classify(["currency", "USD", "2"], format_vocab, format_binding)` returns:

```python
{"format": "currency", "currency": "USD", "precision": "2"}
```

Order independent. `["USD", "2", "currency"]` produces the same result.

**Composed types.** The obvious solution to context-sensitive binding is a third mechanism: a side table keyed on pairs of types. An integer after `"currency"` means decimals; after `"date"` it means year. But a side table is a separate moving part, and it breaks order independence unless you define what "after" means. Composed types handle context inside the vocabulary itself, with no third mechanism required.

A composed type matches when specific base type classifications are all present in the input, and captures the value of one of them:

```python
format_vocab = vocabulary(
    base_types={
        "format_name":   {"currency", "number", "percent"},
        "currency_code": {"USD", "EUR", "GBP"},
        "integer":       predicate(lambda s: s.isdigit()),
    },
    composed_types=[
        composed("currency_precision",
            requires={"format_name": "currency"},
            captures="integer",
        ),
    ],
)

format_binding = binding({
    "format_name":        "format",
    "currency_code":      "currency",
    "integer":            "precision",      # default: integer → precision
    "currency_precision": "decimals",       # override: when currency, integer → decimals
})
```

`classify(["currency", "USD", "2"], format_vocab, format_binding)` returns:

```python
{"format": "currency", "currency": "USD", "decimals": "2"}
```

Note that `"precision"` is absent. The integer was captured by `currency_precision`, so its base binding was suppressed. Change the input to `["number", "USD", "2"]` and `currency_precision`'s requirement is not met; the integer falls through to its base binding and `"precision": "2"` appears instead.

The classify algorithm runs two passes to guarantee order independence: pass one classifies every token against base types; pass two resolves composed types against the full ticket set, then binds everything. No token's classification depends on what came before it in the input.

**Maybe.** Slots can be declared optional. A maybe binding means: if no token matches this type, the slot is present in the manifest with value `Nothing` rather than absent or rejected. The manifest shape is fully predictable from the binding table regardless of what tokens arrive.

```python
binding({
    "format_name":   "format",
    "currency_code": maybe("currency"),   # present as null if no currency token
    "integer":       maybe("precision"),  # present as null if no integer token
})
```

The examples above are Python, and the notation is idiomatic Python. Implementations for every dynamic language that would benefit from this pattern are in progress: the same vocabulary, binding, and composition model expressed in the natural idioms of each language. Not every dynamic language is a target; statically typed languages already have type systems and don't need this one. But for the languages that are, the underlying algorithm is identical and the API surface adapts to what feels natural in that language.

There is a learning curve. Vocabularies, composed types, maybe bindings, two-pass classification: these are new concepts even for experienced programmers, and the notation makes that density visible. A VS Code extension is in development that substantially eases the burden: inline type resolution showing what each token classifies to, chain visualization, overlap detection, and honest-test integration running the exhaustive suite directly in the editor. The notation stays; the cognitive load of navigating it drops considerably.

The same two-layer structure applies anywhere untyped strings arrive and typed, named data needs to come out the other side. Classification puts each token into a category; binding delivers it to the right slot in the manifest, which the downstream function receives as a plain dict with named keys. That delivery step is what "routed" means here: the manifest is the dispatch table.

`classify(["currency", "USD", "2"], format_vocab, format_binding)` returns `{"format": "currency", "currency": "USD", "decimals": "2"}`.

Order independent. Deterministic. Exhaustive. A token either matches or it doesn't. There is no confidence score, no fallback, no "probably."

---

## Stop guessing, start counting

Here's where it gets interesting.

A Set has a known, finite number of members. `CURRENCY_CODES` has 150 entries. `STYLE_NAMES` has 4. `FORMAT_NAMES` has 5. The total permutation space of a three-token binding across those vocabularies is `5 * 150 * 4 = 3,000`. That's not just statically checkable. It's exhaustively testable. You could enumerate every valid and invalid combination in a test suite that runs in milliseconds.

Compare that to a class-based type system. In Java, generics blow the permutation space open. `List<T>` where T is unconstrained means the compiler has to reason about every possible type that could ever be substituted. Wildcard generics (`List<?>`, `List<? extends Foo>`) make it worse. The type space becomes effectively unbounded despite the nominal type system's apparent rigidity.

Pure function tables with bounded vocabularies invert this completely. The permutation space is closed at definition time. A pre-commit hook can walk every function chain, collect the recognizer tables at each link, and verify that the output classifications of one link are a subset of the accepted inputs of the next. Set intersection is the mechanism: trivial to implement, guaranteed correct because the vocabulary is exhaustive by construction.

So the static checker and the runtime validator are the same operation, just invoked at different times. Same predicate tables, same results, zero drift between what the checker thinks and what the runtime does.

TypeScript can't say that. The static checker and the runtime are fundamentally different beasts. The types literally don't exist when the code runs.

Pydantic can't say that either. The runtime validator is real, but there's no static equivalent. The schema is checked at object construction time, not at the boundary where tokens arrive.

Pure function tables check at both times, with the same code. That's something you’ve never seen before.

---

## The pipeline is the type system

The real insight isn't about types. It's about cost. The framing "pure function tables are a type system" is true but undersells it.

Set lookup is O(1). Predicate evaluation is a single function call. The classification chokepoint is so computationally cheap that it stops being an architectural concern. You can put it everywhere, at every function boundary, at every HTTP endpoint, at every DOM attribute, with zero guilt about performance.

Compare that to Pydantic, which does object construction, field coercion, and error accumulation on every validation call. Or JSON Schema validation, which is recursive tree traversal. Or TypeScript, which does nothing at runtime at all.

If validation is effectively free, you stop making tradeoffs between safety and performance. You don't skip validation at internal service boundaries to save cycles. You don't batch-validate at the edge and trust everything downstream. Every function boundary can be a typed boundary and the cost is negligible.

But instead of sprinkling validation all over a codebase like fairy dust, the Honest Code path is to make it a compositional part of a function chain:

```
raw tokens → classify → bind → dispatch → next function → classify → bind → ...
```

Every link in the chain declares its vocabulary. The chain itself handles classification and binding before dispatch. The function never sees an unclassified token. It only ever receives a resolved, named argument.

This has a property worth naming: **it makes invalid states unrepresentable not through type annotations but through the structure of the pipeline itself.** A function downstream in the chain cannot receive an unrecognized token because the chain architecture physically prevents it from arriving. That's stronger than a type annotation, which is advisory. Stronger than a runtime validator, which is incidental. The pipeline is the type system.

---

## The enemy of type safety is dishonesty

I started with a simple demand: keep the code honest. Every function transparent about its inputs, outputs, and effects. Following that demand meant classes fell away, not because I banned them, but because they couldn't meet the standard. And in their absence, without intending to, I arrived at a type system that:

- Works identically at pre-commit time and runtime
- Has bounded, exhaustively testable permutation spaces
- Costs effectively nothing to evaluate
- Requires no compiler, no build step, no toolchain
- Works in every dynamic language with zero modification
- Composes by merging dictionaries

None of this was designed. It was discovered. The pure functions and sets were already there, doing honest validation work. The type system was latent in the code, waiting for someone to notice that a Set used for membership testing is structurally isomorphic to a type declaration.

The standard industry argument has always been: *dynamic languages are unsafe because they lack a type system. You need static typing to catch errors early.*

The honest counterargument is: *the enemy of early type checking is not dynamicism. It is dishonesty.*

Classes make dishonesty easy. Hidden state, implicit mutation, unbounded permutation spaces: these are all forms of dishonesty, and they're what makes static analysis hard, slow, and occasionally wrong. When you demand honesty, transparent functions, explicit data flow, bounded vocabularies, the permutation space collapses to something a pre-commit hook can verify via set intersection in milliseconds.

The entire "dynamic vs. static" framing is a thirty-year red herring. The real variable was always whether your code was honest about its types or hiding them behind class machinery. Honesty made the types visible. The type system was a consequence, not a goal.

---

## What comes next

The Honest Framework implements this as `honest-type`. Python and JavaScript ship first; Ruby and PHP follow. The goal is an idiomatic implementation for every dynamic language that can benefit from it, with the same recognizer tables and binding tables running at every boundary in the stack. HTTP request parameters, DOM attribute values, function chain inputs, database query results. One mechanism, every layer.

The browser library classifies HTML attribute tokens. The server middleware classifies HTTP parameters. The function chain validates inputs at every link. The pre-commit linter verifies chain compatibility. All of them use the same code: a pure function that takes a string and returns a boolean.

A Set membership check is the most primitive possible expression of "this value belongs to this category." Every type system ever built, classes, annotations, compilers, inheritance hierarchies, generic constraints, is a more elaborate way of answering that same question. The elaboration was never the goal. It was the cost of working around class-based architecture. Remove the classes, and the primitive is all you need.

I didn't design a type system. I demanded honesty from my code, and the type system was what honesty looked like when the dishonesty was gone.

---

*These ideas are developed at length in [Honest Code](https://honestcode.software).*

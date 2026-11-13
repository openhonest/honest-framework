<!-- Replaces lines 1--224 of honest-framework-spec.md (the title through the end of "The Patterns and the Implementations," including the horizontal rule that closes that section). -->

# The Honest Framework

## Specification Document

**Version:** 0.1 (Draft) **Date:** March 10, 2026 **Author:** Adam Zachary Wasserman

---

## Definition

The Honest Framework is an architectural standard for code that is **correct by construction**. It eliminates named categories of defect at their source, making them structurally impossible to express rather than detecting them after the fact. Each construct that manufactures a defect class (classes carrying mutable state, inheritance, value-dispatch branching, hidden state, unbounded I/O in business logic) is replaced by one that cannot represent it: pure-function dispatch tables over closed, declared vocabularies, with I/O confined to the boundary. The test for every rule is the same: *which category of defect does this make impossible?* In the Toyota Production System this is called *poka-yoke*.

The framework is aimed especially at the ways AI coding agents fail. An agent writes code fast and repeats whatever patterns it has seen, defects included. The Honest Framework does not politely ask the agent to behave. It makes those defects impossible to write.

AI coding agents treat `.md` files as suggestions or advice. They do not really constrain the agent's behavior. The Honest Framework's rules are enforced by a program, `honest-check`, which rejects code that breaks them, whether a person or an agent wrote it. Exhaustive verification (`honest-test`) runs the full bounded input space rather than sampling it. The specification is language-agnostic. The guarantees are available in ordinary imperative languages (Python, TypeScript, Java, C#, Ruby) without a new language or a body of knowledge to acquire. Adoption means stopping a few habits.

Every honest module has the same structure. Thin I/O boundary functions sit at the edges. They hold no logic, so the impure code has nothing in it that needs testing. Orchestrators receive values from the boundary functions. They hold some business logic and all the sequencing and routing needed to dispatch work to the pure functions below them. A file with the `.hd` extension, for Honest Design, declares that structure. The Honest Framework uses declarations and declarative patterns everywhere.

---

## Origin

The Honest Framework depends upon DATAOS: DOM As The Authority On State. Something that often goes unnoticed in today’s world of “state management” is that the browser already has a native state store. It is called the DOM. It is one of the founding principles: The DOM is not the output of state management; it is the user's state. With no parallel data model, there is no synchronization problem. What is in the DOM is what the user state is, full stop. This is the first *poka-yoke* to be aware of.

Every popular framework violates this. React builds a virtual DOM and a state store and then synchronizes them with the real DOM: three copies that must agree. Redux adds a fourth while mixing in a bunch of separate concerns. The entire React ecosystem is an elaborate solution to a problem that DATAOS eliminates by refusing to create it in the first place. React developers will ask "where is the state store?" The answer is: *you're looking at it*. The DOM is the state store. 

The Honest Framework also uses HATEOAS, through HTMX. The server renders its state directly into the DOM; HTMX transports the delta. There is only ever one copy of the state. The "HTMX can't handle sophisticated UI/UX" complaint is a category error. Sophisticated UI/UX is a function of HTML, CSS, and JavaScript. HTMX is simply a way of keeping that HTML, CSS, and JavaScript on the server and delivering it to the browser as needed. Keeping it on the server has an important benefit, closure, described under *Vision* below.

The framework did not begin as a framework. It began as a series of articles and papers on web application design: language-agnostic, but deeply opinionated about which language constructs are honest and which are not. Those articles became the book *Honest Code*, whose ethos is simple: **code should do what it says and say what it does.**

Writing the book forced a reckoning: most of the framework had already been built as free open-source libraries across several independent repositories, each library written in isolation. A type system here. A persistence layer there. A component model. A client-side attribute library. A checker. A test harness. None of them knew about each other, but all of them were expressions of the same principles.

The Honest Framework is the convergence of those repositories into a single coherent whole, unified around HTMX and a server-rendered, DOM-as-state model, and grounded in the Honest Code principles the book articulates.

| Repository | What it was |
|---|---|
| declaro-persistum | Declarative persistence layer |
| declaro-observe | Server-sent event observation |
| genX | DOM attribute-driven JS behavior |
| domx | Declarative DOM manipulation |
| stateless | Client-side state elimination |
| Type Magic articles | Pure function table type system concept |

---

## Vision

The enemy is **Big State**, and almost every popular framework is guilty.

Big State takes four forms:

- **Hidden state:** behavior that depends on `self`, lifecycle hooks, framework internals, or anything else the programmer cannot see at the call site. Spring beans, Django middleware, React component state, Rails `before_action`: all hidden.
- **Undifferentiated state:** no distinction between transient UI state, server session state, domain state, and configuration. Everything collapses into one mutable blob. Redux stores, Rails instance variables, Angular services: all undifferentiated.
- **Multiple sources of truth:** the database says one thing, the cache says another, the client store says a third. J2EE entity beans, React's client-side state synchronized against a server, any ORM with a dirty-tracking identity map: all duplicated truth.
- **Promiscuous state mutation**: the worst of them all. Statically typed primitives and static compilation are workarounds or mitigations of a fundamental failure mode: the failure to control mutation. Part of React’s success is its encapsulated state setters (`useState` and `useReducer`) which actively promote and constrain how state is mutated. Part of Rust’s success is the borrow checker which actively enforces and encourages the strict control and constraint of state mutation. Popular “Gang of Four” patterns in other languages create public methods which allow any caller from anywhere in the code to cause a state value to mutate. Often these are order dependent. Research in progress by the Open Honest Foundation is showing that most of a random sampling of 300 popular non-React, non-Rust repos on GitHub have a permutation space that is literally infinite, and therefore unable to be exhaustively tested, even with 100% coverage. This situation is what makes end-to-end testing necessary, and structurally inadequate at the same time.

**Closure.** In most architectures, the server has no visibility on what might be in the browser, so tests of the server code must allow for anything you can imagine reaching the surface of the server. By using server-side generated code with HTMX, this problem is eliminated (*poka-yoke*). The universe of possible states of the front end, and the possible values reaching the back end, is contained in the server code itself (this assumes Honest Code Patterns enforced in the front-end, which Honest Framework does). This produces two important benefits:

First, the contracts themselves become a type system where it matters. Not at the primitive level, where typing is a way of hoping and praying the code never encounters a type mismatch, but at the level of controlling what goes into a block of code and ensuring that what comes out of it is what the next block of code expects.

Second, we no longer need end-to-end testing. If each function is tested separately, and each I/O is tested against a real boundary (no mocks), and most importantly of all, if each decision path can be enumerated, even if the values themselves are unbounded, then the system can be rigorously tested at the unit level using limit testing and mutation testing, with no end-to-end tests needed.

This led to Honest Code, the second pillar of the Honest Framework.

**Every mainstream framework in widespread use today commits these crimes. Because of DATAOS and Honest Code, The Honest Framework commits none of them.**

Every layer (HTTP boundary, type system, persistence, UI) is built on the same principle: No business logic outside of pure functions and orchestrators, data in, data out, state only where it is declared, owned, and visible. No hidden state. No undifferentiated state. No duplicate truth, and above all: control over mutation.

For a worked example of this principle taken to its hardest case, the connection pool, the textbook case of hidden, shared, mutable state, see honest-persist §8.1.1. The pattern it shows is general: a declarative I/O surface with pure, bounded decision tables in the middle, the state threaded through as a plain value, and the I/O pushed to a single injected seam at the edge. Even the connection pool, which everyone expects to require hidden state, becomes readable, race-free, and testable against a real database with no mocks.

---

## The Four-Column Model

Every honest module is laid out in the same four parts, and that layout is the framework's canonical diagram of a module.

| Part | What it holds | Declared as |
|---|---|---|
| Input boundary | The doors the world calls through, and the readers the program calls when it needs a value from outside, such as the clock or a file it chose to open | `boundary_in`, `reader` |
| Orchestrators | The functions that run chains, call pure functions and boundaries, and decide what happens to a fault | `orchestrator` |
| Pure functions | The recognizers, classifiers, and folds that do the computing, with no I/O of any kind | `fn` |
| Output boundary | The functions that write to the outside world: responses, persistence, and emitted events | `boundary_out` |

I/O stays at the edges, and the orchestrators sit above the pure functions they dispatch to. Read across, the layout tells you where the outside world is; read down, it tells you where control goes. Work comes in through the input boundary, the orchestrators decide what to do with it, the pure functions compute the answer, and the output boundary sends it out.

A few rules hold the layout together. A plain `fn` declares no side effect and never calls a boundary. An output boundary is the end of the line, so it calls nothing. A reader is the one call that runs back toward the input, because the orchestrator asks for a value and the reader answers. Only a `boundary_in` or a `boundary_out` may raise a fault; everywhere else, a fault comes back as part of the return value. An `edge` is a pure function that a module with real boundaries also exposes for import, and it is drawn with the input boundary because it is a way in. A pure library, which has no boundaries of its own, does not need one.

Each of these rules is a *poka-yoke*: a pure function has no way to name a side effect, a boundary has no logic for untested code to hide in, and since an output boundary calls nothing, the pipeline can never loop back on itself.

The layout does not depend on the language. The same layout describes a module whether it is written in Python, JavaScript, Ruby, PHP, Elixir, Go, or anything else, and the only thing that changes from one language to the next is the code that goes into each part.

---

## The `.hd` Declaration

A `.hd` file (for Honest Design) is where a module's architecture is written down in a form a machine can read. It says what the module is, regardless of the language it is written in: the types it uses, its functions and the role each one plays, the chains that orchestrate them, the boundaries where I/O happens, the routes and entry points that reach it, and the parts of the page it renders. The format is declarative and uses indentation for scope. It has no control flow and no expressions beyond type names, and each file describes one module.

The architecture is **declared, never inferred**. For people not familiar with declaration this means three things: first it means that there is machinery (code) that interprets the declaration and acts on it, second it means that the programmer does not know how that machinery works, they can only ask for results without knowing how the results are achieved. Finally, for this to work, there has to be a declaration syntax, there has to be an absolutely unambiguous way of requesting results that can never get mixed up. That syntax is the `.hd` syntax.

`honest-check` reads the `.hd` and verifies that the code complies with it. Rule `HC-REF005` fails the build when the declaration and the source disagree in any way. It also contains all the rules that enforce the Honest Code pattern, and they run whether or not a `.hd` exists.

This is a *poka-yoke* against architectural drift: the code and its declaration either agree, or the build stops.

The same `.hd` file serves every target language without a single byte changed. The order of work is **spec, then the `.hd` declaration, then a failing test, then code**. Adding a module means writing its `.hd`, and changing a module means changing its `.hd`.

The grammar, the role keywords, the validation rules, and the tools that read the format are all specified in `../02-code-quality/honest-design-architecture.md`, which is the authoritative definition of `.hd`.

---

## Apophasis: correctness attested by refusal

There is one method that runs through the Honest Framework, and it has a name: **apophasis**, definition by negation, the *via negativa*. The framework never asserts the positive claim "this program is correct." A positive claim about behavior has to account for every behavior the program can have, and for any non-trivial system that set is unbounded and unprovable. We can, however, confidently assert the negative: "this program *cannot contain* category X." A claim about the absence of a category is falsifiable.

You cannot demonstrate correctness directly; you can make whole categories of incorrectness impossible to express and then attest their absence. Every mechanism here makes a category of bug impossible to express and then attests that it is absent, and each is a *poka-yoke*:

- **DATAOS** refuses the parallel state model. There is no second copy that could get out of sync, so the synchronization bug cannot exist.
- **Honest Code** refuses promiscuous state and unbounded branches: Pure functions ensure deterministic behavior and forbidding imperative conditionals (*If…else*) by using tables ensures that branches are enumerable.
- **honest-check** is complete and *defaults to rejecting*. There is no way to write an *if…elif* dispatch chain that the dispatch rule fails to see. It proves that forbidden shapes are absent rather than certifying that the remaining code is correct. honest-check builds an abstract syntax tree (AST) of the code at commit time, the same way a static compiler does. Because it reads the whole tree, it sees through indirection, including dispatch tables that pass first-class functions. That lets honest-check determine the end destination of every path and catch mutable values that live outside the function's encapsulation.
- **The input boundary is closed.** This does not mean listing every valid input; it means there is no channel the framework cannot inspect. A catch-all recognizer is rejected, so an unbounded input cannot even be declared.
- **User state is declared in the templates, never discovered at runtime.** The templates say which parts of the page are user state, and generation is deterministic, so it is statically knowable and checkable.
- **Every reference resolves, or the gate stops.** A reference that points at nothing fails the build.
- **Mutation adequacy.** honest-test makes small deliberate changes to the code, called mutations, and runs the tests against each one. If a mutation passes every test, the code it changed is not really tested, and the build stops. A test that compares a value with itself can never fail, so every mutation passes it, and honest-test reports it as a test that checks nothing.
- ***Poka-yoke*** is the design expression: every capability is defined by the category of bug it makes structurally impossible (`principles/poka-yoke.md`).
- **Root-cause analysis** is the debugging expression: not "X is the root cause" (a positive, unfalsifiable claim) but "under a stated evidence set and method, no upstream cause was found" (`methodology/root-cause-analysis.md`).

Every apophatic claim states its bound. honest-check is complete on limited input and best-effort-but-marked on purity. The closed boundary is closed relative to the source the one parser reads. Root-cause analysis is complete relative to its evidence set and method. You attest the completeness of a *bounded search*, never omniscience, and you say where the bound is. A positive claim does not state its bound, so the claim cannot be checked. An apophatic claim states the bound explicitly.

---

## The Third Pillar: the Architecture Explorer

The framework is not a checker plus a plugin plus a code generator stapled together. The first two pillars are DATAOS and Honest Code, and the third is a new kind of development environment: **one whose organizing unit is the architecture, not the file**.

Every mainstream IDE today treats files as the primary concept. The file tree is the navigator. Tabs are files. "Go to definition" jumps between files. Tests live in one file, templates in another, configuration in a third, and the programmer's mental model ("this module handles X, is made of these parts, and is bound to these routes") is nowhere in the tooling. The programmer keeps that model in their head and projects it onto a flat file system whenever they work.

The `.hd` file changes what is possible. Because the architecture is machine-readable, the tooling can treat it as ground truth. A module becomes a first-class unit of editing, and its functions, types, chains, dispatch tables, routes, templates, tests, and diagram become different views of the same module, arranged around the programmer rather than chased by them. The diagram becomes the navigator, and the file tree becomes an implementation detail.

Organizing a development environment around a unit other than the file is not new. Smalltalk had a class browser because the class was the unit. Lisp machines edited images because the running system was the unit. The Honest Framework makes the **architectural module** the unit.

The Architecture Explorer is that tooling. It draws the four-column diagram from any valid `.hd`, whether a person wrote the file by hand, drew it, or generated it, and it checks the declaration itself to make sure I/O stays at the edges. The design surface, which is still being built, turns the Explorer into a two-way tool: the architect draws the diagram, and the tool writes the `.hd` along with skeleton code in Python, JavaScript, TypeScript, Go, Java, Rust, or Ruby. Because the tool refuses to place I/O among the pure functions, an architect cannot even draw that mistake (*poka-yoke*). The patent covers this way of composing an architecture by drawing it, not the format or the tools that read it.

**What is open and what is commercial.** Anything that reads `.hd` is open, and the tool for drawing it is commercial. The format itself (its grammar and what it means), the reference reader that parses and validates it, and the renderer that draws the four-column diagram are all open, under the framework's standard licence tiers. The interactive design surface is the commercial product. It is sold per seat and per organization, and it is protected by trademark, by the patent, and by certification, not by the format. The split is deliberate. A file format cannot really be protected anyway, and an open format with an open reader lets every other tool and AI agent read `.hd`, which is exactly what makes a tool that produces it worth paying for.

The Explorer serves two audiences from the same engine and the same grammar. Someone building the framework itself sees every honest-* module in full four-column detail, down to every function, chain, dispatch table, and dependency between modules. Someone building an application *on* the framework sees their own modules as the main characters, while the framework modules they use (persistence, alerts, forms, auth, components) show up as labeled capabilities that say what they do, not diagrams of how they work. A repository that *is* the framework gets the first view, and a repository that lists the framework as a dependency gets the second. The `.hd` files are identical in both cases; only the presentation and the set of rules that apply are different.

The longer path is a full IDE built around the architectural module. A single engine serves every language, a small adapter handles each language's specifics, and thin plugins for VS Code, JetBrains, and any editor that speaks the Language Server Protocol put it in front of the programmer. Claude skills sit on top of that engine for the jobs that start from intent: each skill captures a recurring architectural judgment and turns a one-sentence request into the `.hd`, code, templates, and tests that judgment implies, and honest-check backstops every one of them. Once that experience outgrows a plugin, the destination is a standalone IDE. We start with plugins to find out whether they are already the best way to work with honest-framework code; a standalone IDE is worth building only if they are.

That plan commits the framework to a few things. The `.hd` format has to stay the authoritative model of the architecture, stable enough for tools to depend on and always checked against the code. honest-check, the introspector, the generator, and the diagram renderer all have to share one engine, because if they ever disagreed, the experience would fall apart. And every new architectural building block has to be designed with its presentation in mind: what it looks like on the diagram, how the tooling shows it, and how a programmer gets to it and back.

---

## The Patterns and the Implementations

The Honest Framework is a set of patterns, not a single codebase. Each pattern defines a concept: how to classify tokens, how to compose functions, how to bind a type system to HTTP, how to structure components without shared state. Each dynamic language gets its own complete, idiomatic implementation of every pattern. A Python programmer installs `honest-py` and gets everything. A Ruby programmer installs `honest-rails` and gets everything. There is no shared runtime, no cross-language package, and no hub dependency *in production code*. The code that ships to production is pure, idiomatic target-language code with no hidden framework runtime underneath it.

The **tooling** is organized the other way around, and deliberately so. A single polymorphic engine (parser, validator, intermediate representation, diagram renderer, LSP, MCP surface, skill orchestration) is shared across every language target. Each language plugs in through a narrow adapter that handles AST introspection and idiomatic code emission for its language. The tooling is one codebase; the runtimes are N codebases. This split is the engineering consequence of the Neonto principle: identical architectural experience across every target language, identical production code idioms per target.

The spec defines what each implementation must do. Each language does it in its own way.

### The Patterns

| Pattern | What the programmer gets |
|---|---|
| **Honest Code** | The prerequisite. The Honest Framework is strongly opinionated: it requires adoption of the Honest Code principles before the rest of the framework has anything to work with. The two that matter most here: **Dict-Lookup Polymorphism** replaces if/elif/else dispatch chains with dict lookup tables (`HANDLERS = {"email": send_email, "sms": send_sms}`); adding a case means adding a row, not modifying control flow. (*poka-yoke*: there is no branch to forget or misorder) **Typed Dicts Over Classes** replaces classes with plain dicts (`User = TypedDict("User", {"email": str, "name": str})`); data is just data, no behavior attached. (*poka-yoke*: there is no `self` to hide state in) These principles are the precondition for everything else in the framework. A codebase that does not follow them cannot use honest-type, cannot be checked by honest-check, and cannot be tested by honest-test. And here is what nobody told you: Honest Code is also automatically typed code. It is typed in the structural sense rather than the TypeScript sense: every value is a plain dict with declared keys, every dispatch table is a finite set of known values, every function accepts and returns declared shapes. The type information is already in the code. honest-type reads that type information; it does not add a new type system. |
| **honest-ui** | The presentation layer that started the framework. The server renders a value into an HTML element as text. The `h*-` attribute on that element is the presentation instruction: `<span hf="currency USD 2">1299.99</span>` tells the formatting module to render this text as currency, USD, 2 decimal places. The element renders as `$1,299.99`. The instruction is inline, on the element it describes, with no indirection. Seventy-three lines of JavaScript become one attribute. |
| **honest-type** | Once you have adopted Dict-Lookup Polymorphism and Typed Dicts Over Classes, those lookup tables and typed dicts are structurally identical to a type system. A Set used for dispatch is a type declaration. A collection of them is a type system. You built one by following the principles. honest-type makes it explicit: collect your existing tables into a vocabulary, add a binding table that names each slot, call `classify()`. Tokens go in, and a named dict comes out. The vast majority of types in an Honest Code codebase are Sets: finite, fully enumerable, and deterministic by definition. The permutation space is closed at definition time and honest-test generates every combination automatically. (*poka-yoke*) Predicates (`s.isdigit()`, UUID format checks) handle the edge cases that cannot be fully enumerated; honest-test applies boundary testing there. The same tables power honest-check (pre-commit checker, zero annotations) and honest-test (exhaustive harness, zero test code). |
| **honest-check** | Type checking for free. honest-check runs as a pre-commit hook, exactly like a compiler: it builds an AST, reads your honest-type declaration tables, and verifies type matching across all possible input combinations without requiring a single type annotation in your code. No mypy. No Pyright. No type declarations cluttering your source. It also checks whether your code is honest according to Honest Code principles, returning errors for serious violations and warnings for lesser ones. Developers hate writing type declarations and hate seeing them in code. honest-check means they never have to. |
| **honest-test** | Correctness testing without hand-written test cases. The same way Swagger reads your API definition and generates documentation, clients, and test interfaces automatically, honest-test reads your vocabulary definitions and generates every test case. You declare what your function accepts. The framework writes the tests, runs them, and reports. Programmers can still add BDD for functional and behavioral testing, but correctness is already covered before they write a single test. |
| **honest-persist** | Declare your schema as data. The framework computes migrations automatically by diffing your declared schema against the actual database state. No migration files to write, no linear revision chains to manage, no ORM session to reason about. (*poka-yoke*: there are no migrations to drift from the schema) Works with PostgreSQL, SQLite, and Turso with one API. Python `Literal` types become database enums automatically. Supports fluent, Django-style, Prisma-style, and pseudo-SQL query styles. Pseudo-SQL is for developers who think in SQL: write `select("id", "email", from_table="users", where="status = :s", params={"s": "active"})` and get a parameterized, schema-validated query without giving up SQL's clarity. Includes latency instrumentation, an optimistic write queue for high-latency backends, and bulk transfer between databases. |
| **honest-observe** | Think of it as an accounting ledger for your application. Accountants never change a ledger entry; they add a correcting entry. honest-observe works the same way: every event is an immutable, append-only record. (*poka-yoke*) State is derived from events via SQL projections, so you can answer any question about any point in time. You can ask not only "what is the error rate now" but also "what was the error rate for this user at 3pm yesterday and what was the exact sequence of events that preceded it." You can replay history, reconstruct any past state, and audit everything. No global loggers, no metric registries, no hidden counters. Exports to OpenTelemetry for teams that need it. Every function call is recorded automatically, so you never need a print statement. |

### The Implementations

| Layer | Python | Pure JS | React | Ruby | PHP | Elixir |
|---|---|---|---|---|---|---|
| **Server** | FastAPI | Hono / Fastify | Next.js | Rails / Sinatra | Laravel | Phoenix |
| **Templates** | Jinja2 | Nunjucks / eta | JSX / RSC | ERB | Blade | HEEx |
| **Frontend** | HTMX | HTMX | React (no HTMX) | HTMX | HTMX | HTMX |
| **DB** | honest-db | postgres.js † | postgres.js † | pg gem † | raw PDO † | Postgrex † |
| **Avoid** | SQLAlchemy | Drizzle, Knex, Prisma | Class components, Redux | ActiveRecord, Sequel | Eloquent, Query Builder | LiveView, Ecto schemas |

† honest-persist port candidate. The pattern is the same in each language: pure functions, SQL strings in, typed dicts or structs out, no model objects.

**DB notes:**
- **PHP:** raw PDO is a thin driver wrapper, honest enough, but no query safety conventions. A persistum port is worth it.
- **Elixir:** Postgrex is raw SQL with typed results. `Ecto.Adapters.SQL.query` also works. Ecto schemas are the dishonest part; skip those, keep the connection pool.
- **Pure JS / React:** postgres.js is tagged template literals over raw SQL. The most honest JS database library by far.
- **Ruby:** the pg gem directly is raw SQL. Sequel is less bad than ActiveRecord but still hides state behind method chains.

Each implementation covers all the patterns in idiomatic code for that language. If a pattern has no implementation yet, it is a specification waiting for a port. If an implementation does not follow a pattern, it is a one-off library.

---

## Comparison with Compiler-Enforced and Language-Level Purity

The Honest Framework is not the first system to pursue pure-function guarantees. Three tiers of enforcement exist in practice, and the Honest Framework's position among them is deliberate.

### Tier 1: Compiler-enforced purity (Haskell, Elm)

Haskell's IO monad makes side effects visible at the type level. A function without `IO` in its return type is provably pure by construction; the compiler rejects any attempt to perform I/O, mutate state, or read global variables without the type signature declaring it. Elm applies the same principle to frontend code. Dependent-type systems (Idris, Agda, Coq) go further still, proving termination and totality.

These languages achieve the equivalent of L1.18 = 0% by definition. The compiler enforces it. The tradeoff is adoption: Haskell, Elm, and the dependently-typed languages collectively account for fewer than 3% of developer usage. Research on human logical reasoning (the Wason Selection Task; Wason 1966, Evans 2016) predicts this: fewer than 10% of humans solve basic conditional-logic problems correctly on first attempt, and Tier 1 languages demand sustained formal reasoning with no escape hatches. They are the correct theoretical solution and the impractical one.

### Tier 2: Language-level immutability, convention-enforced purity (Elixir, Clojure, F#, OCaml)

Elixir and Erlang make data structures immutable at the language level. You cannot mutate a list or a map; every transformation produces a new value. But GenServer processes carry mutable state across calls, the BEAM actor model permits side effects (message passing, I/O, ETS table writes) without type-level marking, and nothing in the compiler prevents a GenServer-heavy codebase from exhibiting high mutable-state ratios. Purity in Elixir is a strong cultural norm, not a compiler guarantee.

Clojure provides persistent immutable data structures as defaults, but atoms, refs, and agents are explicit mutation points available to any function. F# and OCaml are functional-first but allow mutable references (`ref` cells in OCaml, `mutable` keyword in F#) without type-level distinction.

All four languages make impurity *inconvenient* without making it *impossible*. A disciplined Elixir codebase can approach L1.18 = 0%; a GenServer-heavy one can exceed 40%.

### Tier 3: Framework-enforced purity (Honest Framework)

The Honest Framework operates in Tier 0 languages — Python, TypeScript, Java, C#, Ruby, PHP — where the compiler offers zero purity enforcement and mutable state is the path of least resistance. It achieves purity guarantees through three mechanisms that together match Tier 1's mathematical strength for bounded input spaces:

**honest-check (pre-commit checker).** It runs before code enters the repository, at the point where compiling would happen, and in languages that have no compile step. Its *shape* rules — no hidden state, finite vocabularies, table-lookup instead of branching — are **complete**: they match the shape of the code and cannot be dodged. Its outside-world and run-to-run *watch-lists* are best-effort and may miss a call not on the list — but that gap is about purity, not about limited input, and honest-test covers it (see The Verification Model).

**honest-test (runs every case).** For every function that works over finite vocabularies (Set-based recognizers), honest-test lists *every* valid combination of inputs and runs the function on all of them. It calls each function twice with the same inputs and compares the outputs (a purity check). It watches for reads of hidden state, writes, outside-world calls, and network access. It snapshots inputs before and after each step (to catch writes to the input). It runs every chain twice with the same manifest (a repeat-run check). This is not sampling. Every input, every output, every combination is checked.

**honest-type (a finite, listable set of inputs).** The type system that makes running-every-case possible. Set-based recognizers fix a finite input space you can list in full at declaration time. `5 formats × 150 currencies × 4 styles = 3,000 tests`: all run, not sampled. The input space is closed when it is defined; there is no "unknown input" category for Set-based types. Open-ended recognizers (patterns like a UUID-format check) fall back to testing the edges rather than every case — this is where the framework's guarantee is weaker than Tier 1's.

### What the Honest Framework proves vs. what Haskell proves

The two guarantees are on different axes and neither subsumes the other:

| What is proved | Haskell | Honest Framework |
|---|---|---|
| **Type correctness** | Yes — the compiler proves the function's type signature is consistent with its body. "This function accepts an Int and returns a String." | Not directly — honest-check verifies chain-level type flow via set intersection, but individual function signatures are not compiler-checked. |
| **Purity** | Yes — the absence of IO in the return type is a proof of purity. | Yes, for bounded vocabularies — honest-test's double-invocation + instrumentation is an exhaustive empirical proof of purity. For unbounded inputs, it is a strong heuristic, not a proof. |
| **Behavioural correctness** | No — Haskell's types prove structural properties, not that the function produces the right output for every input. QuickCheck samples; it does not exhaust. | Yes, for bounded vocabularies — every valid input is tested, every output is compared against specification. This is a stronger guarantee than Haskell offers on the behavioural axis. |

The practical consequence: Haskell proves your code is *well-typed*. The Honest Framework proves your code *produces the correct output for every input in the bounded vocabulary*. For enterprise auditing — where the question is "does this code do what it claims?" rather than "are the types consistent?" — the behavioural guarantee is the one that matters.

### Why not just use Haskell?

Because Haskell provides those purity guarantees for 3% of the developer population and 0% of the enterprise installed base. The Honest Framework provides them for the languages enterprises already use — Python, TypeScript, Java, C#, Ruby, PHP — at a cognitive cost that does not require sustained System 2 formal reasoning. The programmer writes familiar code in a familiar language with familiar libraries. The framework enforces purity behind the scenes through tooling, not through the type system. The programmer does not need to understand monads, functors, applicatives, or higher-kinded types. They need to write pure functions with dispatch tables — a pattern that most working programmers already recognize, even if they do not use it by default.

The Honest Framework is not "Haskell for Python." Haskell's compiler-level enforcement is one mechanism for achieving a mathematical property (purity), and exhaustive enumeration of bounded input spaces is another mechanism that achieves the same property — with a different tradeoff: narrower scope (bounded vocabularies only) but available in every mainstream language.

---

## The Verification Model

Correctness is guaranteed in two stages, and the order is fixed.

**Stage one — honest-check (the structural gate).** Before any code lands, honest-check asks it one question: *can the complete set of tests be generated from what this code declares?* If not, the code is turned away at commit time. This is the gate. It runs at the same point in the workflow where compiling would, but it asks a question a compiler does not — not "do the types line up?" but "can the behaviour of this code be worked out from what it declares?"

**Stage two — honest-test (generate and run the tests).** For code that passes the gate, honest-test builds the tests from the declarations and runs them. *Defining is testing* — the developer writes no test code. Because stage one made sure the behaviour can be worked out, stage two can work it out.

The two stages run one way only: code must pass the structural gate before its behaviour can be checked. So the gate is built before the modules it has to govern — honest-check first, in a minimal form so it can check its own source, on top of the one thing it needs (the shared parser, checked by hand first) — and every module after it, honest-check included, lands only by passing it. **This is Verification First: no code that fails the framework's own gate enters the repository.** The exact build order is in *Bootstrapping a New Language Implementation* below.

### What the gate actually guarantees

What makes code checkable is **limited input**. Code becomes uncheckable when its inputs are too many or too open-ended to list — there are simply too many combinations to ever test. The framework rules this out by the shape of the code: every value a function receives is a manifest sorted into declared kinds; a finite set of allowed values can be listed in full; an open-ended check is tested at its edges; and a catch-everything recognizer — the one thing that would re-open an endless range of inputs — is rejected when the vocabulary is built. Limited input means the behaviour can be listed in full, which means it can be tested in full.

This guarantee is **complete, and it defaults to rejecting**, because it is enforced on the shape of the code: nothing unrecognized can slip an unlimited input past it, the same way there is no way to write a class that "no classes" fails to see. An unlimited set of allowed values cannot be declared in the first place.

### Two kinds of rule

honest-check's rules split by what they can promise:

- **Shape rules** — no classes, no hidden state, table-lookup instead of an if/elif that branches on a value, faults carried as data rather than thrown, finite vocabularies, every function reachable from a declared role — match shapes that hold in any language. They are **complete and default to rejecting**, and they carry the limited-input guarantee above.
- **Watch-list rules** — touching the outside world, and anything that can differ from one run to the next, spotted by the name of the call against a maintained list — answer a *different* question: not "is the input limited?" but "does the same input always give the same output?" They are lists of known-bad names, so they are best-effort: a name not on the list slips through (a new library, a call made indirectly). They are **not what the checkability guarantee rests on** — a missed outside-world call makes a function differ run-to-run for an input that is still limited — and the gap is covered another way: honest-test runs every step twice and compares, rather than the checker having to catch every case.

So honest-check is **complete on limited input**, which is what decides checkability, and best-effort on the separate question of purity. "Any code that passes honest-check is honest" is exactly true for the first and true-but-backstopped for the second.

### Running a line is not the same as testing it

Running every case proves each line ran. It does not prove that a test would fail if the line were wrong. A test can run a line and catch nothing: if the test's expected answer comes from the same code it is checking, the test passes no matter what that code does. Full coverage cannot see this, because the line did run — the gate is green and the line is untested.

Two requirements close the gap.

**A test's expected answer must come from somewhere other than the code being tested.** It comes from a value written down by hand, from a different module, or from the shared portable contract — the same `suite.json` that checks every language version — never from the output of the function under test. A test that takes its expected answer from the function it is checking will pass whatever that function does, so it proves nothing.

**Every change to the code must make at least one test fail.** The source is changed in small, mechanical ways from a fixed list — a comparison loosened from `<` to `<=`, a number shifted by one, a condition flipped, a line deleted — and each changed version is run against the whole suite. If some change makes no test fail, then no test would catch that same mistake in the real code. Coverage cannot reveal this, because the unchanged line still ran. The list of changes is finite and applied in full, the same way the input vocabularies are. This is measured only against a suite that already passes on the unchanged source: a suite failing for any other reason would register every change as caught and prove nothing. A change that cannot alter the result is set aside — but only when that is *demonstrated* (the change leaves the suite's observed output identical), never merely asserted, since an unjustified set-aside re-creates one level up the very self-checking gap this requirement closes. Such changes come in a few recurring kinds — a guard on a value the parser always supplies, a trailing return that falls through to the same value, a constant shifted in a way that preserves order — each listed by name with its reason, not left to pass silently.

The first requirement means a test cannot check itself against itself. The second means that if a line could be wrong without any test failing, the gate stops. The second also *enforces* the first: a test that takes its expected answer from the code under test cannot fail when that code is changed, so it surfaces as a change nothing caught — self-checking is not a separate rule to police by inspection, it shows up structurally as an uncaught change. Coverage shows the line ran; these two show that a mistake in the line would be caught.

### One parser, and when in doubt it rejects

Source is read with tree-sitter — the framework's only parser, chosen because the framework is one standard meant to run across many languages, and a single parser family lets the same rule shapes run on Python, Rust, C, and the rest. tree-sitter keeps going when it meets something it cannot read, marking those spots rather than dropping them; honest-check stops at the first such spot (HC-SYN). The gate never passes code it could not fully read.

### The input boundary is closed

Conventional web frameworks treat a request as an open channel — a browser running arbitrary JavaScript could send anything — so the server validates defensively against an unknown input space. The honest framework does not. The page is HTML the server rendered; HTMX sends only what the template's own attributes declare (`hx-post`, `hx-vals`, `hx-include`, and the form fields). The developer authored every one of those, so the complete set of tokens that can reach intake is fixed by the templates and readable statically at build time. And JavaScript is not an escape hatch: if a developer shapes a request with JavaScript rather than HTML attributes alone, that JavaScript is itself source they authored — read by the same parser as the templates and the server code, so the request it builds is equally knowable. No input surface escapes inspection; the single parser over every language the application touches — Python, the HTML/HTMX templates, and JavaScript — is exactly why no channel into the application is opaque.

The input space is therefore closed, just as a Set-based vocabulary is closed at definition time — there is no "unknown input" category. The contract for what enters a chain is **derived, never separately declared**: it is the manifest `classify()` produces at intake (Layer 2, below) from the tokens the templates — and any developer-authored client code — targeting that chain's route send. Requests from outside the application's own UI — third-party webhooks, partner systems — are equally closed: they enter through a declared translator (honest-observe §8c) that converts a known external shape into the canonical manifest. Either way, what reaches a chain's first link is statically knowable, so a tool can check the first link against it without running the application.

**User state is in the templates, and that is not a runtime question — READ THIS BEFORE YOU CONCLUDE ANYTHING IS "ONLY KNOWN AT RUNTIME."** The same logic covers what the page *holds*, not only what it *sends*. Which parts of the page are user state — and how to read each one — is declared in the templates: the DATAOS manifest and the elements its selectors point at. Code generation from those templates is deterministic — the same templates always produce the same code — so nothing about user state is discovered while the app runs. It is fixed by the templates and fully knowable before a line executes. Therefore any rule about user state — for example, forbidding a second copy of it kept anywhere but the page — is checkable statically, by reading the templates, at the gate. The reflex "a tool can't know which data is user state, that's a runtime thing" is wrong every time: **it is in the templates, and generation is deterministic.** This trips up readers (and tools) repeatedly; it should never trip you up again.

### Every reference resolves, or the gate stops

A boundary is not only what enters the application; it is also everything a rendered surface *points at*. An artifact the server emits — an HTML fragment, a stylesheet, a behavioural attribute — routinely names identifiers defined in another file: an `hx-get` that must reach a mounted route, an attribute value (`hf-format="currency"`) that must be a member of the closed vocabulary a client runtime recognizes, a class a stylesheet must define, a template include that must exist. Asserting the artifact *contains* the right string proves it was written; it proves nothing about whether the string it *points at* resolves. Two checks can both pass — one describing a control, one describing its target — while the control names a target nothing defines: a dead reference that renders, reports green, and does nothing.

The single parser that makes the input boundary closed makes these references closed as well. The template, the stylesheet, the client code, and the server routes are all source the framework reads, so every identifier one artifact emits can be resolved to a definition in another without running anything. A reference that resolves to no definition is a **structural** fault — the same kind of fact as an undeclared name — so it belongs at the gate, not in a running browser. An end-to-end run is the expensive way to find it: a browser meets a dead reference only incidentally, as the first thing that happens to depend on it, and pays start-up, latency, and flakiness to report what a file read decides for certain.

**The architecture declaration is a reference like any other.** Each module states its surface in its `.hd` — `fn name : (params) -> result` for every function it offers — and that declaration names identifiers defined in the source, exactly as a template names a route. The two must agree in both directions: every name in the declaration must be defined in the source, and every function in the source must be named in the declaration. A mismatch of either kind is the same defect as a route that is used but never modelled. `HC-REF005` is this rule applied between the two artifacts, and it is built when the declaration layer is (see *The build order* below, step 4). If the rule is left out, nothing checks that the declaration still matches the code. Every other rule that reads it — role reachability, orchestrator discipline, the output-boundary and awaiting rules — then silently narrows to whatever subset the `.hd` still happens to name.

The deeper remedy removes the disagreement at its source. When a feature is correct only if several hand-authored artifacts agree — the markup, the config, the stylesheet — those artifacts should be **generated from one declaration**, so they cannot disagree. The framework does the same elsewhere: one declaration is authoritative, and everything else is derived from it. The reference-resolves check covers the cases that have not yet been reduced to a single source.

---

## Bootstrapping a New Language Implementation

A new language version (after the Python reference) is not built module-first and tested after. It is built **gate-first**, in dependency order, with the checker standing up before the modules it has to certify. This is the required path; it makes the two-stage check above concrete.

### The build order

The modules depend on each other in one direction, with no cycles. Build them in an order that respects those dependencies. The full set, with each module's upstream dependencies:

```
# Leaf — depends on nothing. The one true first module, hand-checked.
parse                                              the shared parser (wraps tree-sitter)

# The .hd architecture-declaration layer (the FOSS read path; authoring tooling, not an adopter
# runtime). Second only to parse: every module below it, type included, is declared in .hd.
design     → parse                                 the .hd language layer: the tree-sitter .hd
                                                   grammar, the reader (source -> IR), the validator,
                                                   and the static renderer (IR -> the 4-column
                                                   diagram). Comes right after parse and before type —
                                                   the framework's own modules are declared in .hd,
                                                   and honest-check's conformance tier reads its IR.
                                                   The reader and static renderer are FOSS; the
                                                   interactive design surface that *produces* .hd is
                                                   commercial (see "What is open and what is
                                                   commercial"). Never imposed on adopters.

# Leaf dependency-wise (depends on nothing), but declared in .hd, so it follows design.
type                                               the type system

# Code-quality tier
errors     → type                                  the error-policy leaf: normalizers,
                                                   behavior table, rate-limiter; no I/O
gherkin    → type                                  the BDD execution engine (parse a feature,
                                                   match steps against a registry, fold/run,
                                                   report); test runs on it
check      → parse, design                         the structural gate. The universal tier (shape
                                                   rules) needs only parse and fires with no .hd
                                                   present. The declaration tier (HC-REF005,
                                                   HC-R002, HC-R003) reads design's IR against the
                                                   source, so it lands once design exists.
test       → parse, type, gherkin                  builds and runs the tests; runs feature
                                                   files through the gherkin engine
observe    → type, errors                          the event log and projections;
                                                   composes errors' normalizers
rca        → parse, check, observe                 the causal-completeness solver (apophasis
                                                   for debugging): reads observe's event log
                                                   as the evidence set, grounds deterministic
                                                   causal edges in parse/check, traces to a
                                                   fixpoint, and attests the negative — no
                                                   upstream cause found under a stated E and M
persist    → type, observe                         schema/query/transaction boundaries
                                                   emit to the event log
auth       → type                                  authentication (boundary validation): the AuthProvider contract, a value registry, the boundary dispatch
state      → type                                  the kinds of state and the single-mutator law, as data (no primitives; the law is enforced by honest-check)
features   → type, check, test, observe            feature flags as a bounded vocabulary

# Application-production tier
page       → type                                   the host-page structural contract
DOM        → type, state, observe                   DOM-as-state (DATAOS) primitives
format     → type, DOM, observe                      declarative value formatting: pure
                                                    formatter/converter tables + a DOM
                                                    binding; a value's element declares how
                                                    it reads (hf-format), no imperative call
components → type, page, observe, format             atoms / molecules / organisms
alerts     → errors, observe, persist, state, auth  server-push notifications
boot       → DOM, format, components                the client bootloader and composition root: on
                                                    load it scans the declared h*- attributes, loads
                                                    and inits the owning module (DATAOS), rescans via
                                                    the shared observer (honest.bridge) on HTMX swaps,
                                                    and emits hf.browser.classify. Last in the order —
                                                    it wires together the modules it loads. It parses
                                                    and dispatches the declared attribute tokens against
                                                    the vocabulary (data) — what the "Attribute parsing
                                                    and dispatch" section below loosely calls "classify"
                                                    — which is NOT honest-type's input recognition, so
                                                    boot does not depend on honest-type.
```

Six rules fix this order. The first governs every module; the rest order the modules against each other.

- **Inside a module, the declaration precedes the code.** The order above says which module comes next. Within each one the order is **spec, then the `.hd` declaration, then a failing test, then code**, because a module's `.hd` is what the conformance rules read it against. So the declaration is never written after the fact and never caught up on in a later pass: adding a module means writing its `.hd`, and altering a module means altering its `.hd`. `parse` is the single exception, and only once: the declaration language does not exist while `parse` is being built, so `parse` is declared at step 2 below, as soon as `design` can read a declaration. Every module after that is declared before it is built.
- **`design` second, right after `parse` and before `type`.** The `.hd` layer needs only the parser (its own tree-sitter `.hd` grammar, alongside the jinja/css grammars), so it can come as soon as `parse` exists; `parse` is the only leaf, the single artifact that must precede everything, `design` included. It comes *before* `type` — and before the whole code-quality tier — because `.hd` is the layer in which every subsequent module, `type` included, *declares* its architecture, and everything downstream is checked against those declarations. Its one hard consumer is honest-check's **conformance tier** (the rules that verify an implementation matches its declared architecture — role reachability, orchestrator discipline), which reads `design`'s IR. honest-check's **universal tier** needs only `parse` and fires without any `.hd`, so it is independent of `design`; only the conformance pass depends on `design`'s IR and lands once `design` exists. The `.hd` format and the framework's own `.hd` declarations are hand-authored and hand-checked first, before the reader automates the check — just as `parse` is "the shared parser, checked by hand first." `design` is authoring/dev tooling shipped in the repo, never a runtime dependency of an adopter's app. Its full architecture is in `../02-code-quality/honest-design-architecture.md`.
- **Leaves first, then `errors`.** `parse` and `type` depend on nothing. `errors` depends only on `type` (it returns faults as data in the shared `Result` shape). It normalizes failures into one report, decides behavior as a function of the environment, and throttles repeats. `observe` uses its normalizers and `alerts` uses its behavior table and rate-limiter, so it must precede both.
- **`gherkin` before `test`.** honest-gherkin is the BDD execution *engine* (parse a feature, match its steps against a registry, fold the scenario, report). honest-test *runs on* it — it generates the step scaffolding and ships the standard step library, and the engine runs them (honest-test §8.1, honest-gherkin §1.3). So the engine must exist before test, not the other way round; the engine itself depends only on `type` (for the `Result`/fault-as-data shape).
- **`observe` before `persist`.** Every persistence boundary (execute, apply, transactions) emits to the event log: persist instruments *through* observe. (observe's own emit stores via persist, but it receives that writer at the boundary rather than importing persist, so the dependency runs one way: persist → observe.)
- **Application tier last, and `boot` last of all.** `page`, `DOM`, `format`, `components`, and `alerts` build on the code-quality tier; `components` and `alerts` mount into `page`. `format` sits between `DOM` and `components`: it binds through the DOM's shared observer and `components` render values through its formatters. `boot` — the client bootloader and composition root — comes after them all: it scans the declared `h*-` attributes and loads, inits, and rescans the modules, so it depends on the modules it loads (`DOM`, `format`, `components`). It parses and dispatches the declared attribute tokens against the vocabulary — what the "Attribute parsing and dispatch" section below calls the client's "classify" — matching tokens against the closed vocabularies `honest-type` *declares* (used as data), which is not `honest-type`'s recognition of untrusted input (that runs at the server request boundary). So `boot` does not depend on `honest-type`. Its architecture is in `../03-application-production/honest-boot-architecture.md`.

**`parse` is the real starting point, not `check`.** The gate depends on the parser, so the parser is built and checked by hand first. A language whose grammar tree-sitter does not yet cover must add that grammar to the parser before anything else; the rest of the framework only ever reaches the parser through this one module, never tree-sitter directly. And `parse` covers more than the programming languages: the checker resolves references *across* the rendered surface — a template's `hx-get` to a mounted route, and in time a `class` to a stylesheet rule or a `{% include %}` to a template — so the template grammar, and later the style grammar, are part of what `parse` must supply before the checker can close those references ("Every reference resolves, or the gate stops," above). A reference kind cannot be checked before its grammar is in `parse`.

### Build the un-checkable parts first, then turn the gate on

Four modules cannot be checked by the tools they themselves implement until those tools exist. They are written, then checked once by hand or a small harness, to get started:

1. **Start `parse`.** Check it by hand against the parser rules: a node's text is exactly the slice of source it covers; the walk visits every node, parents before children; line and column count from 1; it reports an error exactly when the tree has one; the same input gives the same result; only known languages are accepted; text decodes correctly.
2. **Start `design`.** Write the `.hd` grammar and the reader, declare the framework's own modules in `.hd`, and check both by hand: every declaration parses, every declaration validates, and every name a declaration carries is a name the source defines. From here on a module's surface is stated on the record.
3. **Start `check`.** Write the shape rules, then run honest-check on its own source until it is clean. From here on the gate exists.
4. **Close the declaration against the code, before any module lands under the gate.** honest-check's `HC-REF005` reads each module's `.hd` against the functions its source offers and fails on any name present in one and absent from the other, in either direction, and on any disagreement in parameter count. It needs `parse` (to read the source), `design` (to read the declaration), and `check` (to host the rule), so step 4 is the earliest point it can exist. Its first run crosses the three modules that already exist by then, `parse` and `design` and `check` itself, which is also the first automated check of the declarations step 2 wrote by hand. It must also exist here rather than later, because every module from this point on declares its surface in `.hd`, and an unchecked declaration will start to diverge from the code as soon as the first commit lands. The Python reference implementation deferred this rule and the declarations drifted exactly as predicted. Measured on 2026-10-02 across its sixteen modules, reading the declarations through honest-design rather than by pattern: 219 functions declared, 1,086 defined in the source, and of the names the packages themselves export, 132 functions and 46 types that no declaration mentions. In one module the undeclared set included the function the module is named for. A new language implementation does not repeat that. It turns this rule on at step 4, so a backlog of undeclared functions cannot accumulate. Every change either adds a module, which means writing its `.hd`, or alters a module, which means altering its `.hd`. The declaration is edited with the code that it describes. The order of work inside a change is **spec, then declaration, then a failing test, then code**.
5. **Start `test`.** Write the generators, then have them check their own rules (a generator that fails to cover a declared finite set is wrong). From here on test generation exists.
6. **Gate everything else.** Every other module — and re-checking the first four — lands only by passing all six gates: honest-check (shape), the declaration crossed against the code (`HC-REF005` and the rest of the declaration tier), its own conformance suite (behaviour), full line-and-branch coverage, one gherkin scenario per function (`HC-P009`), and mutation adequacy (every change to its source caught or set aside). No code that fails the framework's own gate enters the repository.

### Two proofs per module

Each module carries two proofs, and a new version must produce both:

- **The portable contract — `suite.json`.** A language-neutral list of input/output cases (the module's rules, written as plain data). It is the shared record every version is measured against: the *same* file proves any version correct, with no particular language involved. It stays as plain data for that reason; it cannot express things like predicates, functions, or stand-in dependencies, and it is not rewritten into a language or config format.
- **The version's own generated proof.** A harness in the host language that feeds the module's own declarations through the generators and checks the module's rules across everything they generate — covering what the data file cannot reach (predicates, functions that throw, multi-part types, stand-in edges of the outside world, malformed input). This is specific to each language; it is where "defining is testing" actually happens for that language.

The portable contract says *what every version must satisfy*; the generated proof is *how this version proves itself in full*. Neither replaces the other.

### What carries across languages

A new version is not a rebuild of the whole framework from scratch. Most of the checking machinery already works for any language, and seeing that up front changes how big the job is:

- **The shape rules are shared patterns, not code to rewrite.** honest-check's shape rules match patterns in the parsed source — a class, an if/elif that branches on a value, a catch-everything recognizer — and tree-sitter is one parser family across languages. So adding the new language's grammar to the parser lets the *existing* shape rules check the new language's source. The shape stage is extended with a grammar, not rewritten per language. (The watch-list rules are the exception: outside-world and run-to-run calls are spotted by name, and the names differ per language, so each language supplies its own list.)
- **The portable contracts are shared data.** The `suite.json` files are language-neutral; the new version runs the *same* files. It writes no new contract data, only the host-language harness that loads them.
- **The generators are shared methods.** Listing a finite set in full, generating near-miss inputs, sampling the edges, walking short sequences of steps — these are plain data transforms, specified once; a port re-creates the method, not a new design.

So what is genuinely new per language is narrow: adding the grammar to the parser, the thin edge wrappers (parser, outside-world, database drivers), each language's watch-lists, and the host-language generated proof. The reusable core — rule patterns, contracts, generator methods — is the bulk, and it is reused, not rewritten.

### Completeness has to be measured

The generated proof is complete only when it reaches every line and branch of the module. **The bar is 100% line and branch coverage, enforced as a gate — and it is a real test of completeness, not a vanity number:** a line that no rule or example reaches is either dead code (delete it) or a behaviour nothing declares (declare it). Both are faults the coverage gate exposes. A new version wires this gate into its commit step alongside honest-check: nothing lands unless the conformance suites pass *and* coverage is total. The small bits of code that only run when a module is launched as a program are covered by launching it that way, not by leaving them out — the gate has no exceptions.

Coverage proves every line ran, but a line can run inside a test that checks nothing ("Running a line is not the same as testing it", above). So the bar has a second half: every mechanical change to the source, drawn from the fixed list, must make some test fail. A new version wires both into its commit step alongside honest-check: nothing lands unless the conformance suites pass, coverage is total, **and** no such change to the code passes every test.

---

## Architecture Overview

```
       ┌─────────────────────────────────────────────────────────┐
 │       The Patterns (language-agnostic spec)             |
 │                          │                              │
 │ leaves:  honest-parse  honest-type                      │
 │ quality: honest-errors  honest-check  honest-test        │
 │          honest-observe  honest-persist  honest-gherkin  │
 │          honest-auth  honest-state  honest-features      │
 │ app:     honest-page  honest-DOM  honest-components       │
 │          honest-alerts                                   │
 └──────────────────────────┬──────────────────────────────┘
               each language | implements all patterns
          ┌──────────────────┼──────────────────────┐
          │                  │                       │
  ┌───────▼──────┐  ┌────────▼──────┐  ┌────────────▼──────┐
  │  honest-py   │  │  honest-js    │  │  honest-rails     │
  │  (Python)    │  │  (Pure JS /   │  │  honest-laravel   │
  │  FastAPI     │  │   React)      │  │  honest-elixir    │
  └───────┬──────┘  └────────┬──────┘  └────────────┬──────┘
          │                  │                       │
          └──────────────────┼───────────────────────┘
                          all|server implementations share
                             │  the same client layer
                  ┌──────────▼──────────┐
                  │  honest-js          │
                  │  (Browser)          │
                  │                     │
                  │  h*- attributes → classify
                  │  HTMX       → request
                  │  domx       → observe
                  │  adapter    → React │
                  └─────────────────────┘
```

**Data flow (full request cycle):**

Every request in an honest-framework application passes through three instrumentation layers in sequence. Each layer is governed by its own spec. Each layer emits events to honest-observe automatically, with no developer instrumentation code required at any layer. The three layers are: Frontend (honest-DOM), Middleware (honest-py intake + chain), and Database (honest-persist).

---

**Layer 1: Frontend (outbound)** *Governed by: honest-DOM-architecture.md, honest-page-architecture.md*

The user interacts with the page. DOM state changes. domx detects the change via its MutationObserver and emits `hf.dom.changed` to honest-observe via `sendBeacon()`. The changed manifest slots are recorded: which keys changed and their new values. The browser keeps no copy of prior state, so honest-observe supplies the previous value as a projection over the log.

The interaction triggers an HTMX request. Before the request fires, domx calls `collect(appManifest)` and merges the current DOM state into the request body as `_state`. domx emits `hf.browser.request` to honest-observe: method, URL, trigger, target, manifest keys.

The `h*-` attributes on the triggering element declare the presentation intent. They are not classification tokens at this point; they are rendering instructions that the server will honour in the fragment it returns.

```
User interaction
  → domx: hf.dom.changed emitted  (keys changed, new values)
  → domx: collect(appManifest)    (DOM state merged into request body as _state)
  → HTMX: hf.browser.request emitted  (method, url, trigger, target)
  → HTTP request leaves browser
```

---

**Layer 2: Middleware (server boundary)** *Governed by: honest-framework-spec.md, honest-type-architecture.md, honest-check-architecture.md, honest-test-architecture.md*

The request arrives at the server. The intake middleware intercepts it before any route handler runs. It extracts all tokens from three sources: path parameters, query parameters, and `_state` from the request body. Token priority on collision: `_state` wins over query parameters; query parameters win over path parameters. This ordering reflects specificity of intent.

honest-type `classify()` runs the merged token list through the application vocabulary. Every token is either classified into a named slot or recorded as a rejection. The result is a typed manifest: a plain dict of slot names to values. `hf.classify.completed` is emitted to honest-observe: token count, rejection count, duration.

The manifest flows into the function chain. Each `@link` receives the manifest, does pure computation, and returns an updated manifest. The `@link` decorator instruments every execution automatically: `hf.link.executed` is emitted for each link with the link name, chain name, input manifest slots, output manifest slots, duration, and result. No developer logging code anywhere.

If a boundary link calls `emit()` for a business event (`order.placed`, `user.registered`, etc.), that event is appended to the honest-observe event log directly.

At the end of the request, `@catch_at_boundary` assembles `hf.request.canonical`: one dense record colocating HTTP method, path, status, caller identity, chain name, every link in sequence with results, total query count, total query duration, fault code if any, and total duration. This is the zero-join incident response record for this request.

```
HTTP request arrives
  → intake middleware: extract tokens (path + query + _state)
  → honest-type classify(): tokens → named manifest
      hf.classify.completed emitted
  → chain executes link by link:
      each @link: hf.link.executed emitted  (name, manifest in/out, duration, result)
      boundary links: business events emitted via emit()
  → @catch_at_boundary: hf.request.canonical emitted  (full request summary)
```

---

**Layer 3: Database** *Governed by: honest-persist-architecture.md*

Boundary links in the chain call honest-persist `execute()` to read or write. `execute()` is the only place SQL runs. It emits `hf.persist.query` to honest-observe from inside the call, after execution, without blocking the result: table, operation, row count, duration, `sql_hash` (always), full SQL (development mode only), `request_id` (join key to the canonical event).

Migrations run via `apply()`. Each DDL operation emits `hf.persist.migration`: table, operation, SQL executed, duration, success. Schema history is in the event log.

Pool lifecycle events (exhausted, retry, error) emit `hf.persist.pool`. Write queue stalls emit `hf.persist.queue_stalled`.

The chain link assembles the server response: an HTML fragment with `h*-` attributes that carry the presentation instructions for the returned values.

```
Boundary link calls execute():
  → SQL runs against connection pool
  → hf.persist.query emitted  (table, op, rows, duration, sql_hash, request_id)
  → result returned to link as typed records (plain dicts)
  → link assembles HTML fragment with h*- attributes
  → fragment returned through chain to @catch_at_boundary
  → HTTP response leaves server
```

---

**Layer 1: Frontend (inbound)** *Governed by: honest-DOM-architecture.md*

The HTTP response arrives in the browser. HTMX swaps the fragment into the target element. domx emits `hf.browser.response` to honest-observe: status, target, round-trip duration, `request_id` (joins to the server's canonical event, completing the full trace).

The new fragment contains `h*-` attributes. The honest-ui bootloader scans the swapped subtree, classifies each attribute through the module vocabulary, and dispatches a typed manifest to the appropriate module. `hf.browser.classify` is emitted for each element classification. `$1,299.99` appears where `1299.99` was. The table sorts. The skeleton disappears.

domx observes the DOM changes caused by the swap and by module execution. `hf.dom.changed` is emitted. The manifest is updated. The cycle is complete and ready for the next interaction.

```
HTTP response arrives
  → HTMX: fragment swapped into target element
  → domx: hf.browser.response emitted  (status, duration, request_id)
  → bootloader: scans new elements for h*- attributes
      hf.browser.classify emitted per element
      modules execute, DOM updated
  → domx: hf.dom.changed emitted  (manifest updated)
  → cycle ready
```

---

**Example: `honest-observe inspect` output for one request**

| timestamp | event | layer | description |
|---|---|---|---|
| 14:23:07.001 | `hf.dom.changed` | frontend | user changed filter |
| 14:23:07.003 | `hf.browser.request` | frontend | POST /api/items sent |
| 14:23:07.004 | `hf.classify.completed` | middleware | 3 tokens, 0 rejected |
| 14:23:07.005 | `hf.link.executed` ×1 | middleware | validate_filters ok |
| 14:23:07.006 | `hf.link.executed` ×2 | middleware | build_query ok |
| 14:23:07.007 | `hf.persist.query` ×1 | database | SELECT items 47 rows |
| 14:23:07.019 | `hf.link.executed` ×3 | middleware | format_response ok |
| 14:23:07.020 | `hf.request.canonical` | middleware | POST 200 16ms summary |
| 14:23:07.163 | `hf.browser.response` | frontend | 200 160ms #content |
| 14:23:07.165 | `hf.dom.changed` | frontend | #content-area swapped |
| 14:23:07.168 | `hf.browser.classify` ×12 | frontend | new elements typed |

One `request_id` joins every event in this sequence. `honest-observe inspect <request_id>` renders all of them interleaved by timestamp, browser and server together, with timing breakdowns: total, server, network, browser. The developer writes no instrumentation and no print statements.

**A note on performance.** Anyone who suspects this instrumentation layer will slow things down has the architecture backwards. Pure functions doing pure computation with no I/O waiting is what CPUs do best. The honest framework benchmark data at honestcode.software shows what happens when you strip out hidden state, remove synchronization overhead, eliminate the ORM, and use efficient memory layout: the numbers are not worse. They are significantly better. But correctness and safety matter more than performance: a system where every boundary is typed, every function is pure, every input is classified before it reaches any logic, and every mutation is detected and reported cannot produce the class of bugs that most production incidents trace back to. Visit honestcode.software for the evidence.

---

## Project 1: `honest-type`

honest-type is specified in full in `../02-code-quality/honest-type-architecture.md`: the recognizers, the vocabulary, the binding table, the two-pass `classify()` algorithm, composed types, Maybe, the chain execution model, fault and rejection semantics, and the cross-language conformance suite. An implementor can build a conformant honest-type from that document alone.

`honest-check` and `honest-test` grew out of this project and now have architecture documents of their own, `../02-code-quality/honest-check-architecture.md` and `../02-code-quality/honest-test-architecture.md`.

---

## Project 2: `honest-py`

### Purpose

Python server framework. Pure functions, typed boundaries, declarative persistence. Designed to work with FastAPI (or any ASGI server) as the HTTP layer. honest-py is the application architecture inside a web server, not a web server itself.

### Component Map

| Component | Name | Absorbs | What It Does |
|---|---|---|---|
| Persistence | **honest.persist** | declaro-persistum | Pure functional SQL. Schema-first, state-diffing migrations, connection pools. No ORM. |
| Observability | **honest.emit** | declaro-observe | Event sourcing. Events as data, state as derived. Middleware integration. |
| Routing | **honest.routes** | (new) | Declarative route table with typed parameter binding via honest-type. |
| Request binding | **honest.intake** | (new) | HTTP request → token classification → manifest. The server-side chokepoint. |
| Function chains | **honest.chain** | (new, uses honest-type) | Pipeline composition with typed links. The core application pattern. |
| Error flow | **honest.fault** | (new) | Rejection propagation through chains. Typed exceptions at the boundary. |

### honest.routes: Declarative Routing

Routes are a binding table. URL segments and query parameters are tokens. Recognizers classify them. This is Type Magic applied to HTTP.

```python
from honest.routes import routes
from honest_type import vocabulary, binding

# The route vocabulary
api_vocab = vocabulary({
    "resource":  {"users", "workspaces", "cards", "filters"},
    "action":    {"list", "create", "update", "delete", "search"},
    "uuid":      predicate(lambda s: len(s) == 36 and s[8] == "-"),
    "integer":   predicate(lambda s: s.isdigit()),
})

api_binding = binding({
    "resource": "resource",
    "action":   "action",
    "uuid":     "id",
    "integer":  "page",
})

app_routes = routes(
    vocab=api_vocab,
    bind=api_binding,
    handlers={
        ("users", "list"):    list_users,
        ("users", "create"):  create_user,
        ("cards", "search"):  search_cards,
    },
)
```

### honest.intake: Request Binding

ASGI middleware that classifies and binds request parameters before they reach handler functions.

```python
from honest.intake import intake

# As FastAPI middleware
app = FastAPI()

@app.middleware("http")
async def type_magic(request: Request, call_next):
    manifest = intake(
        tokens=extract_tokens(request),
        vocab=app_vocab,
        bind=app_binding,
        context=app_context,
    )
    if manifest.rejections:
        return JSONResponse(status_code=400, content={
            "rejected": manifest.rejections,
        })
    request.state.manifest = manifest
    return await call_next(request)
```

### honest.persist: Pure Functional SQL

```python
from honest.persist import table, query, migrate, pool

# Schema declaration (Pydantic for structure, honest-type for validation)
@table
class User(TypedDict):
    id: str
    email: str
    workspace_id: str
    tier: str

# Pure query functions
async def find_user(conn, user_id: str) -> User | None:
    return await query(conn, "SELECT * FROM users WHERE id = $1", [user_id])

# State-diffing migrations
async def migrate_db(conn):
    await migrate(conn, desired=[User, Workspace, Card])
    # Computes DDL by diffing desired schema vs actual database state

# Connection pool (no global state)
async with pool(config) as conn:
    user = await find_user(conn, manifest["id"])
```

### honest.fault: Error Flow

Rejections and errors flow through chains as data, not exceptions. Exceptions only happen at the HTTP boundary.

A fault carries five fields, all of them always present: `code`, `message`, `category`, `results`, and `detail`. The message names the facts in a sentence a person reads; `detail` carries those same facts as data a caller or a test can read. There are no optional fields and no implicit defaults. The authoritative schema is in `../02-code-quality/honest-type-architecture.md` section 13.2.

```python
from honest.fault import fault, catch_at_boundary

# Inside a chain, faults are data. A fault bubbles up by return, caller to caller,
# out to the boundary. Every field is passed; nothing defaults.
def validate_email(manifest: dict) -> dict | fault:
    if "@" not in manifest.get("email", ""):
        return fault(
            "invalid_email",
            f"Bad email: {manifest.get('email')}",
            "client",
            [],
            {"email": manifest.get("email")},
        )
    return manifest

# At the HTTP boundary, faults become responses
@catch_at_boundary
async def create_user_handler(request: Request):
    result = pipeline(request.state.manifest)
    # If result is a fault, catch_at_boundary returns 400/422
    # If result is data, it proceeds normally
    return result
```

### honest.chain: Function Composition

```python
from honest.chain import chain

# Each function in the chain is a pure function
# honest-type ensures type compatibility between links

create_user_pipeline = chain(
    validate_email,      # manifest → manifest | fault
    check_duplicate,     # manifest → manifest | fault
    hash_password,       # manifest → manifest
    insert_user,         # manifest → user_record
    format_response,     # user_record → response_dict
)

# The chain short-circuits on fault
result = await create_user_pipeline(manifest)
```

---

## Project 3: `honest-js`

### Purpose

Browser framework. Declarative UI behavior via HTML attributes. DOM as the single source of truth. Typed attribute binding via honest-type.

### Relationship to HTMX

honest-js **sits on top of HTMX**, not instead of it. HTMX handles the HTTP-over-the-wire layer: `hx-get`, `hx-post`, `hx-target`, `hx-swap`, `hx-trigger`. It fetches HTML fragments from the server and swaps them into the DOM. That's HTMX's job and honest-js doesn't duplicate it.

honest-js handles everything else: formatting, accessibility, drag-and-drop, data binding, tables, loading states, DOM state observation. Its `h*-` prefixed attributes complement HTMX's `hx-` attributes. They work together on the same elements.

**A React adapter is community, not core.** React owns its own rendering pipeline, so a React adapter cannot sit on HTMX the way the `h*-` modules do; it wraps domx's DOM observation into React hooks (`useDomState`, `useDomValue`) so components read state from the DOM instead of a separate copy — the DATAOS principle inside React's world. But it carries React as a runtime dependency, which would pull unverified third-party code into the framework's dependency-free test closure. So a React adapter is a community contribution, not a shipped or gated framework component (honest-DOM §1.1, §4).

### Component Map

| Component | Name | Absorbs | Attribute Prefix | What It Does |
|---|---|---|---|---|
| DOM state | **honest.observe** | domx | (none) | Collect, apply, observe DOM state. Single MutationObserver. |
| Formatting | **honest.format** | genX fmtX | `hf-*` | Currency, dates, numbers, phones, relative time, percentages, file sizes. |
| Accessibility | **honest.access** | genX accX | `ha-*` | WCAG, ARIA attributes. |
| Loading | **honest.load** | genX loadX | `hl-*` | Skeletons, spinners, loading states. |
| Navigation | **honest.nav** | genX navX | `hn-*` | Client-side routing, URL management. |
| Drag & drop | **honest.drag** | genX dragX | `hd-*` | Drag sources, drop zones, visual feedback. |
| Data binding | **honest.bind** | genX bindX | `hb-*` | Reactive two-way data binding. |
| Smart detect | **honest.smart** | genX smartX | `hs-*` | Auto-detection formatting. |
| UI enhance | **honest.ui** | genX uiX | `hu-*` | UI enhancements. |
| React adapter (community) | honest.react | stateless | (none) | Community contribution, not shipped or gated: it carries React as a dependency, outside the framework's test closure. `useDomState`, `useDomValue`, `useDomArray`, `useDomMap` hooks over domx. |
| Bootloader | **honest.boot** | genX bootloader | (none) | Scans DOM for `h*-` attributes, lazy-loads modules on demand. |
| DOM bridge | **honest.bridge** | genX domx-bridge | (none) | Centralized MutationObserver shared by all modules. |

### honest-ui: The Type System in the Markup

honest-ui is the name for the `h*-` attribute system as a whole. It is not a separate package; it is the point where honest-type vocabularies surface in the browser. Every `h*-` attribute on an HTML element is a type declaration: inline, at the point of use, with no indirection. The type information sits on the element itself. There is no separate schema file to find, no annotation to trace back to an interface, no documentation to consult.

Applied to markup, Honest Code's rule is the same: the code says what it does at the place it does it.

### Attribute parsing and dispatch (the client's "classify")

An `h*-` attribute value is a declared string the developer wrote. The bootloader parses it — including the unordered "Type Magic" form below, where it works out which token is the format, which the currency, which the decimals — and dispatches each to its owning module, matching tokens against the closed vocabularies `honest-type` *declares* (used as data). This parse-and-dispatch of already-declared values is the client's "classify"; it is NOT `honest-type`'s `classify()` of untrusted input, which recognizes an open input space and runs at the server request boundary. The two share only the word — see the glossary entry for **classify**.

```html
<!-- The attribute value "currency USD 2" is three tokens -->
<span hf-format="currency" hf-currency="USD" hf-decimals="2">1299.99</span>

<!-- Or, with Type Magic, a single attribute with unordered tokens -->
<span hf="currency USD 2">1299.99</span>
```

The bootloader passes `"currency USD 2"` through honest-type:
```javascript
import { classify } from 'honest-type'

const manifest = classify(
  ['currency', 'USD', '2'],
  formatVocab,
  formatBinding,
  formatContext
)
// { format: 'currency', currency: 'USD', decimals: 2 }
```

The module receives a typed manifest, not raw strings. The DOM attribute is the boundary. honest-type is the chokepoint.

### honest.observe: DOM State (from domx)

```javascript
import { collect, apply, observe, send, replay } from 'honest-js/observe'

// Collect state from DOM
const state = collect({
  username: { selector: '#username', read: 'value' },
  agreed:   { selector: '#tos',      read: 'checked' },
})

// Observe changes (single MutationObserver)
const unsub = observe(manifest, (newState) => {
  console.log('DOM changed:', newState)
})

// Send with cache-and-replay (page refresh recovery)
send('/api/submit', manifest)
replay() // on page load, re-sends cached request
```

### honest.react: React Bridge (from stateless)

```jsx
import { useDomState, useDomValue, useDomArray } from 'honest-js/react'

function FilterPanel() {
  const filters = useDomState({
    search:   { selector: '#search',   read: 'value' },
    category: { selector: '#category', read: 'value' },
    sort:     { selector: '#sort',     read: 'data:sort-dir' },
  })

  // filters updates automatically when DOM changes
  // No useState. No useEffect. No sync bugs.
  return <Results filters={filters} />
}
```

### Bootloader Architecture

```javascript
// honest.boot scans for any h*- prefixed attributes
// Loads only the modules actually used on the page
// Single shared MutationObserver via honest.bridge

// On DOMContentLoaded:
// 1. Scan document for h*- attributes
// 2. Determine which modules are needed (hf- → honest.format, hd- → honest.drag, etc.)
// 3. Dynamic import only those modules
// 4. Initialize with shared observer
// 5. Watch for new elements (HTMX swaps, dynamic content)
```

---

## Rails Integration: `honest-rails`

A gem that bolts honest-type onto Rails via Rack middleware and ActiveSupport conventions.

### Rack Middleware (The Chokepoint)

```ruby
# lib/honest/middleware.rb
module Honest
  class TypeMagic
    def initialize(app, vocab:, bind:, context: nil)
      @app     = app
      @vocab   = vocab   # { type_name: Set or Proc }
      @bind    = bind    # { type_name: slot_name }
      @context = context # { [ctx, type] => slot_name }
    end

    def call(env)
      request = Rack::Request.new(env)
      tokens  = extract_tokens(request)
      manifest = classify(tokens, @vocab, @bind, @context)

      if manifest[:rejections].any?
        return [400, { 'Content-Type' => 'application/json' },
                [manifest[:rejections].to_json]]
      end

      env['honest.manifest'] = manifest
      @app.call(env)
    end

    private

    def classify(tokens, vocab, bind, context)
      # Identical algorithm to Python and JS implementations
      # Ruby Sets and lambdas map directly
    end
  end
end
```

### Railtie Integration

```ruby
# lib/honest/railtie.rb
module Honest
  class Railtie < Rails::Railtie
    initializer 'honest.configure_middleware' do |app|
      app.middleware.use Honest::TypeMagic,
        vocab:   Honest.configuration.vocab,
        bind:    Honest.configuration.bind,
        context: Honest.configuration.context
    end
  end
end
```

### Controller Integration

```ruby
# app/controllers/application_controller.rb
class ApplicationController < ActionController::Base
  include Honest::Typed

  # Access the classified manifest instead of raw params
  def manifest
    request.env['honest.manifest']
  end
end

# app/controllers/cards_controller.rb
class CardsController < ApplicationController
  # Vocabulary declared per-controller (composable)
  honest_vocab(
    card_type: Set['note', 'reference', 'bookmark'],
    priority:  Set['low', 'medium', 'high', 'critical'],
    uuid:      ->(s) { s.match?(/^[0-9a-f-]{36}$/) },
  )

  honest_bind(
    card_type: :type,
    priority:  :priority,
    uuid:      :id,
  )

  def create
    # manifest[:type] is guaranteed to be one of note/reference/bookmark
    # manifest[:priority] is guaranteed to be one of low/medium/high/critical
    # No params.require().permit() ceremony
    Card.create!(manifest.slice(:type, :priority, :title))
  end
end
```

---

## Naming Conventions

### Project Names

| Project | Gem/Package Name | Import Path |
|---|---|---|
| Core type system (Python) | `honest-type` | `from honest_type import ...` |
| Core type system (JS) | `honest-type` | `import { ... } from 'honest-type'` |
| Python framework | `honest-py` | `from honest.persist import ...` |
| JavaScript framework | `honest-js` | `import { ... } from 'honest-js'` |
| React bridge | `honest-js` (subpath) | `import { ... } from 'honest-js/react'` |
| Rails gem | `honest-rails` | `require 'honest'` |
| Checker | `honest-check` | CLI: `honest-check src/` |
| Testing harness | `honest-test` | CLI: `honest-test src/` |

### Internal Naming Rules

1. **No classes.** Everything is a function or a dict/object. If you find yourself writing `class`, stop.
2. **Functions are verbs:** `classify`, `recognize`, `bind`, `chain`, `check`, `collect`, `observe`, `emit`, `query`, `migrate`.
3. **Data structures are nouns:** `vocabulary`, `binding`, `manifest`, `ticket`, `rejection`, `fault`, `link`, `token`.
4. **Composition uses `|` (pipe/merge):** `vocab_a | vocab_b` merges vocabularies. `binding_a | binding_b` merges bindings.
5. **No abbreviations except established ones:** `hf-` (honest format), `hd-` (honest drag), etc. for HTML attribute prefixes.
6. **Attribute prefixes are two letters:** `h` + first letter of module name. This mirrors the existing genX convention but unifies under `h`.

### HTML Attribute Prefix Registry

| Prefix | Module | Example |
|---|---|---|
| `hf-` | honest.format | `<span hf-format="currency" hf-currency="USD">` |
| `ha-` | honest.access | `<button ha-label="Submit form">` |
| `hl-` | honest.load | `<div hl-skeleton="3 lines">` |
| `hn-` | honest.nav | `<a hn-route="/users">` |
| `hd-` | honest.drag | `<div hd-draggable="card">` |
| `hb-` | honest.bind | `<input hb-model="username">` |
| `hs-` | honest.smart | `<span hs-detect>42.5%</span>` |
| `hu-` | honest.ui | `<div hu-tooltip="Help text">` |

---

## What Needs To Be Built (Priority Order)

### Phase 1: Core (honest-type)

honest-type has to exist first, because honest-py, honest-js, and the rest of the framework depend on it.

1. **Recognizer engine:** Set membership + predicate evaluation. Both Python and JS.
2. **Vocabulary composition:** Merge operator (`|`) with conflict detection.
3. **Flat binding:** Type → slot resolution.
4. **Context-sensitive binding:** (context_type, token_type) → slot resolution.
5. **Manifest construction:** Token sequence → classified, bound manifest.
6. **Rejection handling:** Unrecognized tokens as data, not exceptions.
7. **honest-check:** Chain validation via set intersection.
8. **honest-test harness:** Exhaustive permutation testing, purity verification, chain contract testing, rejection boundary testing, idempotency proof. The Swagger of type systems.
9. **Test suite for honest-type itself:** Exhaustive. Every permutation of every bounded vocabulary. This is the proof that bounded vocabularies are exhaustively testable.

### Phase 2: Server (honest-py)

Build on the existing declaro libraries.

1. **honest.intake:** ASGI middleware for request classification. The server-side chokepoint.
2. **honest.chain:** Function composition with typed links and fault propagation.
3. **honest.fault:** Rejection/error flow as data through chains.
4. **honest.routes:** Declarative route tables using honest-type vocabularies.
5. **honest.persist:** Port declaro-persistum under new namespace.
6. **honest.emit:** Port declaro-observe under new namespace.

### Phase 3: Client (honest-js)

Build on the existing genX, domx, and stateless libraries.

1. **honest.boot:** Bootloader rewritten to scan for `h*-` prefixes.
2. **honest.bridge:** Centralized MutationObserver (port domx-bridge).
3. **honest.observe:** DOM state collection/observation (port domx).
4. **Attribute classification:** honest-type integration into the bootloader. Attribute values pass through `classify()` before reaching modules.
5. **honest.format:** Port fmtX with honest-type attribute binding.
6. **Remaining modules:** Port each genX module under `h*-` prefix.
7. **honest.react:** Port stateless hooks, backed by honest.observe.

### Phase 4: Rails (honest-rails)

After core is stable.

1. **Rack middleware:** honest-type classification in the request pipeline.
2. **Controller mixin:** `Honest::Typed` with `honest_vocab` and `honest_bind` DSL.
3. **View helpers:** Generate `h*-` prefixed attributes from server-side vocabularies.
4. **Generator:** `rails generate honest:vocabulary currencies` scaffolding.

---

## The Credibility Argument

The framework extracts and codifies principles that have been validated at production scale across multiple complex applications.

The Honest Code book establishes the philosophical case. Type Magic (the future book) establishes the theoretical case. The Honest Framework is the implementation.

The sequence:
1. **Honest Code** (published): tears down the justification for class-based programming
2. **The Honest Framework** (this): provides the replacement
3. **Type Magic** (future book): explains why it works, formally

---

## Key Differentiators vs. Existing Frameworks

| Concern | Django/Rails/Next.js | Honest Framework |
|---|---|---|
| Type system | Language-native or bolted-on (mypy, TS) | Pure function tables. Same mechanism everywhere. |
| Static checking | Separate tool, different semantics than runtime | Same predicate tables at pre-commit and runtime. Zero drift. |
| State management | Redux, Zustand, signals, etc. | DOM is the state. No sync layer. |
| Frontend behavior | JavaScript files | HTML attributes. No JS to write. |
| Persistence | ORM (ActiveRecord, SQLAlchemy) | Pure SQL, schema-first, state-diffing migrations. |
| Validation | Schema objects (Pydantic, Zod, ActiveModel) | Recognizer tables at every boundary. |
| Error handling | Exceptions everywhere | Faults as data through chains, exceptions only at boundary. |
| Architecture | MVC with classes | Function chains with typed links. |

---

## Related Work and Prior Art

The specific formulation of pure function tables as a type system appears to be novel. No published research or academic paper directly describes using pure function tables as a type system.

**Adjacent fields:**

- **Predicate dispatch** (Ernst et al.): generalizes multiple dispatch via predicates, but within typed languages
- **Predicate subtyping** (PVS, Typed Racket): predicates refine existing types, not classify raw strings
- **Qualified Types** (Mark Jones): predicates on types in Haskell, but compile-time and statically-typed
- **Intent detection and slot filling** (NLP): fills slots probabilistically, which is the exact inverse of classifying against a closed vocabulary
- **Declarative Signals** (2024 browser proposals): moving toward attribute-driven behavior, but without a type system framing
- **htmx, Unpoly, Turbo:** server-rendered HTML with DOM swaps, but no unified type system across boundaries

**The thesis that appears unoccupied:**

A Set used to check whether a value belongs has the same shape as a type declaration. A collection of such checks is a type system. A table mapping recognized types to named slots is a binding rule set. Together they sort untyped inputs into typed slots without needing a compiler, a static type system, or guesswork.

The enemy of early type checking is classes, not dynamicism.

---

## Language Roadmap

honest-type is implementable in any language with Sets and first-class functions. The priority is driven by community size, receptiveness to the thesis, and book audience alignment.

### Phase 1: Core (Build First)

| Language | Package | Why |
|---|---|---|
| **Python** | `honest-type`, `honest-py` | Home turf. FastAPI ecosystem. |
| **JavaScript** | `honest-type`, `honest-js` | Browser-side is mandatory. Also covers Node/Deno/Bun server. |

### Phase 2: Bolt-On (Major Frameworks)

| Language | Package | Why |
|---|---|---|
| **Ruby** | `honest-type`, `honest-rails` | Rails is the canonical bolt-on target. Rack middleware is a natural fit. Large legacy install base hungry for modernization. |

### Phase 3: Expand

| Language | Package | Why |
|---|---|---|
| **PHP** | `honest-type`, `honest-laravel` | Laravel is the Rails of PHP. Enormous install base. PHP 8+ has Sets and first-class callables. Community wants legitimacy: this gives it to them. |
| **Elixir** | `honest-type` | Already functional, already honest by default. Small community but the loudest evangelists. Would validate the thesis from the other direction. |

### Phase 4: Stretch

| Language | Package | Why |
|---|---|---|
| **Go** | `honest-type` | Not dynamic, but deliberately simple type system. Go developers already use map lookups as dispatch tables. honest-type would feel native. |

### Languages to Skip

- **Java/Kotlin/C#/Swift:** Static, class-based. These are the *target* of the critique, not the audience. Porting would dilute the argument.
- **Rust:** Already has the strongest type system. No need.
- **Lua:** Tables are already the only data structure. Lua is already a pure function table language. Worth mentioning in Type Magic as "Lua was honest all along."
- **Dart:** Too class-heavy, too Google-controlled.

### Package Name Availability (All Verified March 2026)

| Registry | Names Checked | Status |
|---|---|---|
| PyPI | honest-type, honest-py, honest-check, honest-test | All available |
| npm | honest-type, honest-js, honest-check, honest-test | All available |
| RubyGems | honest-type, honest-rails, honest-check, honest-test | All available |
| Packagist (PHP) | TBD | Not yet checked |
| Hex (Elixir) | TBD | Not yet checked |

---

## Reference Materials

The following are included in this repository for reference:

- `honestcode/`: Honest Code companion website (landing page, chapter evidence, testimonials)
- `honest-code-traces/`: Execution traces for all 13 chapters across multiple languages (Python, JavaScript, TypeScript, Java, C#, Kotlin, Swift, PHP, Ruby, Dart, C++, Go). Includes Dockerfile, generation harness, and raw results. These traces power the honestcode.software comparison tool.

---

## Companion Specifications

The following documents extend and distill the framework specification. They are canonical: when they conflict with this document, they are newer and correct. Every module in the build order above appears here, except `parse`, which is specified in prose in this document and by `specs/features/honest-parse.feature`.

### Code Quality Axis

- **`honest-code-principles.md`:** Twenty practices that describe what correct code looks like at the level of daily programming decisions. The distillation of the code quality axis.
- **`honest-persist-architecture.md`:** Language-agnostic architecture specification for honest-persist. Defines exact algorithms, data structures, and conformance requirements. An implementor can build a conformant honest-persist from this document alone.
- **`honest-type-architecture.md`:** Architecture specification for honest-type. Includes the classify() algorithm, composed types, maybe bindings, chain execution model, fault semantics, and conformance suite.
- **`honest-check-architecture.md`:** Complete rule set for the static checker. CLI, LSP, startup integration, and all HC and HC-P rules with algorithms.
- **`honest-design-architecture.md`:** The `.hd` architecture-declaration language: the grammar, the four-column model it expresses, the reader that produces the IR, the validator, and the static renderer. Second in the build order, right after `parse`.
- **`honest-errors-architecture.md`:** The report IR, normalization, the behaviour policy table, the rate limiter, and the email-body formatter. Its normalizers are used by observe and its policy by alerts.
- **`honest-gherkin-architecture.md`:** The BDD execution engine: the source-level IR, pattern compilation, the step registry, the execution model, and the fault vocabulary. honest-test runs on it.
- **`honest-rca-architecture.md`:** The causal-completeness solver, apophasis applied to debugging: the causal IR, evidence hashing, edge construction, fixpoint traversal, and the attestation that makes a fake root cause unrepresentable.
- **`honest-auth-architecture.md`:** The `AuthProvider` contract, provider registration, and boundary actor resolution. Authentication only; what an actor may do is ordinary business logic.
- **`honest-features-architecture.md`:** Feature flags as a bounded vocabulary, flag state as a value, the handler table pattern, the toggle API, and the A/B middleware.
- **`honest-estimate-architecture.md`:** Size, cost, and duration estimated from the `.hd` surface, in three dimensions never fused into one number. Authoring tooling, not in the build order.
- **`honest-test-architecture.md`:** Complete specification for the test harness. Auto-generated tests, honesty tests, BDD runner, state machine testing, and coverage model.
- **`honest-state-architecture.md`:** The six kinds of state, the single-mutator law, and each kind's home module (user state is DATAOS in honest-DOM; state machines are honest-type). honest-state defines no primitives of its own.
- **`honest-observe-architecture.md`:** Event sourcing, projections, OTel export, and honest-framework semantic conventions.

### Application Production Axis

- **`honest-components-architecture.md`:** Three-tier component hierarchy (atoms, molecules, organisms). Language-agnostic interface contract. Multi-target implementation structure. The Neonto principle: one component package, one idiomatic implementation per target language, no runtime abstraction layer in production.
- **`honest-page-architecture.md`:** Base page contract: six required surfaces, bootstrap sequence, honest-alerts SSE wiring, CSS custom property token set, dark mode switching, Jinja2 block contract, and honest-py intake integration.
- **`honest-DOM-architecture.md`:** Client-side DATAOS implementation: collect(), apply(), observe(). Reference implementations: domx and stateless.
- **`honest-alerts-architecture.md`:** Actor model message passing. Mailbox as projection. send_and_wait() coroutine primitive.
- **`honest-format-architecture.md`:** Declarative value formatting: the `hf-*` attribute grammar, the format vocabulary, the formatter contract, and the declared vocabulary manifest HC-REF004 resolves authored values against.
- **`honest-boot-architecture.md`:** The client bootloader and composition root. On load it scans the declared `h*-` attributes, loads and initialises the owning module, and rescans on HTMX swaps. Last in the build order.

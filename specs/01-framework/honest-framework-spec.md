# The Honest Framework

## Specification Document

**Version:** 0.1 (Draft)
**Date:** March 10, 2026
**Author:** Adam Zachary Wasserman

---

## Origin: One Observation

Honest framework exists because of one initial observation: the browser already has a state store. It is called the DOM. Everything built on top of that observation is honest framework. Anything else is dishonest. Once I started looking, I saw dishonesty everywhere.

This is DATAOS: DOM As The Authority On State. It is not a library. It is not a pattern. It is the founding principle. The DOM is not the output of state management; it is the user’s state. There is no parallel data model. There is no synchronization problem. What is in the DOM is what the user state is, full stop.

Every popular framework violates this. React builds a virtual DOM and a state store and then synchronizes them with the real DOM: three things that must agree. Redux adds a fourth while mixing in a bunch of separate concerns. The entire React ecosystem is an elaborate solution to a problem that DATAOS eliminates by refusing to create it in the first place. HTMX does not create it either. The server renders its state directly into the DOM; HTMX transports the delta. One copy. Always.

The "HTMX can't handle sophisticated UI/UX" complaint is a category error. React developers ask "where is the state store?" The answer is: *you’re looking at it*. The DOM is the state store. Honest framework is the architecture that makes that answer sufficient for any application, no matter how sophisticated.

---

## Vision

The enemy is **Big State**, and every popular framework is guilty.

Big State takes three forms:

- **Hidden state:** behavior that depends on `self`, lifecycle hooks, framework internals, or anything else the programmer cannot see at the call site. Spring beans, Django middleware, React component state, Rails `before_action`: all hidden.
- **Undifferentiated state:** no distinction between transient UI state, server session state, domain state, and configuration. Everything collapses into one mutable blob. Redux stores, Rails instance variables, Angular services: all undifferentiated.
- **Multiple sources of truth:** the database says one thing, the cache says another, the client store says a third. J2EE entity beans, React's client-side state synchronized against a server, any ORM with a dirty-tracking identity map: all duplicated truth.

J2EE and Spring made hidden state an enterprise mandated architecture. Rails made multiple sources of truth a convention (over configuration!). In true Python fashion, Django inherited both. React took undifferentiated state and called it a feature. None of them ever treated Big State as the enemy: they made it their foundation.

This led to Honest Code, the second pillar of the Honest Framework.

**Every mainstream framework in widespread use today commits these crimes. Because of DATAOS and Honest Code, The Honest Framework commits none of them.**

Every layer (HTTP boundary, type system, persistence, UI) is built on the same principle: pure functions in, data out, state only where it is declared, owned, and visible. No hidden state. No undifferentiated state. No duplicate truth.

---

## The Third Pillar: Architecture-First IDE

The framework is not a linter plus a plugin plus a code generator stapled together. It is the foundation for a new category of development environment: **an IDE whose organizing unit is the architecture, not the file**.

Every mainstream IDE today treats files as the primary concept. The file tree is the navigator. Tabs are files. "Go to definition" jumps between files. Tests live in one file, templates in another, configuration in a third, and the programmer's mental model — "this module handles X, composed of these parts, bound to these routes" — is nowhere in the tooling. The programmer maintains that model in their head and projects it onto a flat file-system whenever they work.

The `.hd` architectural specification changes what is possible. Because the architecture is machine-readable, the IDE can treat it as ground truth. A module becomes a first-class unit of editing: its functions, types, chains, dispatches, routes, templates, tests, and dependency diagram are different views onto the same concept, arranged around the programmer rather than chased by them. When they focus on a module, the environment materializes all of its surfaces together — prose, code, HTML, and diagram — in a linked workspace. Clicking a chain in the diagram scrolls all panes to the relevant fragment across files. Tests and generated stubs disappear from the file tree because they are build artifacts, regenerated on every save. The diagram becomes the navigator and the file tree becomes implementation detail.

This is not a new idea; it is an old one that required the right foundation. Smalltalk had a class browser because the class was the unit. Lisp machines edited images because the runtime was the unit. Honest Framework makes the **architectural module** the unit, and exposes it through an IDE experience that file-centric tooling has no way to match.

**One polymorphic core, pluggable per-language adapters.** The IDE is built around a single architectural engine that is identical across every language target. That engine owns everything that depends only on the `.hd`: parsing, the intermediate representation, honest-check rules, poka-yoke enforcement, diagram rendering, the dependency graph, the workspace view, the module-as-unit logic, Claude-skill orchestration, and the MCP exposure. It is written once and serves every target.

Each language — Python, JavaScript, Ruby, PHP, Elixir, Go — plugs in through a narrow adapter interface: *introspect this source tree and produce an IR of what the code actually declares*; *given an IR fragment and a target location, emit idiomatic stub code for this language*; *resolve this symbol to a file and line*; *report this side-effect from a boundary function*. The adapter is a few hundred lines of language-specific AST and emit logic. It knows nothing about diagrams, about `.hd` parsing, about Claude skills, or about LSP wire format. Those live in the core.

This split is the direct consequence of the Neonto principle: idiomatic runtime code per language, *but* a single shared architectural model and a single shared tooling surface that treats every language target the same way. A Python programmer and a Ruby programmer open their respective repos in the IDE and get the same diagram, the same diagnostics, the same workspace panes, the same scaffolding commands, the same Claude skills — differing only in the code each language adapter emits into its code pane. The `.hd` file is byte-identical across target languages. The honest-check rules fire on the same architectural violations regardless of target. The conformance laws (see `honest-conformance-suite.md`) verify that adapters preserve semantics across targets.

**Delivery path is incremental.** The first shipped artifact is the polymorphic core plus a Python adapter, exposed over Language Server Protocol. A thin VS Code plugin puts a live diagram preview, synchronized module-workspace layout, scaffolding commands, and a Claude-driven intent panel on top of the LSP. A comparable thin client exists for JetBrains. Every other editor — Neovim, Emacs, Zed, Sublime — gets the diagnostics, completions, jump-to-definition, and quick-fixes through its generic LSP client. Subsequent adapters (JavaScript, Ruby, others) are additive: they bolt into the same core, reuse the same IDE surfaces, and their users get the full experience on day one. One engine, many adapters, many surfaces, no editor or language left behind.

**Implementation language for the polymorphic core: Rust.** The core is written once in Rust and shipped as a statically linked, single-file binary per platform (`honest-lsp-macos-arm64`, `honest-lsp-linux-x64`, `honest-lsp-windows-x64.exe`). Binaries live either in the project repo under `.honest/bin/` (vendored, fully reproducible, zero install) or are downloaded by the editor extension on first run at a version pinned in the project config. No Python, Node, or JVM runtime is required on the user's machine regardless of their project's target language. A Ruby team using honest-framework does not need Python installed to get IDE features; a Go team does not need Node.

The Rust choice is driven by three pragmatic factors. First, honest-framework is polyglot at the target-language level, and the tooling must not impose a language tax on any user; a static binary is the only distribution story that satisfies this universally. Second, Rust's structs-plus-pure-functions idiom maps cleanly onto Honest Code's "no classes, dispatch by match, data flows through transformations" philosophy, so the tooling's own source code reads as an exemplar of the principles it enforces. Third, the developer-tooling ecosystem (tower-lsp for the LSP protocol, chumsky or lalrpop for the grammar, serde for JSON-RPC, notify for the filesystem watcher, salsa for incremental re-computation) is already mature in Rust; this is the category of work Rust libraries exist for, and there is no other language where the "write once, ship as zero-dep binary, match the tonal expectations of the framework" constraints all land together.

Per-language adapters may be written in Rust alongside the core, or in the target language itself if linked via a stable FFI contract; implementation authors pick what they can maintain. The LSP core is agnostic to adapter implementation language — it speaks only the adapter contract.

**Performance budget.** Startup latency of the LSP binary is single-digit milliseconds warm, 20–50ms cold; irrelevant to the user because the LSP is long-lived. Per-keystroke diagnostic tick target: under 20ms. Initial workspace scan for a project with 20 modules: under 200ms. Go-to-definition, hover, completion: single-digit ms against cached IR. MCP tool calls from Claude skills: sub-millisecond on the LSP side, dominated by model latency on the Claude side. These numbers are achievable in Rust on modern hardware and guide the shape of the implementation (incremental re-compute via salsa-style memoization, not full re-parse per change).

### Two Audiences, Two Views, One Engine

The IDE serves two distinct audiences, and it treats them as first-class distinct experiences — not as expert-vs-novice modes of the same UI.

**Framework-author view.** Someone building or extending the framework itself — a new rule in honest-check, a refactor in honest-persist, a new module like honest-queue. This audience sees the full architecture: every honest-* module rendered in 4-column detail, every function, every chain, every dispatch, every cross-module dependency. The workspace diagram is the framework's self-structure, and the audit rules apply at framework-internal granularity (HC-R001 role reachability, HC002 chain type matching within a module, HC-F* rules governing cross-module surface). This is the view the honest-design tool currently ships; it is also the view that core contributors use to reason about the framework's own shape.

**Application-developer view.** Someone building an application *on* the framework — Maya adding the locations module to a SaaS, or a shop standing up an order-tracking system. This audience never sees the framework's internals. The workspace shows *their* modules as first-class citizens — `locations`, `orders`, `customers` — connected by *their* dependencies on each other. The framework modules they *use* (persistence, alerts, forms, auth, components) appear as opaque *capability pills* labeled by what they do, not as 4-column diagrams of how they work. Calls from application code into framework code appear inline where invoked, the same way a Python developer sees `json.dumps` as an ordinary function call rather than a node in their dependency graph. The honest-check rules that fire are the application-facing subset — no classes, dispatch not if-elif, forms declared correctly, tenant filtering where required — not the framework-internal rules. Her `.hd` imports types and capabilities ambient-style; the LSP resolves them without requiring her to author them.

**Same engine, same grammar, same files.** The `.hd` grammar is identical in both views. The parser, the LSP, the validator, the diagram renderer — all shared. The difference is a presentation lens applied over identical data, plus a rule-selection policy that knows which honest-check rules apply at each level. A repo's `pyproject.toml` declaring `honest-framework` as a *dependency* triggers application-developer view; a repo that *is* honest-framework triggers framework-author view; explicit override via configuration is available if needed. One engine, two lenses, zero duplication of tooling.

**Historical context for this split.** The closest analog is the game-engine audience split — Unity, Unreal, Godot — where engine developers and game developers work inside completely different experiences delivered by the same product. The insight is that *frameworks are the same kind of product as game engines*: a capability layer that hundreds of thousands of application developers customize, plus a much smaller group of authors who maintain the capability layer itself. Mainstream application frameworks (Django, Rails, Spring) have never made this split. Everyone sees the same internals whether they want to or not, and that is the root cause of the "too much framework, not enough app" complaint that has dogged framework criticism since the mid-2000s. Honest-framework makes the split a first-class architectural commitment.

### The Skill Registry

Claude skills are the intent-heavy layer on top of the LSP: first-class, multi-file operations invoked through natural language, dispatched through MCP to deterministic tooling. A skill is not a scaffolding macro; it is a *codified architectural judgment*. Each skill in the registry encodes a recurring decision pattern that the framework has opinions about — backend choice for persistence, tenant isolation strategy, state-transition validity, form handling convention — and converts a one-sentence intent into the full shape of `.hd`, code, templates, and tests that judgment implies. The skills ride on the LSP (reading authoritative workspace state via MCP, writing files that the LSP re-validates) and every skill's output is backstopped by honest-check, so a skill that classifies wrong produces a deterministic error rather than silent drift.

The following is the authoritative list of skills the framework ships. Each is developed in its own dedicated conversation that walks four layers: the axes the skill classifies on, the defaults per classification, the questions the skill asks when uncertain, and the guardrails honest-check enforces. The list is ordered roughly by dependency — earlier skills are foundational to later ones.

0. **Customize from capabilities** — the foundational meta-skill. Invoked implicitly by every other skill when operating in application-developer view. Composes the application developer's module from framework capabilities (persistence, alerts, forms, auth, components, etc.) without exposing her to the framework's internal structure. Declares capability dependencies in her `.hd` as named surface references (e.g., `uses persistence.table(Location)`), resolves them to framework-module calls at emission time, and enforces that her application code never reaches past the capability surface into framework internals. Every other skill in the registry routes through this one when called from application-developer view.
1. **DATAOS classification** — the manifest skill for state location. Every new piece of stateful data in a module is routed to exactly one of the six DATAOS owners (DOM-resident, session, user_prefs, tenant storage, configuration, derived) without the developer having to name the owner herself. Axes: scope (request/session/user/tenant/global), lifecycle (ephemeral/persistent/configured/derived), writer (user/system/external), coherence (source-of-truth/cache/view). Guardrails via honest-check: no localStorage / sessionStorage / IndexedDB in client JS; no Redux / Zustand / Recoil / Jotai / MobX / Context imports; no two-writers-to-one-state; derived state must declare its source-of-truth recognizer; DOM-resident state must use declared `hb-*`/`ha-*` attribute vocabulary not hand-rolled `data-*`.
2. **Persistence** — default Turso (pyturso) for low-write/high-read data; Postgres via queue for high-write; placeholder for the queue implementation until honest-queue is finalized. Redis is NOT a default anywhere. Session caching and cross-service common data go to Turso. (Measured finding: Turso is lower-latency than Redis for this class of work.)
3. **Multi-tenancy** — tenant identity propagation without polluting signatures; row-level vs. schema-per-tenant vs. database-per-tenant decision tree; honest-check enforcement that no query lacks a tenant filter.
4. **State machines** — when a recognizer set is a state machine in disguise; a `transitions` primitive in the `.hd` grammar; honest-check enforcement of valid transitions; automatic event emission on transition.
5. **Forms (genX pattern)** — validation rules declared as `hf-*` attributes on inputs; submission produces a manifest; rejections are data; invalid-state rendering is a pure function of the rejection. No form class, no validator-as-method, no ModelForm.
6. **Components** — atoms/molecules/organisms boundary; promotion rules; token flow; the convention for `hb-*`/`ha-*` attribute vocabulary per component.
7. **Tables** — column declarations as a vocabulary; sort, filter, selection, row actions, column visibility, export, pagination-aware selection; table state resident in the DOM (DATAOS), not in a client store.
8. **Number formatting (genX pattern)** — `hf-money`, `hf-percent`, `hf-duration`, `hf-bytes`, `hf-date` attributes resolved against locale and precision config at render time.
9. **a11y (genX pattern)** — ARIA expanded from `hb-*` role declarations; keyboard bindings automatic; missing labels and contrast violations surfaced by honest-check.
10. **i18n (genX pattern)** — `hf-t` attributes for translated strings; resource bundle extraction; hardcoded-string diagnostics; per-locale recognizer sets so every translation key is bounded.
11. **Search and filtering** — filter fields as recognizer vocabulary; DOM-resident filter state; SQL generation from the filter manifest; debounce defaults.
12. **Pagination** — offset vs. cursor decision; per-endpoint defaults; HATEOAS-style link generation.
13. **System notifications** — server-originated SSE events raised off the request/response path (DB save failure, upstream unavailability, queue backpressure, scheduled-job failure). They are NOT in-chain faults (which are data) and NOT pre-request validation errors (which are form rejections). They MAY be routed to a user when the condition requires the user's decision about how to proceed (e.g., "upstream X is down, proceed with cached data from 2 hours ago, retry, or cancel?"). In those cases the notification carries the choice set, the user's response returns through honest-alerts, and the originating operation resumes accordingly.
14. **User notifications** — product-level, in-app toast / email digest / push; routes through the yet-to-be-named `honest-notify` module; does NOT overlap with system notifications.
15. **Progress indicators** — operations expected to take more than ~400ms stream progress via honest-alerts SSE; an `hb-progress` binding renders the stream; automatic, not a thing the developer wires by hand.
16. **Network I/O / external API integration** — auth patterns; retry and backoff defaults; rate-limit handling via honest-features; fault sets enumerated from OpenAPI specs; caching decisions; timeout defaults.
17. **Authentication and authorization** — session handling, OAuth flows, role checks; whether a boundary_in requires auth; fault-set inclusion of unauthorized; bearer token location; rotation policy.
18. **Observability** — emission decisions (when does a chain link become an event vs. stay silent), metric granularity, log levels, trace context propagation.
19. **Error handling and alerting** — which faults email, log, retry, or silently drop; severity classification; rate-limit defaults (wiring into honest-errors).
20. **Feature flags** — how new features enter the codebase behind a flag; graduation criteria; flag expiry discipline (wiring into honest-features).
21. **Scheduled jobs / cron** — a `schedule` primitive in `.hd`; where execution happens; observation through honest-observe; failure routing through honest-alerts; overlapping-execution handling.
22. **File uploads** — multipart handling; content-type recognizer; virus-scan boundary; storage-backend decision tree (local / S3 / Turso blob); sync vs. async.
23. **Webhook reception** — signature verification; idempotency via event-id recognizer; replay protection; sender-retry tolerance.
24. **Import / export / bulk ops** — CSV/Excel import as recognizer vocabularies; bulk writes via queue; progress via honest-alerts; multi-tenancy-aware.
25. **Email delivery** — transactional vs. marketing; locale dispatch; unsubscribe handling; bounce handling; `sent` and `delivered` as distinct honest-observe events.
26. **PDF and report generation** — server-side rendering pattern; template approach; cache vs. regenerate decisions.
27. **Search indexing** — Turso FTS vs. external search as a boundary; decision tree mirroring persistence.
28. **Caching** (distinct from persistence) — memoization validity; invalidation; relationship to honest-features; cache-stampede prevention.
29. **Configuration** — `pyproject.toml` vs. env vars vs. honest-features flags vs. honest-persist config rows; which knob lives where; promotion rules.
30. **Migrations** — schema diffs, data migrations, rollout phases, compatibility windows.
31. **Testing** — example-block expansion into exhaustive assertions; fixture generation; property-test seeding; adequacy rules per chain.
32. **Refactors** — split orchestrator, extract pure fn, collapse duplicate chain, normalize dispatch, extract module.
33. **Audit / compliance** — GDPR export; right-to-delete; audit trails; which boundaries get logged, how.
34. **Deployment** — when to introduce a new service vs. stay monolith; what crosses a process boundary.

Four of these skills (4, 7, 8, 9 — forms, number formatting, a11y, i18n) share the **genX declarative-DOM-attribute pattern**: behavior declared on HTML attributes (`hf-*`, `hb-*`, `ha-*`), expanded by a small client runtime, validated statically by honest-check, tested exhaustively from bounded vocabularies. That pattern extends the same DATAOS philosophy the rest of the framework already embraces — the DOM is state, attributes are declarations, runtime is thin, and nothing lives in a client-side store.

Each skill ships as a folder containing a `SKILL.md` (natural-language trigger description for Claude) plus the helper tooling it invokes (honest-framework CLI commands through the LSP/MCP bridge). Skills are distributed through a first-party plugin marketplace and may be shipped per-project via `.claude/skills/` in the repo. The skills are invisible to users with well-authored `SKILL.md` descriptions: developers type intent, Claude matches, the skill runs, the diff appears for review. Misfires are diagnosable by inspecting the `SKILL.md` to see what the skill thought it was doing.

**The long-term trajectory is a standalone IDE.** Once the module-as-unit experience is distinct enough that it outgrows general-purpose editors — when synchronized multi-pane layouts, architectural navigation, and architecture-aware refactoring tools are the defining experience — the product splits off as its own application. Not today, not during MVP, but it is the destination. The thin-edge strategy keeps that destination honest: if the LSP-plus-plugin version is already the best way to work with honest-framework code, the category move is real. If it is not, the standalone IDE would not save it.

**What this commits the framework to.** The `.hd` format must remain the authoritative architectural model — parseable, round-trippable to and from code, stable enough that tooling can depend on it. The honest-check rules, the introspector, the generator, and the diagram renderer must all share one engine, because inconsistency between them would fracture the IDE experience. Claude skills become a first-class layer for intent-heavy multi-file operations, delivered through an official plugin marketplace. And every future architectural primitive introduced into honest-framework must be designed with its IDE presentation in mind: what it looks like on the diagram, how the LSP surfaces it, how a scaffolding command creates it, how a programmer navigates to and from it.

Every layer of the framework, every principle in *Honest Code*, and every feature of every module is ultimately a line item in the IDE's feature set. That is the correct way to think about what is being built.

---

## Origin

The Honest Framework did not begin as a framework. It began as a series of articles and papers describing a new approach to web application design: language-agnostic, but deeply opinionated about which language constructs are honest and which are not. Those articles became the book *Honest Code*, whose ethos is simple: **code should do what it says and say what it does.**

Writing the book forced a reckoning: the author had already built most of the framework. Across several independent repositories, each solving one piece of the puzzle in isolation, the same principles kept reappearing. A type system here. A persistence layer there. A component model. A client-side attribute library. A linter. A test harness. None of them knew about each other, but all of them were expressions of the same idea.

The Honest Framework is the convergence of those repositories into a single coherent whole, unified around FastAPI and HTMX, and grounded in the Honest Code principles the book articulates.

| Repository | What it was |
|---|---|
| declaro-persistum | Declarative persistence layer |
| declaro-observe | Server-sent event observation |
| genX | DOM attribute-driven JS behavior |
| domx | Declarative DOM manipulation |
| stateless | Client-side state elimination |
| Type Magic articles | Pure function table type system concept |

---

## The Patterns and the Implementations

The Honest Framework is a set of patterns, not a single codebase. Each pattern defines a concept: how to classify tokens, how to compose functions, how to bind a type system to HTTP, how to structure components without shared state. Each dynamic language gets its own complete, idiomatic implementation of every pattern. A Python programmer installs `honest-py` and gets everything. A Ruby programmer installs `honest-rails` and gets everything. There is no shared runtime, no cross-language package, and no hub dependency *in production code* — the code that ships to production is pure, idiomatic target-language code with no hidden framework runtime underneath it.

The **tooling** tells the opposite story, and deliberately so. A single polymorphic engine — parser, validator, intermediate representation, diagram renderer, LSP, MCP surface, skill orchestration — is shared across every language target, and each language plugs in through a narrow adapter that handles AST introspection and idiomatic code emission for its language. The tooling is one codebase; the runtimes are N codebases. This split is the engineering consequence of the Neonto principle: identical architectural experience across every target language, identical production code idioms per target. See "The Third Pillar" below for how the polymorphic core / pluggable adapter split is structured.

The spec defines what each implementation must do. Each language does it in its own way.

### The Patterns

| Pattern | What the programmer gets |
|---|---|
| **Honest Code** | The prerequisite. honest framework is strongly opinionated: it requires adoption of the Honest Code principles before the rest of the framework has anything to work with. The two that matter most here: **Dict-Lookup Polymorphism** replaces if/elif/else dispatch chains with dict lookup tables (`HANDLERS = {"email": send_email, "sms": send_sms}`); adding a case means adding a row, not modifying control flow. **Typed Dicts Over Classes** replaces classes with plain dicts (`User = TypedDict("User", {"email": str, "name": str})`); data is just data, no behavior attached. These are not stylistic preferences. They are the structural precondition for everything else in the framework. A codebase that does not follow them cannot use honest-type, cannot be checked by honest-check, and cannot be tested by honest-test. The principles are the foundation. The framework is what the foundation makes possible. And here is what nobody told you: Honest Code is also automatically typed code. Not typed in the TypeScript sense. Typed in the structural sense: every value is a plain dict with declared keys, every dispatch table is a finite set of known values, every function accepts and returns declared shapes. The type information is already in the code. honest-type does not add a type system. It reads the one you already built. |
| **honest-ui** | The presentation layer that started all of this. The server renders a value into an HTML element as text. The `h*-` attribute on that element is the presentation instruction: `<span hf="currency USD 2">1299.99</span>` tells the formatting module to render this text as currency, USD, 2 decimal places. The element renders as `$1,299.99`. The instruction is inline, on the element it describes, with no indirection. Seventy-three lines of JavaScript become one attribute. |
| **honest-type** | Once you have adopted Dict-Lookup Polymorphism and Typed Dicts Over Classes, something magical happens: those lookup tables and typed dicts are structurally identical to a type system. A Set used for dispatch is a type declaration. A collection of them is a type system. You built one by following the principles. honest-type makes it explicit: collect your existing tables into a vocabulary, add a binding table that names each slot, call `classify()`. Tokens in. Named dict out. The vast majority of types in an Honest Code codebase are Sets: finite, fully enumerable, and deterministic by definition. The permutation space is closed at definition time and honest-test generates every combination automatically. Predicates (`s.isdigit()`, UUID format checks) handle the edge cases that cannot be fully enumerated; honest-test applies boundary testing there. The same tables power honest-check (pre-commit linter, zero annotations) and honest-test (exhaustive harness, zero test code). The principles created the type system. honest-type named it. |
| **honest-check** | Type checking for free. honest-check runs as a pre-commit hook, exactly like a compiler: it builds an AST, reads your honest-type declaration tables, and verifies type matching across all possible input combinations without requiring a single type annotation in your code. No mypy. No Pyright. No type declarations cluttering your source. It also checks whether your code is honest according to Honest Code principles, returning errors for serious violations and warnings for lesser ones. Developers hate writing type declarations and hate seeing them in code. honest-check means they never have to. |
| **honest-test** | Correctness testing at zero effort. The same way Swagger reads your API definition and generates documentation, clients, and test interfaces automatically, honest-test reads your vocabulary definitions and generates every test case. You declare what your function accepts. The framework writes the tests, runs them, and reports. Thousands of cases in milliseconds. Programmers can still add BDD for functional and behavioral testing, but correctness is already covered before they write a single test. |
| **honest-persist** | Declare your schema as data. The framework computes migrations automatically by diffing your declared schema against the actual database state. No migration files to write, no linear revision chains to manage, no ORM session to reason about. Works with PostgreSQL, SQLite, and Turso with one API. Python `Literal` types become database enums automatically. Supports fluent, Django-style, Prisma-style, and pseudo-SQL query styles. Pseudo-SQL is for developers who think in SQL: write `select("id", "email", from_table="users", where="status = :s", params={"s": "active"})` and get a parameterized, schema-validated query without giving up SQL's clarity. Includes latency instrumentation, an optimistic write queue for high-latency backends, and bulk transfer between databases. |
| **honest-observe** | Think of it as an accounting ledger for your application. Accountants never change a ledger entry; they add a correcting entry. honest-observe works the same way: every event is an immutable, append-only record. State is derived from events via SQL projections, so you can answer any question about any point in time. Not just "what is the error rate now" but "what was the error rate for this user at 3pm yesterday and what was the exact sequence of events that preceded it." You can replay history, reconstruct any past state, and audit everything. No global loggers, no metric registries, no hidden counters. Exports to OpenTelemetry for teams that need it. Every function is its own print statement. |

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

Each implementation covers all the patterns in idiomatic code for that language. A pattern without an implementation is a specification waiting for a port. An implementation without a pattern is a one-off library. Together they are a framework.

---

## Comparison with Compiler-Enforced and Language-Level Purity

The Honest Framework is not the first system to pursue pure-function guarantees. Three tiers of enforcement exist in practice, and the Honest Framework's position among them is deliberate.

### Tier 1: Compiler-enforced purity (Haskell, Elm)

Haskell's IO monad makes side effects visible at the type level. A function without `IO` in its return type is provably pure by construction; the compiler rejects any attempt to perform I/O, mutate state, or read global variables without the type signature declaring it. Elm applies the same principle to frontend code. Dependent-type systems (Idris, Agda, Coq) go further still, proving termination and totality.

These languages achieve the equivalent of L1.18 = 0% by definition. The compiler enforces it. The tradeoff is adoption: Haskell, Elm, and the dependently-typed languages collectively account for fewer than 3% of developer usage. Research on human logical reasoning (the Wason Selection Task; Wason 1966, Evans 2016) predicts this: fewer than 10% of humans solve basic conditional-logic problems correctly on first attempt, and Tier 1 languages demand sustained formal reasoning with no escape hatches. They are the correct theoretical solution and the impractical one.

### Tier 2: Language-level immutability, convention-enforced purity (Elixir, Clojure, F#, OCaml)

Elixir and Erlang make data structures immutable at the language level. You cannot mutate a list or a map; every transformation produces a new value. But GenServer processes carry mutable state across calls, the BEAM actor model permits side effects (message passing, I/O, ETS table writes) without type-level marking, and nothing in the compiler prevents a GenServer-heavy codebase from exhibiting high mutable-state ratios. Purity in Elixir is a strong cultural norm, not a compiler guarantee.

Clojure provides persistent immutable data structures as defaults, but atoms, refs, and agents are explicit mutation points available to any function. F# and OCaml are functional-first but allow mutable references (`ref` cells in OCaml, `mutable` keyword in F#) without type-level distinction.

All four languages make impurity *inconvenient* without making it *impossible*. A disciplined Elixir codebase can approach L1.18 = 0%; a GenServer-heavy one can exceed 40%. The language nudges; it does not enforce.

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

Because Haskell solves the problem for 3% of the developer population and 0% of the enterprise installed base. The Honest Framework solves it for the languages enterprises already use — Python, TypeScript, Java, C#, Ruby, PHP — at a cognitive cost that does not require sustained System 2 formal reasoning. The programmer writes familiar code in a familiar language with familiar libraries. The framework enforces purity behind the scenes through tooling, not through the type system. The programmer does not need to understand monads, functors, applicatives, or higher-kinded types. They need to write pure functions with dispatch tables — a pattern that most working programmers already recognize, even if they do not use it by default.

The Honest Framework is not "Haskell for Python." It is the observation that Haskell's compiler-level enforcement is one mechanism for achieving a mathematical property (purity), and that exhaustive enumeration of bounded input spaces is another mechanism that achieves the same property — with a different tradeoff: narrower scope (bounded vocabularies only) but incomparably broader adoption surface (every mainstream language).

---

## The Verification Model

Correctness is guaranteed in two stages, and the order is fixed.

**Stage one — honest-check (the structural gate).** Before any code lands, honest-check asks it one question: *can the complete set of tests be generated from what this code declares?* If not, the code is turned away at commit time. This is the gate. It runs at the same point in the workflow where compiling would, but it asks a question a compiler does not — not "do the types line up?" but "can the behaviour of this code be worked out from what it declares?"

**Stage two — honest-test (generate and run the tests).** For code that passes the gate, honest-test builds the tests from the declarations and runs them. *Defining is testing* — the developer writes no test code. Because stage one made sure the behaviour can be worked out, stage two can work it out.

The two stages run one way only: code must pass the structural gate before its behaviour can be checked. So the gate is built before the modules it has to govern — honest-check first, in a minimal form so it can check its own source, on top of the one thing it needs (the shared parser, checked by hand first) — and every module after it, honest-check included, lands only by passing it. **This is Verification First: no code that fails the framework's own gate enters the repository.** The exact build order is in *Bootstrapping a New Language Implementation* below.

### What the gate actually guarantees

What makes code checkable is **limited input**. Code becomes uncheckable when its inputs are too many or too open-ended to list — there are simply too many combinations to ever test. The framework rules this out by the shape of the code: every value a function receives is a manifest sorted into declared kinds; a finite set of allowed values can be listed in full; an open-ended check is tested at its edges; and a catch-everything recognizer — the one thing that would re-open an endless range of inputs — is refused when the vocabulary is built. Limited input means the behaviour can be listed in full, which means it can be tested in full.

This guarantee is **complete, and it defaults to rejecting**, because it is enforced on the shape of the code: nothing unrecognized can slip an unlimited input past it, the same way there is no way to write a class that "no classes" fails to see. A class is always a class; an unlimited set of allowed values cannot be declared in the first place.

### Two kinds of rule

honest-check's rules split by what they can promise:

- **Shape rules** — no classes, no hidden state, table-lookup instead of an if/elif that branches on a value, faults carried as data rather than thrown, finite vocabularies, every function reachable from a declared role — match shapes that hold in any language. They are **complete and default to rejecting**, and they carry the limited-input guarantee above.
- **Watch-list rules** — touching the outside world, and anything that can differ from one run to the next, spotted by the name of the call against a maintained list — answer a *different* question: not "is the input limited?" but "does the same input always give the same output?" They are lists of known-bad names, so they are best-effort: a name not on the list slips through (a new library, a call made indirectly). They are **not what the checkability guarantee rests on** — a missed outside-world call makes a function differ run-to-run for an input that is still limited — and the gap is covered another way: honest-test runs every step twice and compares, rather than the checker having to catch every case.

So honest-check is **complete on the thing that decides checkability** (limited input) and best-effort on the separate question of purity. "Any code that passes honest-check is honest" is exactly true for the first and true-but-backstopped for the second.

### One parser, and when in doubt it rejects

Source is read with tree-sitter — the framework's only parser, chosen because the framework is one standard meant to run across many languages, and a single parser family lets the same rule shapes run on Python, Rust, C, and the rest. tree-sitter keeps going when it meets something it cannot read, marking those spots rather than dropping them; honest-check stops at the first such spot (HC-SYN). The gate never passes code it could not fully read.

---

## Bootstrapping a New Language Implementation

A new language version (after the Python reference) is not built module-first and tested after. It is built **gate-first**, in dependency order, with the checker standing up before the modules it has to certify. This is the required path; it makes the two-stage check above concrete.

### The build order

The modules depend on each other in one direction, with no cycles. Build them in an order that respects those dependencies. The full set, with each module's upstream dependencies:

```
# Leaves — depend on nothing. Built and hand-checked first.
parse                                              the shared parser (wraps tree-sitter)
type                                               the type system
errors                                             the error-policy leaf: normalizers,
                                                   behavior table, rate-limiter; no I/O

# Code-quality tier
check      → parse                                 the structural gate
test       → parse, type                           builds and runs the tests
observe    → type, errors                          the event log and projections;
                                                   composes errors' normalizers
persist    → type, observe                         schema/query/transaction boundaries
                                                   emit to the event log
gherkin    → test, check                           BDD scaffolding over the generated tests
auth       → type, persist                          authentication / authorization
state      → type, check, test, persist            the kinds of state and the single-mutator rule
features   → type, check, test, observe            feature flags as a bounded vocabulary

# Application-production tier
page       → type                                   the host-page structural contract
DOM        → type, state, observe                   DOM-as-state (DATAOS) primitives
components → type, page, observe                     atoms / molecules / organisms
alerts     → errors, observe, persist, state, auth  server-push notifications
```

Three rules fix this order:

- **Leaves first.** `parse`, `type`, and `errors` depend on nothing. `errors` is a true leaf — it normalizes failures into one report, decides behavior as a pure function of the environment, and throttles repeats, all with no I/O — and it is *composed* by `observe` (the normalizers) and `alerts` (the behavior table and rate-limiter), so it must precede both.
- **`observe` before `persist`.** Every persistence boundary (execute, apply, transactions) emits to the event log: persist instruments *through* observe. (observe's own emit stores via persist, but it receives that writer at the boundary rather than importing persist, so the dependency runs one way: persist → observe.)
- **Application tier last.** `page`, `DOM`, `components`, and `alerts` build on the code-quality tier; `components` and `alerts` mount into `page`.

The Python reference has implemented through `parse`, `type`, `check`, `test`, `persist`, and `observe` (the last as its pure foundation); the remaining modules are specified and not yet built.

**`parse` is the real starting point, not `check`.** The gate depends on the parser, so the parser is built and checked by hand first. A language whose grammar tree-sitter does not yet cover must add that grammar to the parser before anything else; the rest of the framework only ever reaches the parser through this one module, never tree-sitter directly.

### Build the un-checkable parts first, then turn the gate on

Two modules cannot be checked by the very thing they implement until that thing exists. They are written, then checked once by hand or a small harness, to get started:

1. **Start `parse`.** Check it by hand against the parser rules: a node's text is exactly the slice of source it covers; the walk visits every node, parents before children; line and column count from 1; it reports an error exactly when the tree has one; the same input gives the same result; only known languages are accepted; text decodes correctly.
2. **Start `check`.** Write the shape rules, then run honest-check on its own source until it is clean. From here on the gate exists.
3. **Start `test`.** Write the generators, then have them check their own rules (a generator that fails to cover a declared finite set is wrong). From here on test generation exists.
4. **Gate everything else.** Every other module — and re-checking the first three — lands only by passing honest-check (shape) and its own conformance (behaviour). No code that fails the framework's own gate enters the repository.

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

### Completeness is measured, not claimed

The generated proof is complete only when it reaches every line and branch of the module. **The bar is 100% line and branch coverage, enforced as a gate — and it is a real test of completeness, not a vanity number:** a line that no rule or example reaches is either dead code (delete it) or a behaviour nothing declares (declare it). Both are faults the coverage gate exposes. A new version wires this gate into its commit step alongside honest-check: nothing lands unless the conformance suites pass *and* coverage is total. The small bits of code that only run when a module is launched as a program are covered by launching it that way, not by leaving them out — the gate has no exceptions.

---

## Architecture Overview

```
       ┌─────────────────────────────────────────────────────────┐
 │       The Patterns (language-agnostic spec)             |
 │                          │                              │
 │ leaves:  honest-parse  honest-type  honest-errors       │
 │ quality: honest-check  honest-test  honest-observe       │
 │          honest-persist  honest-gherkin  honest-auth     │
 │          honest-state  honest-features                   │
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
                  │  stateless  → React │
                  └─────────────────────┘
```

**Data flow (full request cycle):**

Every request in an honest-framework application passes through three instrumentation layers in sequence. Each layer is governed by its own spec. Each layer emits events to honest-observe automatically, with no developer instrumentation code required at any layer. The three layers are: Frontend (honest-DOM), Middleware (honest-py intake + chain), and Database (honest-persist).

---

**Layer 1: Frontend (outbound)**
*Governed by: honest-DOM-architecture.md, honest-page-architecture.md*

The user interacts with the page. DOM state changes. domx detects the change via its MutationObserver and emits `hf.dom.changed` to honest-observe via `sendBeacon()`. The changed manifest slots are recorded: which keys changed, from what, to what.

The interaction triggers an HTMX request. Before the request fires, domx calls `collect(appManifest)` and merges the current DOM state into the request body as `_state`. domx emits `hf.browser.request` to honest-observe: method, URL, trigger, target, manifest keys.

The `h*-` attributes on the triggering element declare the presentation intent. They are not classification tokens at this point; they are rendering instructions that the server will honour in the fragment it returns.

```
User interaction
  → domx: hf.dom.changed emitted  (keys changed, from/to values)
  → domx: collect(appManifest)    (DOM state merged into request body as _state)
  → HTMX: hf.browser.request emitted  (method, url, trigger, target)
  → HTTP request leaves browser
```

---

**Layer 2: Middleware (server boundary)**
*Governed by: honest-framework-spec.md, honest-type-architecture.md, honest-check-architecture.md, honest-test-architecture.md*

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

**Layer 3: Database**
*Governed by: honest-persist-architecture.md*

Boundary links in the chain call honest-persist `execute()` to read or write. `execute()` is the only place SQL runs. It emits `hf.persist.query` to honest-observe from inside the call, after execution, without blocking the result: table, operation, row count, duration, `sql_hash` (always), full SQL (development mode only), `request_id` (join key to the canonical event).

Migrations run via `apply()`. Each DDL operation emits `hf.persist.migration`: table, operation, SQL executed, duration, success. Schema history is in the event log.

Pool lifecycle events (exhausted, retry, error) emit `hf.persist.pool`. Write queue stalls emit `hf.persist.queue_stalled`. Nothing is silent.

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

**Layer 1: Frontend (inbound)**
*Governed by: honest-DOM-architecture.md*

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

One `request_id` joins every event in this sequence. `honest-observe inspect <request_id>` renders all of them interleaved by timestamp, browser and server together, with timing breakdowns: total, server, network, browser. Zero developer instrumentation. Zero print statements.

**A note on performance.** Anyone who suspects this instrumentation layer will slow things down has the architecture backwards. Pure functions doing pure computation with no I/O waiting is what CPUs do best. The honest framework benchmark data at honestcode.software shows what happens when you strip out hidden state, remove synchronization overhead, eliminate the ORM, and use efficient memory layout: the numbers are not worse. They are significantly better. But performance is not the real argument. The real argument is correctness and safety: a system where every boundary is typed, every function is pure, every input is classified before it reaches any logic, and every mutation is detected and reported cannot produce the class of bugs that most production incidents trace back to. Visit honestcode.software for the evidence.

---

## Project 1: `honest-type`

### Purpose

Every language has the concept of a function that wraps another function. A middleware. A decorator. A higher-order function. Whatever your language calls it, the concept is the same: intercept a call, do something with the inputs, pass them on, optionally do something with the output.

honest-type is that wrapper for every function in your application. You write a function. honest-type wraps it. Before your function runs, the wrapper takes the raw strings that were going to arrive as arguments, classifies them into a named typed dict, and passes that in instead. Your function never sees a raw string. It receives named, typed values and does pure computation with them. On the way out, the wrapper validates that the output is consistent with what this function declared it would produce, so the next function in the chain can trust what it receives.

This is not a new idea. It is the same idea as a type-checking compiler, except it runs at the boundary where strings enter your system instead of at compile time. The mechanism that classifies a raw string into a named type is the `recognize()` function. The collection of all the types your application knows about is the vocabulary. `classify()` runs `recognize()` against every type in the vocabulary and returns a dict of matched names to values. That dict is the manifest. Your function receives the manifest.

### Core Concepts

| Term | What It Is |
|---|---|
| **recognizer** | A single function: `recognize(token, declaration) → boolean`. You pass it a token (a string) and a declaration (a Set, a callable, or a `predicate()`). It returns true or false. A Set declaration checks membership. A callable declaration calls it. A `predicate()` declaration evaluates it. One function, three kinds of declaration. |
| **vocabulary** | A dict of type names to declarations: `{"currency_code": {"USD", "EUR", "GBP"}, "integer": predicate(lambda s: s.isdigit())}`. Every type the application knows about, in one place. When `classify()` runs, it calls `recognize(token, declaration)` for each entry in this dict until it finds a match. The matching entry's name is the type. |
| **classify()** | The function that does the work. You pass it a list of raw string tokens and a vocabulary. For each token it calls `recognize()` against every entry in the vocabulary until one matches. It returns a plain dict of type names to matched values. That dict is the manifest. |
| **manifest** | The plain dict that `classify()` returns. Instead of your function receiving the raw string `"currency EUR 2"` and parsing it, it receives `{"format": "currency", "currency": "EUR", "precision": "2"}`. Named values, ready to use. |
| **binding** | An optional dict that renames the keys in the manifest. Without it, `classify()` uses the type name as the key: `{"currency_code": "EUR"}`. With a binding `{"currency_code": "currency"}`, the manifest key becomes `"currency"` instead. Lets you use friendly names in your functions regardless of what the type is called in the vocabulary. |
| **composed type** | A declaration that only fires when a specific other type has already matched in the same token list. Handles cases where the same token means different things in different contexts, without requiring the tokens to be in a specific order. |
| **rejection** | An unrecognized token. Not an exception: a data value in the manifest. The function receives it and decides what to do. |
| **fault** | A processing error (predicate threw, non-string token, etc.). Also a data value, not an exception. Exceptions only at the HTTP boundary. |
| **link** | A function wrapped by honest-type so that it receives a typed manifest instead of raw strings. In Python this is a decorator (`@link`); in other languages it is whatever that language uses to wrap a function. The wrapper handles classification, routes the manifest in, and routes the result out. The function itself stays pure: it sees only named, typed values. |
| **chain** | An ordered list of links. The manifest that comes out of one link goes into the next. Each link does one thing. The chain composes them into a pipeline. |

### API (Python)

```python
from honest_type import vocabulary, binding, chain, link, classify, check

# --- Layer 1: Recognizers ---

# Set-based recognizer (finite vocabulary)
currencies = vocabulary({
    "currency_code": {"USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF"},
    "format_name":   {"currency", "number", "percent", "date", "phone", "duration"},
    "style_name":    {"short", "medium", "long", "full"},
})

# Predicate-based recognizer (open pattern)
from honest_type import predicate

patterns = vocabulary({
    "integer":  predicate(lambda s: s.isdigit()),
    "boolean":  {"true", "false"},
    "iso_date": predicate(lambda s: len(s) == 10 and s[4] == "-" and s[7] == "-"),
})

# Vocabularies compose by merging
format_vocab = currencies | patterns


# --- Layer 2: Flat Binding ---

format_binding = binding({
    "format_name":   "format",
    "currency_code": "currency",
    "style_name":    "style",
    "integer":       "precision",
    "boolean":       "enabled",
})


# --- Classification ---

result = classify(
    tokens=["currency", "EUR", "2"],
    vocab=format_vocab,
    bind=format_binding,
)
# result is a manifest:
# {
#     "format": "currency",
#     "currency": "EUR",
#     "precision": "2",
# }

# See honest-type-architecture.md for composed types,
# which handle context-sensitive binding without a third mechanism.


# --- Chains ---

@link(accepts=format_vocab, binds=format_binding)
def format_value(value: str, manifest: dict) -> str:
    """Pure function. Receives only classified, bound arguments."""
    ...

@link(accepts=output_vocab, binds=output_binding)
def render_output(formatted: str, manifest: dict) -> str:
    ...

pipeline = chain(format_value, render_output)

# --- Static Check (honest-check) ---

errors = check(pipeline)
# Returns [] if chain is valid
# Returns list of type mismatches if not
```

### API (JavaScript)

```javascript
import { vocabulary, binding, classify, chain, link } from 'honest-type'

// Identical semantics, JS idiom
const currencies = vocabulary({
  currency_code: new Set(['USD', 'EUR', 'GBP', 'JPY', 'CAD']),
  format_name:   new Set(['currency', 'number', 'percent', 'date']),
  style_name:    new Set(['short', 'medium', 'long', 'full']),
  integer:       (s) => /^\d+$/.test(s),
  boolean:       new Set(['true', 'false']),
})

const formatBinding = binding({
  format_name:   'format',
  currency_code: 'currency',
  style_name:    'style',
  integer:       'precision',
  boolean:       'enabled',
})

const result = classify(['currency', 'EUR', '2'], currencies, formatBinding)
// { format: 'currency', currency: 'EUR', precision: '2' }
```

### Properties (rules that always hold)

These must hold in both implementations:

1. **Determinism**: Same tokens + same tables = same manifest. Always.
2. **Order independence** (flat binding): Token order does not affect the manifest when using Layer 2 only.
3. **Exhaustive classification**: Every token is either classified or rejected. No silent pass-through.
4. **Rejection is data**: An unrecognized token produces a rejection entry in the manifest, not an exception. The caller decides what to do.
5. **Composition via merge**: `vocab_a | vocab_b` produces a valid vocabulary. Binding tables merge the same way.
6. **Bounded enumeration**: For Set-based recognizers, the complete list of valid values is available for static analysis and exhaustive testing.

### honest-check (The Linter)

Focused, single-purpose.

**Rules:**

| Rule ID | Description | Severity |
|---|---|---|
| `HC001` | Function in chain has no vocabulary declared | Error |
| `HC002` | Chain link output types not subset of next link input types | Error |
| `HC003` | Recognizer overlap: token matches multiple types in same vocabulary | Warning |
| `HC004` | Dead vocabulary: type defined but never bound to a slot | Warning |
| `HC005` | Unused binding: slot defined but no recognizer produces that type | Warning |
| `HC006` | Context binding references type not in vocabulary | Error |
| `HC007` | Chain has no links | Error |
| `HC008` | Link function is not pure (heuristic: accesses global state) | Warning |

**Invocation:**

```bash
# Python
honest-check src/

# JavaScript
honest-check --lang js src/

# Pre-commit hook
# .pre-commit-config.yaml
- repo: honest-type
  hooks:
    - id: honest-check
```

### honest-test (The Testing Harness)

Where honest-check asks "does this code *look* honest?" honest-test asks "does this code *behave* honestly?" It does this by leveraging the defining property of bounded vocabularies: **if you can enumerate every valid input, you can run every valid input.**

This is the Swagger principle applied to type systems. Swagger reads an API definition and generates documentation, test interfaces, and client SDKs. honest-test reads vocabulary definitions and generates exhaustive test cases. The vocabulary *is* the spec.

**Capabilities:**

| Capability | What It Does | How |
|---|---|---|
| **Exhaustive permutation** | Generates and runs every valid input combination | Enumerates Set members, combines across vocabularies. `5 formats * 150 currencies * 4 styles = 3,000 tests`: all run, not sampled. |
| **Purity verification** | Proves a function is pure, not just guesses | Calls `f(x)` twice, compares output. Instruments for global reads, mutations, I/O, network. |
| **Chain contract testing** | Verifies data actually flows through chains | Runs every valid output of link N through link N+1. Confirms nothing crashes, nothing is dropped. |
| **Rejection boundary** | Confirms invalid inputs are always caught | Generates adversarial near-miss tokens, off-by-one strings, type confusions. Verifies all produce rejections. |
| **Idempotency proof** | Catches hidden state | Runs every chain twice with the same manifest. Results must be identical. |
| **Mutation detection** | Catches functions that modify their input | Snapshots manifest before dispatch, compares after. Any difference is a dishonesty violation. |

**How it differs from property-based testing:**

Property-based testing (Hypothesis, QuickCheck) *samples* from infinite input spaces. It finds bugs probabilistically. Run it twice and you might get different results.

honest-test *enumerates* from bounded input spaces. It proves their absence exhaustively, not probabilistically. Run it a thousand times and the result is identical, because every possible input was tested every time.

This is only possible because honest-type vocabularies are limited to a known, finite set of values. No other framework has type spaces you can list in full. This is a categorically different guarantee.

**The compile-time argument, resolved:**

The standard objection to dynamic languages is: "better to catch errors at compile time than at runtime."

honest-test eliminates this objection entirely. The same predicate tables run at three times:

1. **Pre-commit** (honest-check): static verification via set intersection
2. **Test suite** (honest-test): exhaustive runtime verification of every permutation
3. **Production** (honest-type): runtime classification at every boundary

All three use the same code. The same tables. The same semantics. There is no gap between what the static checker knows, what the tests cover, and what the runtime enforces. Zero drift.

The fiction was never "dynamic vs. static." The fiction was that unbounded type spaces (created by classes) required a compiler to check. Bounded type spaces don't need a compiler. They need a `for` loop.

**Invocation:**

```bash
# Run exhaustive tests for all chains in src/
honest-test src/

# Test a specific chain
honest-test src/pipelines/create_user.py

# Show all generated permutations without running them (dry run)
honest-test src/ --dry-run

# Generate test report (like Swagger UI, but for type coverage)
honest-test src/ --report html --output coverage.html

# Verify purity of all link functions
honest-test src/ --purity

# Run rejection boundary tests only
honest-test src/ --rejections
```

**Generated output (example):**

```
honest-test v0.1.0
Scanning src/ for chains...

Found 4 chains, 12 links, 6 vocabularies

format_pipeline (3 links)
  Vocabulary: format_name(5) × currency_code(150) × style_name(4)
  Permutations: 3,000
  Running.............. 3,000/3,000 PASS
  Purity: 3/3 links verified pure
  Idempotency: PASS
  Rejections: 847 adversarial inputs, 847 rejected

create_user_pipeline (5 links)
  Vocabulary: action(3) × role(4) × boolean(2)
  Permutations: 24
  Running... 24/24 PASS
  Purity: 4/5 links verified pure
    ⚠ insert_user: I/O detected (expected: boundary function)
  Chain contracts: all outputs of link N accepted by link N+1
  Rejections: 156 adversarial inputs, 156 rejected

Total: 3,024 permutations tested, 0 failures
       11/12 links verified pure (1 boundary function)
       1,003 adversarial inputs rejected
```

**Comparison with honest-check:**

| | honest-check (linter) | honest-test (harness) |
|---|---|---|
| When | Pre-commit, static | Test suite, runtime |
| How | AST analysis, set intersection | Actually runs the code |
| Proves | "This code *looks* honest" | "This code *behaves* honestly" |
| Catches | Missing vocabularies, chain type mismatches, dead bindings | Impure functions, hidden state, silent failures, mutation |
| Generates | Warnings and errors | Exhaustive test cases from vocabularies |
| Analogy | ESLint for honesty | Swagger for type systems |

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

```python
from honest.fault import fault, catch_at_boundary

# Inside a chain, faults are data
def validate_email(manifest: dict) -> dict | fault:
    if "@" not in manifest.get("email", ""):
        return fault("invalid_email", f"Bad email: {manifest.get('email')}")
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

**honest.react is different.** The React bridge does NOT sit on top of HTMX. React owns the rendering pipeline. honest.react wraps domx's DOM observation into React hooks (`useDomState`, `useDomValue`), letting React components read state from the DOM instead of maintaining a separate state copy. It's the DATAOS principle applied inside React's world.

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
| Tables | **honest.table** | genX tableX | `ht-*` | Sorting, filtering, pagination, responsive layouts. |
| Smart detect | **honest.smart** | genX smartX | `hs-*` | Auto-detection formatting. |
| UI enhance | **honest.ui** | genX uiX | `hu-*` | UI enhancements. |
| React bridge | **honest.react** | stateless | (none) | `useDomState`, `useDomValue`, `useDomArray`, `useDomMap` hooks. |
| Bootloader | **honest.boot** | genX bootloader | (none) | Scans DOM for `h*-` attributes, lazy-loads modules on demand. |
| DOM bridge | **honest.bridge** | genX domx-bridge | (none) | Centralized MutationObserver shared by all modules. |

### honest-ui: The Type System in the Markup

honest-ui is the name for the `h*-` attribute system as a whole. It is not a separate package; it is the point where honest-type vocabularies surface in the browser. Every `h*-` attribute on an HTML element is a type declaration: inline, at the point of use, with no indirection. The element says what it is where it is. There is no separate schema file to find, no annotation to trace back to an interface, no documentation to consult. The markup is the type system.

This is the deepest expression of the honest principle: code that says what it does, where it does it.

### Attribute Classification via honest-type

honest-ui attribute values are untyped strings. honest-type classifies them.

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
| Linter | `honest-check` | CLI: `honest-check src/` |
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
| `ht-` | honest.table | `<th ht-sortable="name">` |
| `hs-` | honest.smart | `<span hs-detect>42.5%</span>` |
| `hu-` | honest.ui | `<div hu-tooltip="Help text">` |

---

## What Needs To Be Built (Priority Order)

### Phase 1: Core (honest-type)

This is the foundation. Nothing else works without it.

1. **Recognizer engine:** Set membership + predicate evaluation. Both Python and JS.
2. **Vocabulary composition:** Merge operator (`|`) with conflict detection.
3. **Flat binding:** Type → slot resolution.
4. **Context-sensitive binding:** (context_type, token_type) → slot resolution.
5. **Manifest construction:** Token sequence → classified, bound manifest.
6. **Rejection handling:** Unrecognized tokens as data, not exceptions.
7. **honest-check linter:** Chain validation via set intersection.
8. **honest-test harness:** Exhaustive permutation testing, purity verification, chain contract testing, rejection boundary testing, idempotency proof. The Swagger of type systems.
9. **Test suite for honest-type itself:** Exhaustive. Every permutation of every bounded vocabulary. This is the proof that bounded vocabularies are exhaustively testable.

### Phase 2: Server (honest-py)

Build on existing declaro work.

1. **honest.intake:** ASGI middleware for request classification. The server-side chokepoint.
2. **honest.chain:** Function composition with typed links and fault propagation.
3. **honest.fault:** Rejection/error flow as data through chains.
4. **honest.routes:** Declarative route tables using honest-type vocabularies.
5. **honest.persist:** Port declaro-persistum under new namespace.
6. **honest.emit:** Port declaro-observe under new namespace.

### Phase 3: Client (honest-js)

Build on existing genX/domx/stateless work.

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

The specific formulation of pure function tables as a type system appears to be novel. No published research or academic paper directly describes this approach.

**Adjacent fields:**

- **Predicate dispatch** (Ernst et al.): generalizes multiple dispatch via predicates, but within typed languages
- **Predicate subtyping** (PVS, Typed Racket): predicates refine existing types, not classify raw strings
- **Qualified Types** (Mark Jones): predicates on types in Haskell, but compile-time and statically-typed
- **Intent detection and slot filling** (NLP): solves the same problem probabilistically, which is the exact inverse of this approach
- **Declarative Signals** (2024 browser proposals): moving toward attribute-driven behavior, but without a type system framing
- **htmx, Unpoly, Turbo:** server-rendered HTML with DOM swaps, but no unified type story across boundaries

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

The following documents extend and distill the framework specification. They are canonical: when they conflict with this document, they are newer and correct.

### Code Quality Axis

- **`honest-code-principles.md`:** Sixteen practices that describe what correct code looks like at the level of daily programming decisions. The distillation of the code quality axis.
- **`honest-persist-architecture.md`:** Language-agnostic architecture specification for honest-persist. Defines exact algorithms, data structures, and conformance requirements. An implementor can build a conformant honest-persist from this document alone.
- **`honest-type-architecture.md`:** Architecture specification for honest-type. Includes the classify() algorithm, composed types, maybe bindings, chain execution model, fault semantics, and conformance suite.
- **`honest-check-architecture.md`:** Complete rule set for the static linter. CLI, LSP, startup integration, and all HC and HC-P rules with algorithms.
- **`honest-test-architecture.md`:** Complete specification for the test harness. Auto-generated tests, honesty tests, BDD runner, state machine testing, and coverage model.
- **`honest-state-architecture.md`:** The six kinds of state, DATAOS client primitives, and pure function state machines.
- **`honest-observe-architecture.md`:** Event sourcing, projections, OTel export, and honest-framework semantic conventions.

### Application Production Axis

- **`honest-components-architecture.md`:** Three-tier component hierarchy (atoms, molecules, organisms). Language-agnostic interface contract. Multi-target implementation structure. The Neonto principle: one component package, one idiomatic implementation per target language, no runtime abstraction layer in production.
- **`honest-page-architecture.md`:** Base page contract: six required surfaces, bootstrap sequence, honest-alerts SSE wiring, CSS custom property token set, dark mode switching, Jinja2 block contract, and honest-py intake integration.
- **`honest-DOM-architecture.md`:** Client-side DATAOS implementation: collect(), apply(), observe(). Reference implementations: domx and stateless.
- **`honest-alerts-architecture.md`:** Actor model message passing. Mailbox as projection. send_and_wait() coroutine primitive.

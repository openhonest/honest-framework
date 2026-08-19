# Honest Code: Coding Principles

## Dict-Lookup Polymorphism
Most imperative conditional structures (if/elif/else chains) that dispatch on type or category can be replaced by a dict mapping keys to functions: `HANDLERS = {"email": send_email, "sms": send_sms}` then `HANDLERS[channel](data)`. The dict is a declarative dispatch table. Adding a new case means adding a row, not modifying control flow.

## Typed Dicts Over Classes
A `class User` with fields, methods, getters, setters, and lifecycle hooks becomes `User = TypedDict("User", {"email": str, "name": str})`. The data is just data — no behavior attached. If you can't `json.dumps()` it, it's too clever by half.

## Pure Functions Over Methods
A method like `user.validate()` that mutates internal state becomes `validate_user(user: dict) -> dict`. Input in, output out. The function has no access to `self` because there is no `self`. No side effects, no surprises.

## I/O at the Boundary
Pure business logic functions in the middle; I/O (database, HTTP, file system) happens once, at the edges (route handlers, CLI entry points). The boundary calls the pure function and then does the I/O with the result. This is why mocks become unnecessary — the pure core has nothing to mock.

## Flat Composition Over Inheritance
Instead of `class B extends A extends Base`, use `pipe(validate, authenticate, rate_limit, create_order)`. Each step is an independent function. The pipeline is visible at the point of assembly. No `super()` calls, no hidden method resolution order.

## DOM as State (DATAOS)
The DOM *is* the state. Instead of Redux/MobX/Zustand synchronizing a shadow copy of server state, the server renders HTML and HTMX swaps it into the page. `hx-get` + `hx-target` replaces `useState` + `useEffect`. One copy of truth, not two.

## HTML Attributes Over Imperative DOM Manipulation
Instead of `addEventListener`, `querySelector`, `innerHTML` in JavaScript, use `hx-post="/endpoint"`, `hx-target="#result"`, `hf-format="currency"`. The attribute declares intent; the library handles mechanism. Seventy-three lines of JS become six attributes.

## Typed Exceptions at the Boundary
Don't catch inside business logic. Let functions raise. The route handler (or supervisor) catches, inspects the exception type (`ValidationError`, `GatewayTimeout`), and returns the appropriate status code. Retry logic belongs in the task queue infrastructure, not inline in the function.

## SQL Over Application Caches
Before adding a cache, profile the query. A single SQL join with proper indexes runs under 3ms. The cache adds invalidation bugs, stale data, and a second source of truth. Fix the query or the schema first. Only cache after measurement proves it necessary.

## Pure Function Assertions Over Mocks
`assert f(input) == expected_output` — that's the whole test. If you need 9 mocks to test a function, the function has 9 hidden dependencies. Extract the pure logic; test it directly. Test the wiring separately with integration tests that hit real services.

## Type Declarations Over Imperative Validation
Instead of writing `if not isinstance(x, str)`, `if len(x) > 255`, `if not re.match(...)` — declare a schema in your language's validation layer, a TypedDict, a SQL column constraint, or an `<input type="email">`. The runtime, type checker, database, or browser enforces the constraint. The programmer declares it; the machinery enforces it.

## Context Managers Over Instance State
Instead of `self._connection = await connect()` stored on a class, use `async with create_connection(config) as conn:`. The connection opens and closes within the scope. No persistent state leaks into the caller. Crash recovery is trivial because there's nothing to clean up.

## Configuration as Parameters
Instead of `self._config` set in `__init__`, pass `config: dict` as an argument to each function that needs it. The dependency is visible in the signature. No hidden state, no initialization order bugs.

## No Implicit Defaults
`def f(x, timeout=30)` silently absorbs the caller's omission. Afterwards the program cannot distinguish a caller who chose thirty seconds from one who forgot, and the non-default region is invisible at every call site, so nothing exercises it. A default is catch-and-swallow applied to inputs, and it manufactures an untested input region by construction. Encode absence as an explicit member of a bounded type, a Maybe or a named `Nothing`, resolved in a visible boundary step and exercised by a test. The `=` is the swallow; the boundary resolve is the surfaced decision.

## Simple Gherkin Steps Signal Honest Architecture
If your Gherkin step definition is 30 lines of mock configuration, the code under test has hidden dependencies. When the function is pure, the step definition is: call the function, check the result. Simple step definitions are a signal of honest architecture.

## Declarative Equivalents Over Framework Lifecycle Hooks
Instead of `componentDidMount`, `useEffect` cleanup, `ngOnInit` — use HTMX attributes that declare when to load (`hx-trigger="load"`), or server-rendered HTML that arrives ready. No client-side initialization sequence.

## Strangler Pattern for Migration
Extract one pure function from one class method per sprint. The method now calls the function. The class still exists; the interface doesn't change. After six months the class is a thin shell that does nothing, and removing it is a trivial cleanup.

## Dispatch Tables Close Open Input
An open input space cannot be tested in full, so the work is to close it, and a table with its keys written out is how you close it. The keys are the type. `HANDLERS = {"email": send_email, "sms": send_sms}` declares that exactly two channels exist, so the partition a test must cover is two, whatever the caller passes. The same move works whether the value selects a handler, a format, a parser or a node kind, and it is why `getattr(obj, name)` is honest when `name` ranges over a declared set and dishonest when it ranges over the request. The line is bounded against unbounded, never static against dynamic.

The half that gets dropped is the miss. Read the table by subscript and let an unknown key raise. `table.get(key, default)` files an input nobody wrote a rule for under an answer somebody wrote for a different input, and afterwards nothing can tell the two apart. That is the input side of silent failure, and it does more damage here than anywhere else: the table was the thing that made the space enumerable, so a default quietly re-opens it while the code still reads closed. Where a miss is genuinely expected, return it as a named case the caller has to handle, never as a value shaped like a hit.

Then record what missed. An unknown key is not the caller's mistake, it is a gap in your table, and a table only grows correctly if the misses are collected rather than absorbed. The bug category this eliminates is an unhandled input read as a handled one.

## Atomic Test-and-Set Over Check-Then-Act
A guard that reads a shared value and then writes it is not a guard. Between the read and the write another caller reads the same answer, and both proceed believing they hold the thing exclusively. Under real threads this is rare enough to be unreproducible from a bug report; under an async runtime it is not rare at all — any await between the two, a log line or a metric or any I/O, makes the race certain rather than occasional, and the code that does it looks completely ordinary. Express the guard as one operation whose return value distinguishes "I took it" from "someone else holds it": an atomic insert, a compare-and-swap, an insert-if-absent. The token written must be unique to the caller, because a shared sentinel is not a fix — every later caller reads it back, matches it, and reports success. The bug category this eliminates is a guard that reports protection while protecting nothing.

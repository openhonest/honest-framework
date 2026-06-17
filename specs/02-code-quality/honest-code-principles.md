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
Instead of writing `if not isinstance(x, str)`, `if len(x) > 255`, `if not re.match(...)` — declare a Pydantic schema, a TypedDict, a SQL column constraint, or an `<input type="email">`. The runtime, type checker, database, or browser enforces the constraint. The programmer declares it; the machinery enforces it.

## Context Managers Over Instance State
Instead of `self._connection = await connect()` stored on a class, use `async with create_connection(config) as conn:`. The connection opens and closes within the scope. No persistent state leaks into the caller. Crash recovery is trivial because there's nothing to clean up.

## Configuration as Parameters
Instead of `self._config` set in `__init__`, pass `config: dict` as an argument to each function that needs it. The dependency is visible in the signature. No hidden state, no initialization order bugs.

## Simple Gherkin Steps Signal Honest Architecture
If your Gherkin step definition is 30 lines of mock configuration, the code under test has hidden dependencies. When the function is pure, the step definition is: call the function, check the result. Simple step definitions are a signal of honest architecture.

## Declarative Equivalents Over Framework Lifecycle Hooks
Instead of `componentDidMount`, `useEffect` cleanup, `ngOnInit` — use HTMX attributes that declare when to load (`hx-trigger="load"`), or server-rendered HTML that arrives ready. No client-side initialization sequence.

## Strangler Pattern for Migration
Extract one pure function from one class method per sprint. The method now calls the function. The class still exists; the interface doesn't change. After six months the class is a thin shell that does nothing, and removing it is a trivial cleanup.

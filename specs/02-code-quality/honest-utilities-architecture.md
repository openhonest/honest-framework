# honest-utilities Architecture

## 1. Purpose

honest-utilities holds a capability that several modules share and that belongs to none of them in particular. A capability moves here once at least two modules use it and no single module is its natural owner. The law runner and the environment-variable reader are the capabilities that live here now. honest-utilities sits in the foundation layer.

## 2. Shape

Every capability here is entered by import and runs from no flow of its own. honest-utilities never calls its sibling modules; the siblings reach into it. Each capability takes the framework's standard shape, so the crossing checker reads it with no exception: a door takes the import, hands its input to one orchestrator, and the orchestrator drives the pure functions that make the decisions and any reader that touches the world. The door and the reader are the only cards that touch the world or run code the module did not write; every decision behind them stays in a pure function, testable without the world. A capability whose boundary runs a caller's injected code is an engine; one whose boundary reads the world is a reader.

## 3. Composition

A caller states what it wants as data and hands that declaration in. honest-utilities owns the capability; the caller owns the declaration. A module declares a property and the law runner checks it; a module names the variables it needs and the reader reads them. Neither side reaches into the other's internals.

Each capability's functions and types are declared in honest-utilities.hd. The appendices below give the domain-specific contract the .hd is built from, one per capability.

## Appendix A — The Law Runner

A **law** pairs an identifier and a plain-language statement with a pure predicate. `law(identifier, statement, check)` returns a Law record of those three fields. The `check` is a pure function from one subject to a list of violation messages: it returns an empty list when the property holds for that subject, and one message per violation otherwise. A check never raises and never returns a bare boolean; the messages are the evidence a failure reports.

A **subject** is a `(name, params)` pair. The name labels the case for the report, and `params` is a record the check reads. One law is checked against many subjects, so the same property is proven across a bounded space of cases. A caller builds those subjects from the generators it already has: honest-test's Set enumeration (honest-test-architecture.md §3.2) and adversarial neighbors (§3.5).

`verify_laws(laws, subjects)` runs every law against every subject and returns a run record: how many law-and-subject pairs passed, the total checked, and a list of violations. Each violation names the law's identifier, its statement, the subject it failed on, and the messages the check returned.

Roles for the .hd: `verify_laws` is the door. It hands to the orchestrator `run_laws`, which drives a reader, `run_check`, and a pure function, `to_violation`. `run_check` runs one injected predicate against one subject's `params` and returns its messages; running the caller's predicate is the engine's boundary — honest-utilities executing code it did not write — so `run_check` is a reader whose world is `process`, not a pure function. `to_violation` records each failed pair as a Violation. `law` is the pure constructor a caller uses before anything enters.

Types: **Law** (`identifier`, `statement`, `check`), **Subject** (`name`, `params`), **LawRun** (`passed`, `total`, `violations`), **Violation** (`identifier`, `statement`, `subject` as the failing subject's name, `messages`).

## Appendix B — The Environment-Variable Reader

A module reads its configuration from the environment at startup: a database URL, a connection-pool size, a feature flag. Read by hand, each variable repeats the same three decisions in every module. Coerce the raw string to the type the module wants. Treat a missing variable as an explicit absence, never as a silent default. Fault on a value that is present but will not coerce.

A caller declares the variables it wants, each as a name, a target type, and whether it is required. `read_env(declarations)` reads the environment once and returns a resolved record: each present, valid variable coerced to its type; each absent optional variable set to `NOTHING`; and a fault when a required variable is missing or any value will not coerce. One fault names every variable at fault together, so a misconfigured deployment reports all its problems at once rather than one restart at a time.

A variable coerces to one of a closed set of target types: `str`, `int`, `bool`, `float`, `UUID`, or `key`. A `str` passes through. An `int` and a `float` parse as a number and fault on anything else. A `bool` reads `"true"`, `"1"`, `"yes"`, and `"on"` as true and `"false"`, `"0"`, `"no"`, and `"off"` as false, case-insensitive, and faults on any other word. A `UUID` parses as a UUID string. A `key` is a secret, such as an API key or token: it passes through as a string, but its value never appears in a fault message or anywhere else the module reports — only its name does.

Roles for the .hd: `read_env` is the door. It hands to the orchestrator `load_env`, which drives a reader, `read_raw_env`, and a pure function, `resolve_env`. `read_raw_env` pulls the raw strings for the declared names from the environment; reading the environment is the capability's boundary, so it is a reader whose world is `env`. `resolve_env` coerces each value, fills an absent optional variable with `NOTHING`, and collects the failures into one fault. It coerces by dispatching on the target type through `by_target_type`, which maps each of the six types to its own pure coercer: `coerce_str`, `coerce_int`, `coerce_bool`, `coerce_float`, `coerce_uuid`, and `coerce_key`.

Types: **EnvRequest** (`name`, `type_name` from the closed set above, `required`), **EnvValues** (each declared name mapped to its coerced value or `NOTHING`), and **Fault**. honest-utilities carries Fault as honest-type's shape across the seam — the four fields `code`, `message`, `category`, and `detail`, a bare union `X | Fault` recognized by shape with no ok/err envelope. A fault comes back on a missing required variable or a value that will not coerce.

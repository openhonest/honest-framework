# honest-auth: Architecture Specification

**Date:** April 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-auth is the **authentication interface layer** of the Honest Framework. It defines a plugin contract — `AuthProvider` — that any authentication implementation satisfies to integrate with honest-check (static verification) and honest-test (auto-generated verification).

The framework does not implement authentication itself. It defines the interface. Implementations are plugins, registered at application startup.

### 1.1 The requirement

> *Actor identity is established at the boundary and passed inward as data. The pure interior never derives the actor and never trusts an actor read from request input.*

This is the only requirement the framework places on authentication, and it is the framework's own *I/O-at-the-boundary* rule applied to identity: reading a token, verifying a signature, or looking up a session is I/O, so it happens at the boundary — the request pipeline / middleware — not in the middle of a chain. The boundary validates the incoming token, resolves it to an **actor** (or to a typed failure), and passes that actor inward as an ordinary value. Every link downstream receives the actor the way it receives any other input; none of them re-validates it, and none of them accepts an actor identifier supplied in the request body, query string, or form fields.

Identity is *good for the request*: it is resolved once, at the start, from the credential the boundary verified. The framework does not re-verify identity at the instant of each write. How a provider resolves identity — a session token, a signed JWT, a cryptographic capability, a federated assertion — is the provider's choice.

### 1.2 Relationship to honest-check and honest-test

| Tool | Role |
|---|---|
| **honest-check** | Enforces that an operation requiring authorization takes its actor from the boundary-resolved value, never from request input (HC-A001, HC-A002). |
| **honest-test** | Auto-generates authentication-honesty tests from the provider's `test_token_generator`, exercising the valid, revoked, expired, malformed, missing, and forged token classes. |

### 1.3 What honest-auth Covers

- The `AuthProvider` plugin interface
- Registration and resolution of a single active provider per application
- The contract every provider must meet
- Example registrations (non-normative)
- Conformance requirements for providers

### 1.4 What honest-auth Does Not Cover

- Session mechanics (tables, rotation, lifetimes) — **provider implementation detail**
- Credential handling, password hashing, MFA flows — **provider implementation detail**
- Cryptographic protocols, token formats, key management — **provider implementation detail**
- Storage tiers for session data (HSM, enclave, in-memory) — **provider implementation detail**
- Multi-factor extensions (biometrics, device attestation, location, TOTP) — **provider implementation detail**
- **Authorization for a specific target** (does this actor own this record? hold this role?) — this is ordinary business logic. A link checks it with an early-return guard or a role vocabulary, using the actor the boundary resolved, the same as any other business rule. honest-auth resolves *who the actor is*; the application decides *what that actor may do*.

These are deliberately excluded. They are neither standardized across providers nor required by the framework's core claim. A provider that does the minimum (a demo with plaintext tokens) and a provider that does everything (a production-grade commercial offering) both satisfy the same `AuthProvider` contract.

---

## 2. The `AuthProvider` Interface

Every authentication plugin provides a value conforming to:

```
AuthProvider = {
    name:                 String,                          # unique stable identifier
    actor_recognizer:     Recognizer,                      # token wire-format recognizer
    resolve_actor:        (Token) -> Result[Actor, AuthFault],   # validate + identify, at the boundary
    test_token_generator: TestTokenGenerator,              # produces token classes for tests
    fault_mapping:        dict[AuthFault, HttpStatus],
}
```

### 2.1 `name`

A unique, stable string identifying the provider. Used in log output, honest-check diagnostics, conformance reports, and error messages. Examples: `"example-auth-pro"`, `"honest-auth-capabilities"`, `"honest-auth-jwt"`.

Implementations do not change `name` across versions without coordinating with downstream tooling that pins the provider by name.

### 2.2 `actor_recognizer`

A recognizer (Set or predicate) matching the wire format of the token the provider accepts. It runs at the boundary to classify the token before anything else happens. The recognizer is strict: malformed tokens, including near-misses (edit-distance-1 and the other adversarial classes in honest-test §3.5), are rejected here and never reach `resolve_actor`.

Examples:

- example-auth-pro: predicate matching base64url-encoded 256-bit values
- honest-auth-capabilities: predicate matching a Macaroon serialization format
- honest-auth-jwt: predicate matching three dot-separated base64url segments

### 2.3 `resolve_actor`

The boundary validator. Given a token that passed `actor_recognizer`, it validates the token and resolves it to an actor, or to a typed failure.

```
resolve_actor(token: Token) -> Result[Actor, AuthFault]
```

- **`ok(actor)`** — the token is valid; `actor` is the resolved identity (a `user_id`, a capability-granted scope, a JWT claims set). This value is what the boundary passes inward.
- **`err(fault)`** — the token is invalid; `fault` is an `AuthFault` category (`unauthenticated`, `expired`, `revoked`, `forged`, …). The boundary maps it to an HTTP status via `fault_mapping` and the request never enters a chain.

`resolve_actor` runs at the boundary, so it **may perform I/O** — session-store lookups, signature verification, an introspection call to an identity provider. That is the point of placing it at the boundary. What it must not do is mutate domain state or emit observable side effects beyond the read it needs to identify the actor; auditing of failed authentications is emitted through honest-observe at the boundary, not woven into resolution.

The resolved `Actor` then travels as data. Because identity is fixed for the request, a provider does not need a transactional or per-write resolution path; the framework's contract is satisfied by resolving once, at the boundary, and never trusting an actor from input thereafter.

### 2.4 `test_token_generator`

A generator that produces tokens in named classes, consumed by honest-test's authentication-honesty test:

| Class | Description | Expected outcome |
|---|---|---|
| `valid` | A well-formed token for a real, active identity | `resolve_actor` returns `ok(actor)` |
| `revoked` | A token that was once valid but has been revoked | `err(revoked)` |
| `expired` | A token whose expiry is in the past | `err(expired)` |
| `malformed` | A token that does not match `actor_recognizer` | rejected by the recognizer, before `resolve_actor` |
| `missing` | NULL / empty / absent | `err(unauthenticated)` |
| `forged` | A token that passes `actor_recognizer` but maps to no real identity | `err(forged)` (or the provider's `fault_mapping` equivalent) |

The generator is a plain callable, like the provider's other fields — the framework has no objects with methods:

```
test_token_generator(class: ClassName, context: TestContext) -> Token
```

`context` supplies any test-relevant state (e.g. which identity is the active one). The generator produces a deterministic, reproducible token for the requested class. (Whether a resolved actor is *authorized* for a particular target is business logic the application tests with its ordinary link verification, not part of the provider's token classes.)

### 2.5 `fault_mapping`

A lookup table that translates authentication-failure categories to HTTP response status codes. The boundary uses it to turn an `err(fault)` from `resolve_actor` into the correct HTTP response.

```
fault_mapping = {
    "unauthenticated": 401,   # no valid identity (missing, expired, revoked, forged)
    "forbidden":       403,   # a resolved actor is not permitted (business-logic authorization)
    "conflict":        409,   # stale precondition surfaced at the boundary
}
```

Providers may extend the mapping with additional categories as long as `unauthenticated` remains. Custom categories map to 4xx or 5xx statuses.

---

## 3. Provider Registration

Exactly one provider is active per application instance. Registration occurs at application startup, before any request is served. The registry is a **value**, not module state: `empty_registry()` yields one with no provider, and `register_auth_provider` returns a new registry — registration carries no shared mutable state, so two runs never collide (the honest-gherkin step-registry pattern).

```
empty_registry() -> Registry
register_auth_provider(registry: Registry, provider: AuthProvider) -> Result

Result = ok(Registry) | err({code: "already_registered"})
         | err({code: "invalid_provider", detail: ValidationError})

registered_provider(registry: Registry) -> AuthProvider | Nothing
```

The application's startup holds the registry and hands it to the boundary, which reads the active provider with `registered_provider`.

### 3.1 Resolution order

1. If an application calls `register_auth_provider()` during startup, that provider is active for the registry it returns.
2. If no provider is registered, honest-check emits HC-A001 (warning) and honest-test does not auto-generate authentication-honesty tests. Any operation that requires an actor fails HC-A002 (error), since there is no boundary validator to resolve one.
3. A framework-level configuration may specify `auth.provider = "module.path"` to register a provider automatically from configuration.

### 3.2 No implicit default

The framework does NOT ship a default `AuthProvider`. An application with no registered provider is a valid state — it simply cannot authenticate. This is intentional: a weak default would produce a false sense of security.

---

## 4. Public Contract

Every registered provider guarantees, for the lifetime of the application:

### 4.1 Boundary resolution

`resolve_actor` runs at the boundary and produces the actor as a plain value passed inward. The interior of every chain treats the actor as data and never re-runs resolution.

### 4.2 Rejection of invalid tokens

For every class in `test_token_generator` except `valid`, resolution fails (or the recognizer rejects, for `malformed`). The specific categorization (`unauthenticated`, `expired`, …) is per the provider's `fault_mapping`.

### 4.3 No domain mutation during resolution

`resolve_actor` reads what it needs to identify the actor and nothing more. It does not mutate domain state, and any audit of a failed authentication is emitted through honest-observe at the boundary, not during resolution.

### 4.4 Deterministic under fixed state

Given a fixed backing state and a fixed token, `resolve_actor` produces the same result every time. This is required for honest-test's determinism monitor (§4.5 of honest-test) and for honest-check's static analysis.

### 4.5 Identity is never trusted from input

The only source of an actor is `resolve_actor` at the boundary. The framework passes that resolved value inward as `actor`, and a link that acts on behalf of an actor uses that `actor`. No link, route, or query may take an actor identifier from request input (body, query string, form fields, headers other than the verified credential). honest-check enforces this (HC-A002): a link declared `authorizes=True` must use the boundary-resolved `actor`; one that does not is sourcing identity from input.

### 4.6 Black-box testability

The provider need not expose its internals. Conformance auditors predict the provider's behaviour using only the `test_token_generator` classes and the `fault_mapping` outputs. A provider whose behaviour cannot be predicted from the public contract fails conformance regardless of how secure its internals are.

### 4.7 The authentication-honesty verifier

honest-auth ships the contract of §4.2–§4.6 as an executable pure function, so a provider's honesty is checked, not asserted. `authentication_honesty(provider, context)` runs the provider's `test_token_generator` across every token class and, for each, sends the token through the boundary flow (`authenticate`) and checks the outcome the class names: a `valid` token resolves to an actor; a `malformed` one is rejected at the recognizer before `resolve_actor`; and `revoked`, `expired`, `missing`, and `forged` each fail as unauthenticated — no valid identity. It returns `ok(provider)` or an `err` listing every class whose outcome was wrong. It is pure over the provider's injected generator and resolver, so it is deterministic and mock-free. This is the executable core of §9.1's Core level, and the function honest-test auto-generates its authentication-honesty test around (§8).

For the Full level, `resolve_actor_deterministic(provider, token)` resolves the same token twice under the same backing state and reports whether the two results agree (§4.4).

---

## 5. Example Registrations

The following are illustrative. The framework does not privilege any specific provider.

### 5.1 example-auth-pro (proprietary)

```
example_auth_pro = AuthProvider(
    name                 = "example-auth-pro",
    actor_recognizer     = predicate(r"^[A-Za-z0-9_-]{43}$"),   # 256-bit base64url
    resolve_actor        = example_auth_pro_resolver,           # session-store lookup at the boundary
    test_token_generator = ExampleAuthProTokenGenerator(...),
    fault_mapping        = {"unauthenticated": 401, "forbidden": 403, "conflict": 409},
)

register_auth_provider(example_auth_pro)
```

Implementation is proprietary and ships as a black-box service or container. The session schema, rotation mechanics, and storage tier are not part of the FOSS spec.

### 5.2 honest-auth-capabilities (illustrative)

```
honest_auth_capabilities = AuthProvider(
    name                 = "honest-auth-capabilities",
    actor_recognizer     = predicate_is_macaroon_serialization,
    resolve_actor        = validate_macaroon,                   # verify caveats, return the granted scope
    test_token_generator = MacaroonTokenGenerator(...),
    fault_mapping        = {"unauthenticated": 401, "forbidden": 403, "conflict": 409},
)
```

A Macaroon-based capability provider resolves the actor from a cryptographic token signed with attenuable caveats — no server-side session-to-user mapping; the token itself carries the authorization scope.

### 5.3 No-auth (testing / development only)

```
no_auth = AuthProvider(
    name                 = "no-auth",
    actor_recognizer     = predicate_any,                       # accepts anything
    resolve_actor        = always_ok_anonymous,                 # resolves to a fixed development actor
    test_token_generator = UniformTokenGenerator(always_valid),
    fault_mapping        = {},
)
```

Every request resolves to the same development actor regardless of token content. Useful for local development and the framework's own test suite. honest-check emits a warning at registration if `no-auth` is registered in a non-development environment.

---

## 6. Relationship to Patent-Protected Implementations

Some `AuthProvider` implementations may embody inventions protected by patents held by the provider's author. The `AuthProvider` interface itself is deliberately not a patent claim — it is a plugin contract that admits many implementations, including ones that do not infringe any particular patent (capability-based providers, JWT providers, federated OIDC providers).

Using the `AuthProvider` interface does not grant a license to practice any particular provider's implementation. Applications that register a patent-protected provider must hold the relevant license under the terms distributed with that provider.

---

## 7. honest-check Consumption (summary)

See `honest-check-architecture.md` for the full rule definitions.

- **HC-A001** (warning) — No `AuthProvider` registered; operations that require an actor cannot be verified. Suggests registering a provider.
- **HC-A002** (error) — An operation that acts on behalf of an actor takes that actor from request input instead of the boundary-resolved value. Identity must be resolved at the boundary, never trusted from input. Code is dishonest.

---

## 8. honest-test Consumption (summary)

See `honest-test-architecture.md` for the full test definition.

- honest-test runs the provider's `test_token_generator` across each token class and asserts `resolve_actor` returns the outcome the class names (a valid actor for `valid`; the mapped fault otherwise), with the recognizer rejecting `malformed` before resolution.
- The authentication-honesty test is auto-generated from the provider's contract. No developer test code is written. Authorization for a target is verified by the application's ordinary link tests, since it is ordinary business logic over the resolved actor.

---

## 9. Conformance

### 9.1 Conformance Levels

| Level | Requirement |
|---|---|
| **Core** | Implements all five `AuthProvider` fields; `test_token_generator` produces all named classes; passes the authentication-honesty conformance suite. |
| **Full** | Core + `resolve_actor` is verifiably deterministic under fixed state and performs no domain mutation, confirmed by the conformance probes. |
| **Complete** | Full + provides a black-box deployment surface (container image or hosted endpoint) that conformance auditors can probe without source access. |

### 9.2 Conformance Suite

The conformance suite lives at `honest/honest-auth-conformance/`. It contains:

- A synthetic application whose boundary resolves an actor and passes it inward
- The token classes generated against a scripted backing state
- Expected HTTP responses per class, per the provider's `fault_mapping`
- A check that the resolved actor reaches the interior as data and that no operation reads an actor from request input

An implementation declares its conformance level in package metadata:

```
[honest-auth-provider]
name = "my-provider"
conformance = "Full"
conformance-suite-version = "1.0"
```

### 9.3 Independent verifiability

Conformance is verifiable by a third party using only the public interface. An implementation that passes its vendor's own test suite but fails the public conformance suite is non-conformant regardless of any internal guarantees the vendor claims. Applications and regulators rely on the public contract, not on vendor-specific assertions.

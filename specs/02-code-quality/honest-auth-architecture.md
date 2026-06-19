# honest-auth: Architecture Specification

**Version:** 0.1 (Draft)
**Date:** April 2026
**Status:** Active
**Author:** Adam Zachary Wasserman

---

## 1. Purpose and Scope

honest-auth is the **authorization interface layer** of the Honest Framework. It defines a plugin contract — `AuthProvider` — that any authentication and authorization implementation must satisfy to integrate with honest-check (static verification) and honest-test (auto-generated verification).

The framework does not implement authorization itself. It defines the interface. Implementations are plugins, registered at application startup.

### 1.1 The abstract requirement

> *Chains that authorize on actor identity must obtain the actor atomically with the mutation they authorize, under serializable isolation.*

This is the only requirement the framework places on authorization. How a provider derives actor identity — from a session token, a cryptographic capability, a signed JWT, a federated identity assertion — is the provider's choice. What the provider cannot do is derive the actor *outside* the atomic scope of the mutation's guard, because cross-scope derivation is vulnerable to session revocation, capability attenuation, or token rotation occurring between derivation and commit.

### 1.2 Relationship to honest-check and honest-test

| Tool | Role |
|---|---|
| **honest-check** | Enforces that `@link`s declared `authorizes=True` reference the registered provider's derivation expression in their guards (HC-A001, HC-A002). |
| **honest-test** | Auto-generates auth honesty tests from the provider's `test_token_generator`, exercising valid, revoked, expired, malformed, and NULL token classes (§4.7). |
| **honest-persist** | Exposes the provider's `derivation_expression` as a first-class clause inside the guard DSL (§7.5 / §7.6 of honest-persist). |

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

These are deliberately excluded. They are neither standardized across providers nor required by the framework's core claim. A provider that does none of them (e.g., a demo with plaintext tokens) and a provider that does all of them (e.g., a production-grade commercial offering) both satisfy the same `AuthProvider` contract.

---

## 2. The `AuthProvider` Interface

Every authorization plugin must provide a value conforming to:

```
AuthProvider = {
    name:                  String,                     # unique stable identifier
    actor_recognizer:      Recognizer,                 # token format recognizer
    derivation_expression: GuardExpressionTemplate,    # how to derive actor inside a guard
    test_token_generator:  TestTokenGenerator,         # produces token classes for tests
    fault_mapping:         dict[GuardFault, HttpStatus]
}
```

### 2.1 `name`

A unique, stable string identifying the provider. Used in log output, honest-check diagnostics, conformance reports, and error messages. Examples: `"example-auth-pro"`, `"honest-auth-capabilities"`, `"honest-auth-jwt"`.

Implementations must not change `name` across versions without coordinating with downstream tooling that pins the provider by name.

### 2.2 `actor_recognizer`

A recognizer (Set or predicate) matching the wire format of the token the provider accepts. The recognizer runs at the HTTP boundary to classify the token before it enters any chain.

Examples:

- example-auth-pro: predicate matching base64url-encoded 256-bit values
- honest-auth-capabilities: predicate matching Macaroon serialization format
- honest-auth-jwt: predicate matching three dot-separated base64url segments

The recognizer must be strict: malformed tokens, including near-misses (edit-distance-1 and the other adversarial classes in honest-test §3.5), must be rejected at the recognizer and never reach a guard.

### 2.3 `derivation_expression`

A `GuardExpressionTemplate` that, when instantiated with a token slot, yields a guard expression that atomically derives the actor identity (or signals failure) inside the mutation's transaction.

The template is consumed by honest-persist's guard DSL (§7.5) and compiled to a backend-specific atomic operation. honest-check inspects the template to verify that any authorizing `@link` composes it into the guard (HC-A002).

**Contract:** the expression, when evaluated inside an SSI transaction, resolves to either:

- A valid actor identity (e.g., a `user_id`, a capability-granted permission scope, a JWT claims set) — the mutation proceeds
- A sentinel failure value (NULL, `unauthorized`, `revoked`, `expired`, `malformed`) — the guard fails with `guard_failed` categorized by the registered `fault_mapping`

The expression may perform arbitrary computation, including lookups in the persist layer, cryptographic verification, or external HTTP calls to an identity provider — **as long as the entire evaluation is atomic with the mutation's commit**. Providers that require I/O outside the transaction (e.g., OIDC introspection) must cache verified results inside the transaction's snapshot or fail the contract.

### 2.4 `test_token_generator`

A generator that produces tokens in seven named classes, consumed by honest-test's auth honesty test (§4.7):

| Class | Description |
|---|---|
| `valid_authorized` | Token for a user who has permission for the target record |
| `valid_unauthorized` | Token for a user who does NOT have permission for the target record |
| `revoked` | Token that was once valid but has been revoked |
| `expired` | Token whose expiry is in the past |
| `malformed` | Token that does not match `actor_recognizer` |
| `missing` | NULL / empty / absent |
| `forged` | Token that passes `actor_recognizer` but does not map to any real identity |

The generator is exposed as:

```
test_token_generator.generate(class: ClassName, context: TestContext) -> Token
```

`context` supplies the target record and any test-relevant state (e.g., which user is the authorized one). The generator produces a deterministic, reproducible token for the requested class.

### 2.5 `fault_mapping`

A lookup table that translates guard-failure categories to HTTP response status codes. This is the surface the boundary uses to map a `guard_failed` result to the correct HTTP response.

```
fault_mapping = {
    "unauthenticated":    401,   # actor derivation failed (revoked, expired, missing, forged)
    "forbidden":          403,   # actor valid but not authorized for target
    "invariant_violated": 422,   # business invariant violated; not a caller error
    "conflict":           409,   # serialization conflict or stale precondition
}
```

Providers may extend the mapping with additional categories as long as the four defaults remain. Custom categories must map to 4xx or 5xx statuses.

---

## 3. Provider Registration

Exactly one provider is active per application instance. Registration occurs at application startup, before any chain is executed.

```
register_auth_provider(provider: AuthProvider) -> Result

Result = ok() | err({code: "already_registered"})
         | err({code: "invalid_provider", detail: ValidationError})
```

### 3.1 Resolution order

1. If an application calls `register_auth_provider()` during startup, that provider is active.
2. If no provider is registered, honest-check emits HC-A001 (warning) and honest-test does not auto-generate auth honesty tests. Any `@link` declared `authorizes=True` fails HC-A002 (error) for lack of a derivation expression to reference.
3. A framework-level configuration may specify `auth.provider = "module.path"` to register a provider automatically from configuration.

### 3.2 No implicit default

The framework does NOT ship a default `AuthProvider`. An application with no registered provider is a valid state — it simply cannot authorize. All chains in such an application must be declared `authorizes=False`. This is an intentional decision: providing a weak default would produce a false sense of security.

---

## 4. Public Contract

Every registered provider must guarantee, for the lifetime of the application:

### 4.1 Atomic derivation

The `derivation_expression` evaluates atomically with the mutation's commit under honest-persist's serializable isolation (§11 of honest-persist). Any state the expression reads (session tables, capability records, revocation lists) participates in the same transaction as the mutation and the same SSI anomaly detection.

### 4.2 Rejection of invalid tokens

For every class in `test_token_generator` except `valid_authorized`, the expression must produce a guard failure. The specific categorization (`unauthenticated`, `forbidden`, etc.) is per the provider's `fault_mapping`.

### 4.3 No side effects outside the transaction

The `derivation_expression` must not emit events, log to stderr, call external services, or produce any observable side effect outside the containing transaction. All state changes must be rolled back with the transaction on failure. Providers that need auditing of failed authorizations must emit audit events via the honest-observe layer after the transaction commits — not during derivation.

### 4.4 Deterministic under fixed state

Given a fixed persist snapshot and a fixed token, the expression must produce the same result every time. This is required for honest-test's determinism monitor (§4.5) and for honest-check's static analysis of the guard.

### 4.5 Black-box testability

The provider need not expose its internal implementation. Challengers and conformance auditors must be able to probe the provider's behavior using only the `test_token_generator` classes and the `fault_mapping` outputs. A provider whose behavior cannot be predicted from the public contract fails conformance regardless of how secure its internals are.

---

## 5. Example Registrations

The following are illustrative. The framework does not privilege any specific provider.

### 5.1 example-auth-pro (proprietary)

```
example_auth_pro = AuthProvider(
    name                  = "example-auth-pro",
    actor_recognizer      = predicate(r"^[A-Za-z0-9_-]{43}$"),   # 256-bit base64url
    derivation_expression = GuardExpressionTemplate.lookup(
                                "session_actor",
                                args = [Slot("token")],
                            ),
    test_token_generator  = ExampleAuthProTokenGenerator(...),
    fault_mapping         = {
        "unauthenticated":    401,
        "forbidden":          403,
        "invariant_violated": 422,
        "conflict":           409,
    },
)

register_auth_provider(example_auth_pro)
```

Implementation is proprietary and ships as a black-box service or container. The session schema, rotation mechanics, and storage tier choices are not part of the FOSS spec.

### 5.2 honest-auth-capabilities (illustrative)

```
honest_auth_capabilities = AuthProvider(
    name                  = "honest-auth-capabilities",
    actor_recognizer      = predicate_is_macaroon_serialization,
    derivation_expression = GuardExpressionTemplate.lookup(
                                "validate_capability",
                                args = [Slot("token"), TargetColumn("record_id")],
                            ),
    test_token_generator  = MacaroonTokenGenerator(...),
    fault_mapping         = {
        "unauthenticated":    401,
        "forbidden":          403,
        "invariant_violated": 422,
        "conflict":           409,
    },
)
```

A Macaroon-based capability provider derives authorization from a cryptographic token signed with attenuable caveats. No server-side session-to-user mapping; the token itself is the authorization.

### 5.3 No-auth (testing / development only)

```
no_auth = AuthProvider(
    name                  = "no-auth",
    actor_recognizer      = predicate_any,                       # accepts anything
    derivation_expression = GuardExpressionTemplate.literal(True),
    test_token_generator  = UniformTokenGenerator(always_valid_authorized),
    fault_mapping         = {},
)
```

Every chain authorizes to the bearer regardless of token content. Useful for local development and for the framework's own test suite. honest-check emits a warning at registration if `no-auth` is registered in a non-development environment.

---

## 6. Relationship to Patent-Protected Implementations

Some `AuthProvider` implementations may embody inventions protected by patents held by the provider's author. The `AuthProvider` interface itself is deliberately not a patent claim — it is a plugin contract that admits many implementations, including ones that do not infringe any particular patent (capability-based providers, JWT providers, federated OIDC providers).

Using the `AuthProvider` interface does not grant a license to practice any particular provider's implementation. Applications that register a patent-protected provider must hold the relevant license under the terms distributed with that provider.

---

## 7. honest-check Consumption (summary)

See `honest-check-architecture.md` for the full rule definitions.

- **HC-A001** (warning) — No `AuthProvider` registered; `@link`s declared `authorizes=True` cannot be verified. Suggests registering a provider.
- **HC-A002** (error) — `@link` declared `authorizes=True` has a guard that does not reference the registered provider's `derivation_expression`. Auto-generation fails; code is dishonest.

---

## 8. honest-test Consumption (summary)

See `honest-test-architecture.md §4.7` for the full test definition.

- For every `@link` declared `authorizes=True`, honest-test runs the provider's `test_token_generator` against each of the seven token classes and asserts outcomes according to `fault_mapping`.
- The auth honesty test is auto-generated from the link's authorization declaration and the provider's contract. No developer test code is written.

---

## 9. Conformance

### 9.1 Conformance Levels

| Level | Requirement |
|---|---|
| **Core** | Implements all five `AuthProvider` fields; `test_token_generator` produces all seven classes; passes the auth-honesty-test conformance suite. |
| **Full** | Core + derivation expression is verifiably atomic under honest-persist's SSI conformance probes (§11 of honest-persist). |
| **Complete** | Full + provides a black-box deployment surface (Docker image or hosted endpoint) that conformance auditors can probe without source access. |

### 9.2 Conformance Suite

The conformance suite lives at `honest/honest-auth-conformance/`. It contains:

- A synthetic application with a single authorizing chain
- The seven token classes generated against a scripted persist state
- Expected HTTP responses per class, per the provider's `fault_mapping`
- SSI probe integration: concurrent mutations under contention, verifying that revoked tokens never commit an authorization

An implementation declares its conformance level in package metadata:

```
[honest-auth-provider]
name = "my-provider"
conformance = "Full"
conformance-suite-version = "1.0"
```

### 9.3 Independent verifiability

Conformance must be verifiable by a third party using only the public interface. An implementation that passes its vendor's own test suite but fails the public conformance suite is non-conformant regardless of any internal guarantees the vendor claims. This is required because applications and regulators rely on the public contract, not on vendor-specific assertions.

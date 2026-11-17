Feature: honest-auth — generated, one scenario per function (15 total for 12 functions)
  honest-auth is a pure library: it owns no door, reader or orchestrator, and every function is
  pure composition over a provider's injected callables, reached by import. A failure returns as a
  bare union arm (value | Fault), recognized by honest-type's is_fault off the reserved is_err tag,
  never raised and never wrapped in an ok/err envelope. authenticate and register_auth_provider each
  carry more than one decision path, so each gets one scenario per path.

  # --- building and holding faults and the registry -------------------------

  Scenario: auth_fault builds one AuthFault record from its parts
    Given category: FaultCategory and code: str and message: str and detail: dict<str, any>
    When auth_fault is called
    Then it returns one Fault record carrying the category, the code, the message and the detail, with is_err set true, the single place honest-auth assembles a fault
    And the Fault is carried by the return as a bare union arm recognized by is_fault, never raised and never wrapped in an envelope

  Scenario: empty_registry returns a fresh Registry with no provider
    Given nothing
    When empty_registry is called
    Then it returns a fresh Registry whose provider field is NOTHING, the seed register_auth_provider extends
    And it reads no world and holds no module state, the registry being a value a run threads

  Scenario: validate_provider checks a provider is well-formed before registration
    Given provider: AuthProvider
    When validate_provider is called
    Then it returns the provider unchanged when all five fields — name, actor_recognizer, resolve_actor, test_token_generator, fault_mapping — are present and fault_mapping retains the unauthenticated category
    And it invokes auth_fault to return a fault with code invalid_provider whose detail names the missing or malformed field when the provider is not well-formed
    And it builds no registry, performs no I/O and reads no world

  Scenario: registered_provider returns the registry's active provider or NOTHING
    Given registry: Registry
    When registered_provider is called
    Then it returns the registry's active provider, or NOTHING when none is registered
    And NOTHING carries no is_err tag and is never recognized by is_fault, keeping the bounded absence disjoint from a Fault
    And it is a field read, reading no world and returning no fault

  # --- register_auth_provider, one scenario per decision path ---------------

  Scenario: register_auth_provider returns a new Registry on success
    Given registry: Registry and provider: AuthProvider
    When register_auth_provider is called
    Then it returns a new Registry carrying the provider when the registry holds none and the provider is well-formed
    And it never mutates its argument, so two runs never collide
    And it reads no world, registration happening at application startup before any request is served

  Scenario: register_auth_provider faults with already_registered when a provider is active
    Given registry: Registry and provider: AuthProvider
    When register_auth_provider is called
    Then it invokes auth_fault to return a fault with code already_registered when the registry already holds a provider, since exactly one provider is active per application
    And the fault is recognized by is_fault, returned as a bare union arm with no envelope

  Scenario: register_auth_provider faults with invalid_provider for a malformed provider
    Given registry: Registry and provider: AuthProvider
    When register_auth_provider is called
    Then it invokes validate_provider and returns the fault with code invalid_provider that validate_provider produces when the provider is malformed
    And the fault is recognized by is_fault, returned as a bare union arm with no envelope

  # --- authenticate, one scenario per decision path -------------------------

  Scenario: authenticate rejects a token that fails actor_recognizer before resolve_actor
    Given provider: AuthProvider and token: Token
    When authenticate is called
    Then it first runs the provider's injected actor_recognizer on the token, and a token that fails it is malformed
    And it invokes auth_fault to return at once, before resolve_actor runs, a fault with category unauthenticated

  Scenario: authenticate hands a recognized token to resolve_actor and returns its result unchanged
    Given provider: AuthProvider and token: Token
    When authenticate is called
    Then a token that passes actor_recognizer is handed to the provider's injected resolve_actor, whose Actor or Fault is returned unchanged
    And honest-auth performs no I/O here: the recognizer and resolve_actor are injected provider callables and the real reads live inside resolve_actor at the application's request boundary

  Scenario: fault_status translates an AuthFault into an HTTP status
    Given provider: AuthProvider and fault: Fault
    When fault_status is called
    Then it returns the HttpStatus found by looking the fault's category up in the provider's fault_mapping — unauthenticated to 401, forbidden to 403, conflict to 409, plus any category the provider added
    And the lookup for the no-valid-identity categories always resolves, since unauthenticated is always mapped

  # --- the three per-class outcome checkers ---------------------------------

  Scenario: _expect_actor checks the valid token class resolved to an Actor
    Given cls: TokenClass and result: Actor | Fault
    When _expect_actor is called
    Then it returns true when result is an Actor and not a fault, the valid class having to resolve to an actor, recognizing a Fault by its is_err tag through is_fault
    And it reads no world and returns no fault, reached through the class_outcome table

  Scenario: _expect_unauthenticated checks the revoked, expired, missing and forged classes failed
    Given cls: TokenClass and result: Actor | Fault
    When _expect_unauthenticated is called
    Then it returns true when result is a Fault, the class having to fail as unauthenticated with no valid identity, recognizing the fault by its is_err tag through is_fault
    And it reads no world and returns no fault, reached through the class_outcome table

  Scenario: _expect_recognizer_reject checks the malformed class was rejected at the recognizer
    Given cls: TokenClass and result: Actor | Fault
    When _expect_recognizer_reject is called
    Then it returns true when result is a Fault produced by the recognizer before resolve_actor ran, distinguished from a resolution fault by its code, confirming the token was rejected at actor_recognizer and not resolved
    And it reads no world and returns no fault, reached through the class_outcome table

  # --- the honesty verifier and the determinism check -----------------------

  Scenario: authentication_honesty folds every token class through its required outcome
    Given provider: AuthProvider and context: TestContext
    When authentication_honesty is called
    Then it folds over every token class in token_classes and, for each, generates a token with the provider's injected test_token_generator against context, sends it through authenticate, and selects the right outcome checker through the class_outcome table
    And it returns the provider unchanged when every class's outcome is right, or an auth_fault whose detail lists every class whose outcome was wrong
    And it is pure over the injected generator and resolver, deterministic and mock-free, invoking authenticate, the class_outcome dispatch and auth_fault

  Scenario: resolve_actor_deterministic reports whether the same token resolves twice alike
    Given provider: AuthProvider and token: Token
    When resolve_actor_deterministic is called
    Then it calls the provider's injected resolve_actor twice on token under the same backing state and compares the two returns — two Actors that match, or two faults of the same category
    And it returns true when they agree and false when they differ, propagating no honest-auth fault and reading no world of its own

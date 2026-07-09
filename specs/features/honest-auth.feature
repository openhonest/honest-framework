Feature: honest-auth — authentication is validated at the boundary and passed inward as data

  Scenario: empty_registry holds no provider
    Given a fresh application
    When empty_registry is created
    Then it has no active provider

  Scenario: validate_provider checks the provider carries the required fields
    Given a candidate provider value
    When validate_provider checks it
    Then it is ok when all five fields are present, else invalid_provider listing the missing ones

  Scenario: register_auth_provider registers the single active provider
    Given a registry and a provider
    When register_auth_provider is called
    Then it returns a new registry holding a valid provider, already_registered if one exists, or invalid_provider if malformed, never mutating its argument

  Scenario: registered_provider reads the active provider
    Given a registry
    When registered_provider is asked
    Then it returns the held provider, or nothing when none is registered

  Scenario: authenticate validates a token at the boundary
    Given a provider and a token
    When authenticate runs
    Then a malformed token is rejected at the recognizer and any other token is resolved by resolve_actor to an actor or a fault

  Scenario: fault_status maps a fault to its HTTP status
    Given a provider and a fault
    When fault_status maps it
    Then the provider fault_mapping wins, else the framework default for the category, else 500

  Scenario: _outcome classifies what the boundary produced for a token
    Given the result of authenticating a token
    When _outcome classifies it
    Then an ok result is an actor, a recognizer rejection is a recognizer_reject, and any other fault is its category

  Scenario: authentication_honesty checks a provider honours the token-class contract
    Given a provider and a test context
    When authentication_honesty runs its token classes through the boundary
    Then a valid token resolves to an actor, a malformed one is rejected at the recognizer, and every other class fails as unauthenticated, else it lists each dishonest class with its expected and actual outcome

  Scenario: resolve_actor_deterministic confirms a token resolves the same way twice
    Given a provider and a token
    When resolve_actor_deterministic resolves it twice under fixed state
    Then it reports whether the two results agree

  Scenario: dev_auth_provider builds a development-only plaintext user/password provider
    Given an optional {username: password} table
    When dev_auth_provider is called
    Then it returns a conforming AuthProvider over that table, defaulting to a single 'dev' user with an empty password

  Scenario: _dev_recognizer accepts the dev token wire format
    Given a candidate token
    When _dev_recognizer inspects it
    Then it is recognised only when it is a string with a non-empty username before a colon

  Scenario: _dev_resolver resolves a plaintext credential against the dev table
    Given a dev user table and a username:password token
    When _dev_resolver resolves it
    Then the actor resolves when the user exists and the stored password is empty or matches, else an unauthenticated fault

  Scenario: _dev_token_generator produces a token for each token class
    Given a dev user table
    When _dev_token_generator is asked for a token class
    Then it yields a valid token for the first user, a colonless malformed token, a missing None credential, and unknown-user tokens for the revoked, expired, and forged classes

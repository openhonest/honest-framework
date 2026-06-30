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

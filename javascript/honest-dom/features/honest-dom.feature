Feature: honest-DOM (domx) — the client-side DATAOS primitives

  One scenario per function point: the named functions of the JavaScript reference implementation.
  The scenario count is the directly-counted function-point measure, the same invariant the Python
  modules hold.

  Scenario: readShortcut resolves a read shortcut to a pure extractor
    Given a read shortcut name
    When readShortcut resolves it
    Then it returns a pure extractor that reads the matching property of an element

  Scenario: writeShortcut resolves a write shortcut to a pure writer
    Given a write shortcut name
    When writeShortcut resolves it
    Then it returns a pure writer that sets the matching property of an element

  Scenario: collect reads DOM state through a manifest and an injected query
    Given a manifest and a query that returns the matching elements
    When collect reads the state
    Then each key maps to null for no match, the scalar for one, or the array for many, using the read shortcut or a custom extractor

  Scenario: apply writes a state object back through a manifest and an injected query
    Given a manifest, a state object, and a query that returns the matching elements
    When apply writes the state
    Then it writes each present key with a write shortcut to every matching element, skipping the rest

  Scenario: send collects, caches, and POSTs the state
    Given a url, a manifest, options, and injected deps
    When send runs
    Then it collects fresh state, caches the request under the cache key, and POSTs the state as JSON

  Scenario: replay re-sends the last cached request unless it is absent or expired
    Given injected deps holding the cached request
    When replay runs
    Then it returns null for an absent or past-ttl request, otherwise it re-POSTs the cached request

  Scenario: clearCache removes the cached request
    Given injected deps
    When clearCache runs
    Then it removes the cached request from storage

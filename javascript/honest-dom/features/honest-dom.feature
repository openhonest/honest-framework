Feature: honest-DOM (domx) — the client-side DATAOS primitives

  One scenario per function point: the named functions of the JavaScript reference implementation.
  The scenario count is the directly-counted function-point measure, the same invariant the Python
  modules hold.

  Scenario: readShortcut resolves a read shortcut to a pure extractor
    Given a read shortcut name
    When readShortcut resolves it
    Then it returns a pure extractor that reads the matching property of an element

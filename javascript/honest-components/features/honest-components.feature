Feature: honest-components — interactive component behaviours

  One scenario per function point: the named functions of the JavaScript reference implementation, each a
  pure enhancement over the DOM and honest-DOM's injected event bus (§2.4). Spec-captured from genX's uix
  (the reference of record). The shared enhancement runtime (applyChanges, enhance, scan) is the
  capability common to every component, kept as its own composed module; each component owns only its
  events and its pure handle. This increment carries the switch and the accordion.

  Scenario: applyChanges writes an element's changed attributes
    Given an element and a change set
    When applyChanges writes it
    Then it sets each changed attribute, skips the prevent-default marker, and does nothing for an unchanged attribute or a null change set

  Scenario: enhance wires a component's behaviour through the injected event bus
    Given an element, an event bus, a component's events, and its handle
    When enhance subscribes it to those events
    Then firing an event applies the handled change and prevents the key default, and the returned unsubscribe tears down every subscription

  Scenario: scan enhances every unenhanced element matching a component's selector
    Given a root, an event bus, a selector, a component's events, and its handle
    When scan reads the elements matching the selector
    Then it enhances and marks each one lacking hc-enhanced, skipping the already-enhanced, and returns their unsubscribes

  Scenario: toggled reads a switch's next checked state from the DOM
    Given a switch element
    When toggled reads its aria-checked state
    Then it returns the negation of what the DOM currently shows, treating an absent value as not-checked

  Scenario: handle computes the attribute changes a switch event produces
    Given a switch element and a DOM event
    When handle reads them
    Then it returns the toggled aria-checked change for a click or an activation key, and nothing for another key

  Scenario: accordionExpanded reads an accordion header's next expanded state from the DOM
    Given an accordion header element
    When accordionExpanded reads its aria-expanded state
    Then it returns the negation of what the DOM currently shows, treating an absent value as collapsed

  Scenario: accordionHandle computes the attribute change an accordion event produces
    Given an accordion header element and a DOM event
    When accordionHandle reads them
    Then it returns the toggled aria-expanded change for a click or an activation key, and nothing for another key

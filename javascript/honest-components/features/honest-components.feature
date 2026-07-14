Feature: honest-components — interactive component behaviours

  One scenario per function point: the named functions of the JavaScript reference implementation, each a
  pure enhancement over the DOM and honest-DOM's injected event bus (§2.4). Spec-captured from genX's uix
  (the reference of record). This increment carries the switch, the proving pattern for the client
  behaviour contract; the other components follow its shape.

  Scenario: toggled reads a switch's next checked state from the DOM
    Given a switch element
    When toggled reads its aria-checked state
    Then it returns the negation of what the DOM currently shows, treating an absent value as not-checked

  Scenario: handle computes the attribute changes a switch event produces
    Given a switch element and a DOM event
    When handle reads them
    Then it returns the toggled aria-checked change for a click or a toggle key, and nothing for another key

  Scenario: applyChanges writes a switch's changed attributes to the element
    Given an element and a change set
    When applyChanges writes it
    Then it sets each changed attribute, skips the prevent-default marker, and does nothing for an unchanged attribute or a null change set

  Scenario: enhance wires a switch's behaviour through the injected event bus
    Given a switch element and an event bus
    When enhance subscribes it to its events
    Then firing a click or a toggle key applies the handled change and prevents the key default, and the returned unsubscribe tears down every subscription

  Scenario: scan enhances every unenhanced switch under a root
    Given a root and an event bus
    When scan reads the elements carrying hc-switch
    Then it enhances and marks each one lacking hc-enhanced, skipping the already-enhanced, and returns their unsubscribes

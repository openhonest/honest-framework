Feature: honest-components — interactive component behaviours

  One scenario per function point: the named functions of the JavaScript reference implementation, each a
  pure enhancement over the DOM and honest-DOM's injected event bus (§2.4). Spec-captured from genX's uix
  (the reference of record). The shared enhancement runtime (applyChanges, enhance, scan) is the
  capability common to every component, kept as its own composed module; each component owns only its
  events and its pure handle. This increment carries the switch and the accordion, plus the CSS namespace
  contract (spec section 6): the pure transforms that scope an organism's styles and check its token API.

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

  Scenario: splitRules splits CSS into its top-level rules, brace-aware
    Given CSS text with comments, strings, and a nested at-rule
    When splitRules walks it
    Then it returns each top-level rule's prelude and body verbatim, counting a brace only outside comments and strings

  Scenario: scopeCss scopes an organism's selectors under its BEM block
    Given an organism's CSS file and its block name
    When scopeCss rewrites it
    Then it prefixes every selector the organism owns with the block, leaving already-namespaced, global, and group at-rule preludes alone

  Scenario: tokenContractViolations checks the style.json to CSS token bijection
    Given an organism's style.json manifest and its CSS file
    When tokenContractViolations compares them
    Then it reports a non-namespaced token, a declared-but-unused token, and a used-but-undeclared token, exempting shared tokens

  Scenario: mergeTokenContracts merges every component's tokens and fails loudly on a duplicate
    Given the style.json manifests of the installed components
    When mergeTokenContracts collects their tokens
    Then it returns one key-to-description contract, throwing and naming both owners when two components declare the same token

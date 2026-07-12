Feature: honest-format — declarative value formatting

  One scenario per function point: the named functions of the JavaScript reference implementation,
  spec-captured from genX's fmtx/smartx (the reference of record). This increment carries the shared
  value coercion and the hf-type input conversion; the formatters, auto-detection, declared vocabulary
  manifest, and DOM binding land in the spokes that follow.

  Scenario: toNumber reads a value to a number or null
    Given a value
    When toNumber reads it
    Then it returns the parsed number, or null when the value does not parse

  Scenario: convert applies an hf-type input conversion before formatting
    Given a value and an hf-type name
    When convert reads it
    Then it returns the value scaled, parsed, or coerced by the named conversion, or the value unchanged for an absent, auto, or unknown type

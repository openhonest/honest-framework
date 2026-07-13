Feature: honest-format — declarative value formatting

  One scenario per function point: the named functions of the JavaScript reference implementation,
  spec-captured from genX's fmtx/smartx (the reference of record). This increment carries the shared
  value coercion and the hf-type input conversion; the formatters, auto-detection, declared vocabulary
  manifest, and DOM binding land in the spokes that follow.

  Scenario: toNumber reads a value to a number or null
    Given a value
    When toNumber reads it
    Then it returns the parsed number, or null when the value does not parse

  Scenario: toDate reads a value to a Date or null
    Given a value
    When toDate reads it
    Then it returns the constructed Date, or null when the value does not parse

  Scenario: convert applies an hf-type input conversion before formatting
    Given a value and an hf-type name
    When convert reads it
    Then it returns the value scaled, parsed, or coerced by the named conversion, or the value unchanged for an absent, auto, or unknown type

  Scenario: format renders a value to a display string under a named format
    Given a value, a format name, and options
    When format renders it
    Then it returns the named numeric or text formatting, or the value's own string form for an unknown format or a numeric format applied to an unparseable value

  Scenario: bestDenominator finds the nearest power-of-two denominator for a decimal
    Given a decimal
    When bestDenominator searches
    Then it returns the smallest power-of-two denominator whose fraction approximates it within a hundredth, up to the guaranteed 64

  Scenario: formatCustomDate renders a date through a token pattern
    Given a date and a pattern of date tokens
    When formatCustomDate substitutes each token
    Then it returns the pattern with YYYY, MM, DD and the rest replaced by the date's components, longer tokens before their prefixes

  Scenario: detect auto-detects the type of a value by a confidence-scored pattern table
    Given a value
    When detect scores it against the patterns
    Then it returns the highest-confidence match, or text at full confidence when the value is empty or nothing matches

  Scenario: readSource reads an element's value to format
    Given an element
    When readSource reads it
    Then it returns the recorded hf-raw source, else hf-value, else the trimmed text, else the input value, else empty

  Scenario: readOptions reads an element's hf-* option attributes
    Given an element
    When readOptions reads its hf-* attributes
    Then it returns the format options, each coerced to a number, a boolean, or a string per attribute

  Scenario: writeDisplay writes the display to an element only when it changes
    Given an element and a display string
    When writeDisplay writes it
    Then it sets the input value or the text content, and does nothing when the display is unchanged

  Scenario: formatElement formats an element and records its source
    Given an element and the current instant
    When formatElement renders it
    Then it writes the formatted display, delegating a smart format to detection, and records the source in hf-raw

  Scenario: unformatElement restores an element to its recorded source
    Given an element
    When unformatElement is asked
    Then it writes the hf-raw source back, or returns nothing when the element was never formatted

  Scenario: scan formats every unprocessed element under a root
    Given a root and the current instant
    When scan reads the elements carrying hf-format
    Then it formats each one that lacks hf-raw, leaving the already-processed elements untouched

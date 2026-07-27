Feature: honest-boot — the client bootloader's pure scan/read core

  Scenario: buildSelector covers every declared attribute and class prefix
    Given the declared vocabulary
    When buildSelector builds the query selector
    Then it matches every declared honest attribute and class prefix, and nothing undeclared

  Scenario: resolvePrefix names the module prefix an element declares
    Given an element and the declared vocabulary
    When resolvePrefix reads its attributes and classes
    Then it returns the declared prefix for a honest attribute or class, and nothing for an undeclared one

  Scenario: neededModules lists the modules a set of elements needs
    Given a set of elements and the declared vocabulary
    When neededModules resolves each element's prefix
    Then it returns the owning modules, sorted and deduplicated

  Scenario: scan finds the declared elements and the modules they need
    Given an injected query and the declared vocabulary
    When scan queries the built selector
    Then it returns the matched elements and the modules they need

  Scenario: readConfig resolves a declared attribute into its module config
    Given an element and the declared vocabulary
    When readConfig reads the declared attribute
    Then it returns the owning module, the attribute, and the declared value, or nothing when there is no honest attribute

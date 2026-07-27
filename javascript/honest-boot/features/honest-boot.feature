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

  Scenario: loadModules imports the needed modules that are not already loaded
    Given the needed module names, an injected importer, and the already-loaded names
    When loadModules imports the fresh ones
    Then it imports each not-yet-loaded module once and returns the updated loaded set and the fresh modules

  Scenario: initModule brings a loaded module to life against the root
    Given a loaded module and the root element
    When initModule initialises it
    Then it prefers the DATAOS autoInit over a plain init, and returns nothing when the module exposes neither

  Scenario: activate runs one pass over a root, loading, initialising, and emitting
    Given a root and the injected query, importer, and emit
    When activate scans, loads, inits, and emits
    Then it loads and inits only the fresh modules and emits one classify event per resolved element, returning the updated loaded set

  Scenario: boot activates on start and re-activates on each observer event
    Given a root and the injected observer subscription
    When boot starts and the shared observer later reports a change
    Then it activates once on the root and re-activates on each changed subtree

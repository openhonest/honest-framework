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

  Scenario: parseVerbose collects the prefix attributes into a config
    Given an element and a prefix
    When parseVerbose reads the prefix attributes
    Then it returns each prefix- attribute as a config key, skipping the -opts and -raw attributes and non-prefix attributes

  Scenario: parseJson reads the prefix-opts attribute as a config object
    Given an element and a prefix
    When parseJson reads the prefix-opts attribute
    Then it returns the parsed JSON object, or an empty object when there is no such attribute

  Scenario: zipSlots pairs positional tokens with the ordered slots
    Given a list of tokens and the ordered slots
    When zipSlots pairs them
    Then it maps each token to the slot in the same position, dropping any token past the last slot

  Scenario: parseColon maps the colon-separated type value onto the slots
    Given an element, a prefix, and the vocabulary's slot order
    When parseColon splits the type attribute's value on the colon
    Then it zips the tokens onto the slots, or returns nothing when there are no slots, no attribute, or no colon

  Scenario: parseClass maps the hyphen-separated class token onto the slots
    Given an element, a prefix, and the vocabulary's slot order
    When parseClass splits the mapped class token after its prefix on the hyphen
    Then it zips the tokens onto the slots, or returns nothing when there are no slots, no mapping class prefix, or no matching class

  Scenario: readConfig merges the notations into one module config
    Given an element and the declared vocabulary
    When readConfig parses the element's notations
    Then it returns the owning module and the merged config, with JSON overriding verbose, or nothing when there is no honest attribute or nothing to parse

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

Feature: honest-check — the static honesty gate
  One scenario per function. honest-check reads source, flags the dishonest patterns the
  framework forbids, suppresses what a directive silences, and reports the result. Each
  scenario names the single behaviour the gate stands on; the count of scenarios is the
  module's directly-counted function-point size. Behaviour that can only be stated in
  host-language terms (tree-sitter node mechanics, Python-specific watch lists) lives in
  the python supplement and is counted there.

  # diagnostics.py

  Scenario: diagnostic assembles one reported violation
    Given a rule id, a severity, a location, and a message
    When diagnostic assembles them
    Then it yields a single reported violation carrying every field
    And it is the one place the shape of a violation is constructed

  # config.py — honest-check.toml configuration

  Scenario: normalize_config extracts the supported settings with defaults
    Given a parsed configuration
    When normalize_config reads it
    Then it returns the paths, exclusions, severity, and disabled rules
    And any setting that is absent falls back to its default

  Scenario: empty_config supplies the settings used when no configuration is found
    Given no configuration file
    When empty_config is asked for settings
    Then it returns the normalized defaults

  Scenario: is_excluded decides whether a path is excluded
    Given a path and a list of exclusion patterns
    When is_excluded checks it
    Then it reports true when the path matches any pattern
    But false when it matches none

  Scenario: resolve_severity settles the reporting threshold
    Given a severity from the command line and one from the configuration
    When resolve_severity settles them
    Then the command-line severity wins when given
    And otherwise the configured one, and otherwise the default

  Scenario: resolve_paths settles which paths to check
    Given paths from the command line and paths from the configuration
    When resolve_paths settles them
    Then the command-line paths win when given
    And otherwise the configured ones, and otherwise the current directory

  # formats.py — output formats

  Scenario: counts tallies violations by severity
    Given a list of violations
    When counts tallies them
    Then it returns how many are errors, warnings, and infos

  Scenario: filter_by_severity keeps violations at or above a threshold
    Given a list of violations and a minimum severity
    When filter_by_severity applies the threshold
    Then it keeps only the violations at or above that severity

  Scenario: filter_by_rule keeps and drops violations by rule
    Given a list of violations, a set to keep, and a set to suppress
    When filter_by_rule applies them
    Then it keeps only the rules requested and drops the suppressed ones
    But an empty keep-set keeps every rule

  Scenario: has_errors reports whether anything blocks
    Given a list of violations
    When has_errors inspects them
    Then it reports true when any violation is an error
    And this is what drives a failing exit code

  Scenario: render_human renders violations for a person to read
    Given a list of violations
    When render_human renders them
    Then each violation shows its location, severity, rule, and message
    And a closing line summarizes the totals by severity

  Scenario: render_json renders violations as a machine-readable document
    Given a list of violations
    When render_json renders them
    Then it produces a document with a summary and one entry per violation

  Scenario: render_github renders violations as continuous-integration annotations
    Given a list of violations
    When render_github renders them
    Then each violation becomes one workflow annotation at its level and location

  Scenario: render_junit renders violations as a test report
    Given a list of violations
    When render_junit renders them
    Then errors and warnings appear as failing test cases in a test report

  Scenario: render selects a renderer by name
    Given a list of violations and a format name
    When render is asked for that format
    Then it dispatches to the matching renderer and returns its output

  Scenario: supported_formats lists the available formats
    Given the set of renderers
    When supported_formats is asked
    Then it returns the available format names, sorted

  # suppression.py — directive suppression

  Scenario: is_suppressed decides whether a rule is silenced at a line
    Given a rule, a line, and the collected suppression directives
    When is_suppressed checks them
    Then it reports true when an inline ignore covers that line
    Or when a disable block spans that line

  # startup.py — framework startup integration

  Scenario: startup_check runs the fast rules during boot and acts on findings
    Given paths to check and a chosen reaction to dishonest code
    When startup_check runs the startup-eligible rules over them
    Then clean code passes silently
    But findings are warned, raised, or halt the boot per the chosen reaction

  # rules.py — the rules and the entry point

  Scenario: check_hc_syn flags source that does not parse
    Given source that does not parse
    When check_hc_syn inspects it
    Then it flags the first broken place as HC-SYN
    And this short-circuits every other rule

  Scenario: check_hc_p003 flags a class declaration
    Given a class declaration
    When check_hc_p003 inspects it
    Then it flags a class with no approved base as HC-P003
    And a class that inherits from a non-approved base as HC-P003
    But it permits the approved data and contract bases

  Scenario: check_hc_p001 flags an if-chain that dispatches on one value
    Given an if-chain whose branches each compare the same value for equality
    When check_hc_p001 inspects it
    Then once the branches reach the dispatch threshold it flags the chain as HC-P001
    And it asks for a lookup table instead

  Scenario: check_hc_p011 flags a framework lifecycle hook
    Given a call to a framework lifecycle hook
    When check_hc_p011 inspects it
    Then it flags the hook as HC-P011
    And it asks for server-rendered markup and HTMX attributes instead

  Scenario: check_hc_p007 flags underscore-prefixed instance state set in a constructor
    Given a constructor that assigns underscore-prefixed state on its instance
    When check_hc_p007 inspects it
    Then it flags that hidden instance state as HC-P007

  Scenario: check_hc_p016 flags a closure that captures and mutates an enclosing name
    Given an inner function that captures an enclosing name and rebinds it
    When check_hc_p016 inspects it
    Then it flags the mutable closure as HC-P016

  Scenario: check_hc_p004 flags hidden side effects in a non-boundary function
    Given a non-boundary function that performs input or output, draws on non-determinism, or reads mutable module-level state
    When check_hc_p004 inspects it
    Then it flags the hidden side effect as HC-P004
    And it asks for the work to move to a declared boundary

  Scenario: check_hc_p005 flags a runtime type check in business logic
    Given a runtime type check outside a boundary function
    When check_hc_p005 inspects it
    Then it flags it as HC-P005 and suggests a vocabulary declaration instead

  Scenario: check_hc_p006 flags a cache without profiling evidence
    Given a cached function carrying no profiling evidence
    When check_hc_p006 inspects it
    Then it flags the unjustified cache as HC-P006

  Scenario: check_hc007 flags a chain with no links
    Given a chain declared with no links
    When check_hc007 inspects it
    Then it flags the empty chain as HC007 because it cannot be tested

  Scenario: check_hc003 flags two types that match the same token
    Given a vocabulary whose types could both match one token
    When check_hc003 inspects it
    Then it flags two bounded types that share a value as HC003
    But two open-ended types that may overlap are routed to honest-test as information

  Scenario: check_state_machine_vocab flags transitions outside the declared vocabulary
    Given a state machine whose transitions or initial state use undeclared states or events
    When check_state_machine_vocab inspects it
    Then it flags an undeclared transition state, event, or initial state against its vocabulary

  Scenario: check_state_machine_reachability flags unreachable and dead states
    Given a state machine with an initial state and transitions
    When check_state_machine_reachability inspects it
    Then it flags a state that cannot be reached
    And a non-terminal state with no way out

  Scenario: check_hc_r001 flags an orphan function with no role and no caller
    Given a module that declares at least one function role
    When check_hc_r001 inspects it
    Then it flags any function that has no role and is not reachable from a roled one as HC-R001

  Scenario: check_hc_or001 flags an orchestrator that calls another orchestrator
    Given an orchestrator that calls another orchestrator
    When check_hc_or001 inspects it
    Then it flags the call as HC-OR001 because orchestrators do not compose

  Scenario: check_hc_p002 flags an exception caught in business logic
    Given a non-boundary function that catches an exception
    When check_hc_p002 inspects it
    Then it flags the caught fault as HC-P002
    But cleanup without catching is allowed

  Scenario: check_hc_a001 flags authorizing links with no registered provider
    Given links that declare they authorize but no authorization provider is registered
    When check_hc_a001 inspects them
    Then it flags the unverifiable authorization as HC-A001

  Scenario: check_hc_a002 flags an authorizing link that ignores the provider's derivation
    Given a registered authorization provider with a derivation expression and an authorizing link
    When check_hc_a002 inspects the link
    Then it flags the link as HC-A002 when its guard never references that derivation

  Scenario: check_hc010 flags a link that emits a type it never produces
    Given a link that declares it emits a type its body never produces
    When check_hc010 inspects it
    Then it flags the phantom emission as HC010

  Scenario: check_hc004 flags a vocabulary type that is never bound or composed
    Given a vocabulary type that is neither bound nor used by a composed type
    When check_hc004 inspects it
    Then it flags the unused type as HC004

  Scenario: check_hc005 flags a binding entry for a type outside its vocabulary
    Given a binding entry naming a type absent from the paired vocabulary
    When check_hc005 inspects it
    Then it flags the stray binding as HC005

  Scenario: check_hc_p013 flags a database routing key bound to a predicate recognizer
    Given a binding where db_id, tenant_id, or credential is backed by a predicate recognizer rather than a bounded Set
    When check_hc_p013 inspects it
    Then it flags the routing key as HC-P013 because an unbounded predicate lets an arbitrary database identifier reach the pool

  Scenario: check_hc_p014 flags one recognizer shared across distinct slots
    Given a vocabulary where one recognizer is shared by types bound to different slots
    When check_hc_p014 inspects it
    Then it flags the shared recognizer as HC-P014 because a field swap would go uncaught

  Scenario: check_hc_or003 flags orchestrators that share a run of operations
    Given two orchestrators that share a run of consecutive operations
    When check_hc_or003 inspects them
    Then it flags the shared run as HC-OR003 and suggests extracting it

  Scenario: check_hc008 flags an impure link that is not a boundary
    Given a non-boundary link whose body performs input, output, or non-deterministic work
    When check_hc008 inspects it
    Then it flags the impure link as HC008 and suggests marking it a boundary

  Scenario: check_hc_p017 flags HTTP output produced outside a declared link
    Given a function that produces HTTP output without being a link that declares what it emits
    When check_hc_p017 inspects it
    Then it flags the undeclared output as HC-P017

  Scenario: check_hc001 flags a chain step with no declared vocabulary
    Given a chain that names a defined function carrying no link vocabulary
    When check_hc001 inspects it
    Then it flags the undeclared step as HC001

  Scenario: check_hc002 flags a chain step that accepts what its predecessor never emits
    Given a chain where one step accepts a type the previous step does not emit
    When check_hc002 inspects it
    Then it flags the broken contract as HC002

  Scenario: check_hc006 flags a composed type that names an unknown base type
    Given a composed type that requires or captures a base type absent from its vocabulary
    When check_hc006 inspects it
    Then it flags the unknown base type as HC006

  Scenario: check_hc009 flags a recognizer that may throw on non-matching input
    Given an open-ended recognizer whose body can throw on input it does not match
    When check_hc009 inspects it
    Then it flags the throwing recognizer as HC009

  Scenario: check_hc011 routes catch-all recognizer detection to honest-test
    Given an open-ended recognizer that bounded analysis cannot judge for catch-all behaviour
    When check_hc011 inspects it
    Then it records HC011 as information routing the check to honest-test
    But a bounded recognizer can never be a catch-all and is left clean

  Scenario: check_source parses once, runs every rule, then applies suppressions
    Given source text and its path
    When check_source checks it
    Then unparseable source returns only the syntax fault
    And otherwise it runs every registered rule and collects their violations
    And a directive-silenced violation is downgraded to information rather than dropped

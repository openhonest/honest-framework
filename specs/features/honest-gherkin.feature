Feature: honest-gherkin — generated, one scenario per function (26 total)

  Scenario: parse_feature parses one feature file's text into a ParsedFeature
    Given a source: str and a source_path: str
    When parse_feature is called
    Then it reads the lines one at a time, sorts each into a line kind with _classify, and folds the matching line_handlers state handler over an immutable state, flushing the current scenario at end of input, and on well-formed input returns a ParsedFeature whose ok arm is the Feature carrying its scenarios and steps, and on any structural violation such as a step outside any scenario or a scenario with no name returns a ParsedFeature whose err arm is a StepFault with code bad_feature_syntax and the first error's line number and message in detail, returned as data and never raised

  Scenario: compile_pattern compiles one step pattern into a Result
    Given a pattern: str
    When compile_pattern is called
    Then it translates the {name} and {name:type} placeholders into a both-ends-anchored full-text regex with named captures and records the per-placeholder coercion for each one, and on success returns a Result whose ok arm is a CompiledPattern, and on a placeholder whose type is not one of the PLACEHOLDER_TYPES keys str, int or float returns a Result whose err arm is a StepFault with code bad_feature_syntax, returned and never raised

  Scenario: empty_registry returns the empty starting registry
    Given no parameters
    When empty_registry is called
    Then it returns a Registry whose patterns list is empty, the seed value register_step appends to and a step module's register builds up from, so a run threads a value rather than reading global state

  Scenario: register_step returns a new registry with one pattern appended
    Given a registry: Registry and a kind: str and a pattern: str and a handler: Callable
    When register_step is called
    Then it builds a StepPattern from kind, pattern and handler, appends it to a copy of registry.patterns, and returns a new Registry, never mutating the registry it was given

  Scenario: match_step matches one step against the registry and returns a Result
    Given a step: Step and a registry: Registry
    When match_step is called
    Then it compiles each registered pattern and attempts a full-text match of the step text against each, and on zero matches returns a Result whose err arm is a StepFault with code step_unmatched, on more than one match returns a Result whose err arm is a StepFault with code ambiguous_step listing the competing patterns in detail, and on exactly one match returns a Result whose ok arm is a StepMatch with its captures bound and coerced per the matched pattern's recorded coercions, never raising

  Scenario: run_step runs one step and classifies the outcome into a StepResult
    Given a step: Step and a context: dict<str, any> and a registry: Registry and a scenario_name: str
    When run_step is called
    Then it matches the step against the registry and on a successful match invokes the handler with the bound captures, treating a handler that returns a falsey value as returning the unchanged context, and catches the handler's exception at this single boundary and classifies the outcome via the exception-type table so that step_unmatched gives status unmatched, ambiguous_step gives status ambiguous, a handler assertion failure gives status failed with code assertion_failed, any other handler exception gives status errored with code step_errored, and a clean run gives status ok with a NOTHING fault, and on any non-ok status the calling scenario stops and the remaining steps are not run

  Scenario: run_scenario runs one scenario and returns a ScenarioReport
    Given a scenario: Scenario and a background: list<Step> and a registry: Registry
    When run_scenario is called
    Then it folds the steps, background steps first then the scenario's own, over an empty immutable context, running each with run_step, threading each step's returned context into the next, and stopping at the first non-ok step, and sets the scenario status to ok iff every executed step is ok and else to err, and stamps duration_ms with the wall-clock run time, the one impure read inside this function reading the clock, which a spoke may treat as 0 in a repeatable-test mode

  Scenario: fold_feature_report combines per-scenario reports into a FeatureReport
    Given a feature: Feature and a scenario_reports: list<ScenarioReport>
    When fold_feature_report is called
    Then it counts the scenarios whose status is ok into total_passed and the rest into total_failed, and returns a FeatureReport carrying the feature_name, source_path, the scenario reports and the two counts, reading no world and raising nothing

  Scenario: step_fault builds one StepFault from its parts
    Given a code: str and a detail: str and a scenario_name: str and a step_text: str
    When step_fault is called
    Then it returns the StepFault assembled from the four values, pure, assembling a value rather than raising, which is how matching, binding and run failures stay data all the way to the edge

  Scenario: run_feature runs one whole feature and returns a FeatureReport
    Given a source: str and a source_path: str and a registry: Registry
    When run_feature is called
    Then it calls parse_feature and on ok runs every scenario with run_scenario and folds the per-scenario reports with fold_feature_report into one FeatureReport, and on a parse err yields a FeatureReport whose single scenario carries the bad_feature_syntax fault so a parse failure is reported as a failure and never swallowed, raising nothing

  Scenario: _is_blank classifies the blank line kind
    Given a line: str
    When _is_blank is called
    Then it returns true when the line is empty or holds only whitespace, the first check in the line_kinds table, reading no world

  Scenario: _starts_with classifies the keyword line kinds
    Given a line: str and a prefix: str
    When _starts_with is called
    Then it returns true when the line, ignoring leading whitespace, begins with the bound prefix, which is # for a comment, @ for a tag, Feature: for the feature line and Scenario: for a scenario line, with the classification order making a # line a comment before it can be read as a feature, reading no world

  Scenario: _is_step classifies the step line kind
    Given a line: str
    When _is_step is called
    Then it returns true when the line, ignoring leading whitespace, begins with one of the five step keywords Given, When, Then, And or But followed by step text, reading no world, and a line matching no classifier falls through to the description kind

  Scenario: _on_ignore handles the blank and comment line kinds
    Given a state: dict<str, any> and a line: str
    When _on_ignore is called
    Then it returns the state unchanged, because a blank line or a # comment contributes nothing to the IR, reading no world

  Scenario: _on_tag handles the tag line kind
    Given a state: dict<str, any> and a line: str
    When _on_tag is called
    Then it returns a new state with the line's tag words, the @-prefixed words with the @ stripped, appended to the pending-tags list that awaits the next Scenario: line, reading no world and mutating nothing

  Scenario: _on_feature handles the feature line kind
    Given a state: dict<str, any> and a line: str
    When _on_feature is called
    Then it returns a new state recording the feature name, the text after Feature:, and setting the in-feature-header flag so the description lines that follow until the first Scenario: are accumulated as the feature description, reading no world

  Scenario: _on_scenario handles the scenario line kind
    Given a state: dict<str, any> and a line: str
    When _on_scenario is called
    Then it returns a new state that flushes any scenario under construction into the completed-scenarios list, starts a new scenario from the name after Scenario:, attaches and clears the pending tags, and clears the in-feature-header flag, and records a Scenario: line with no name as a structural violation in the state's error list that becomes a bad_feature_syntax fault at end of input, reading no world

  Scenario: _on_step handles the step line kind
    Given a state: dict<str, any> and a line: str
    When _on_step is called
    Then it returns a new state appending a Step, its literal kind, the text with the keyword stripped and the source line number, to the current scenario's steps, and updates the last-resolved-kind when the keyword is Given, When or Then so a following And or But inherits it, and records a step line that appears before any Scenario: as a structural violation in the error list that becomes a bad_feature_syntax fault, reading no world

  Scenario: _on_description handles the description line kind
    Given a state: dict<str, any> and a line: str
    When _on_description is called
    Then it returns a new state appending the line to the accumulated description while the parser is in the feature header, the free text between the Feature: line and the first Scenario:, reading no world

  Scenario: _classify sorts one source line into exactly one line kind
    Given a line: str
    When _classify is called
    Then it folds the line through the ordered line_kinds table of predicates and returns the name of the first kind whose predicate matches, one of blank, comment, tag, feature, scenario or step, or description when no predicate matches, with classification order significant so a # line is a comment even if it begins with the word Feature, reading no world

  Scenario: read_feature_source reads one feature file's text from disk
    Given a path: str
    When read_feature_source is called
    Then it reads that one file's text from disk and returns it, doing nothing else, neither parsing nor matching nor running nor writing, and its one side effect is reading the file

  Scenario: _discover_features lists the feature file paths under a path
    Given a path: str
    When _discover_features is called
    Then it returns the flat list of .feature file paths to run, the one file when path names a file or every *.feature found by searching the directory recursively when path names a directory, doing nothing else, and its one side effect is reading the file

  Scenario: _load_steps imports the step modules and builds the registry
    Given a module_paths: list<str> and a registry: Registry
    When _load_steps is called
    Then it imports each named module from the running process and calls that module's register builder, threading the registry through the modules in order and returning the fully built Registry, doing nothing else, neither parsing nor matching nor running, and its one side effect is reading the process

  Scenario: print_report writes one feature report's summary to stdout
    Given a report: FeatureReport
    When print_report is called
    Then it writes that report's summary line to standard output and returns nothing, a terminus that only writes, declaring no fault because a report is plain data and a failed stdout write is not an engine fault, and its one side effect is writing stdout

  Scenario: run_cli sequences the CLI run and returns the exit code
    Given an argv: list<str>
    When run_cli is called
    Then it builds the registry by seeding empty_registry and threading it through the --steps modules with _load_steps, discovers the .feature files under the positional path with _discover_features, and for each discovered file reads its text with read_feature_source, runs it with the pure run_feature and writes the report with print_report, and returns the process exit code 0 iff total_failed is 0 across every feature run and else 1, sequencing the readers and the pure core and doing no filesystem or process read of its own beyond calling the readers

  Scenario: main hands argv to the orchestrator and returns the exit code
    Given an argv: list<str>
    When main is called
    Then it hands argv straight to the orchestrator run_cli and returns the exit code run_cli decides, turning it into the process exit, holding no discovery, registry building, parsing or running, with the exit code 0 iff total_failed is 0 across all features and else 1, and the world reaches it through the cli:__main__ entry the entry-check reports UNCHECKED

  Scenario: _flush moves the scenario under construction into the completed list
    Given a parse state folded forward
    When _flush runs
    Then it returns a new state with the scenario under construction appended to the completed-scenarios list and none under construction, or the state unchanged when there is none, reading no world; it is shared by the _on_scenario handler, which flushes the previous scenario before the next, and by parse_feature, which flushes the last at end of input

  Scenario: _classify_exception maps a caught handler exception to its status and fault code
    Given an exception run_step caught at its single handler boundary
    When _classify_exception reads the section 7.1 table
    Then it returns the pair as a two-element list of strings, failed and assertion_failed for a handler assertion failure and the catch-all errored and step_errored for any other exception, reading no world and raising nothing

  Scenario: _now_ms reads the wall clock in milliseconds
    Given the run model needs a scenario's duration
    When _now_ms reads the clock
    Then it returns the current monotonic time in milliseconds, the one impure seam the orchestrator injects as the run's now parameter so run_scenario brackets the fold without reading the clock itself, and a spoke may stub it to return 0 for a repeatable test mode

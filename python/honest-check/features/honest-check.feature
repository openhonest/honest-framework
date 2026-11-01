Feature: honest-check — generated, one scenario per function (5 total)

  Scenario: check_source
    Given source: str and path: str and rule_config: RuleConfig
    When check_source is called
    Then it takes one source unit already held in memory and parses it under the grammar honest-parse detects from path's extension
    And source is the full text of one honest-framework application source file in a language honest-parse recognizes (Python, JavaScript or TypeScript, Ruby, Go), never a .hd declaration and never honest-check's own internals
    And it resolves the framework's own construction call sites in source — vocabulary(), binding(), chain(), composed(), state_machine() — to build the declaration graph of vocabularies, bindings, links, chains and state machines
    And path is the filesystem path the text came from, used to detect the grammar and to stamp each diagnostic's source_location, never to open the file
    And it runs every rule in the RuleId catalogue, both startup_rules and non_startup_rules, over that graph, the rules reading the graph and not raw ASTs
    And rule_config is the resolved per-rule settings, a map from a configurable rule's id to its settings; when the project set min_run = N it is {"HC-OR003": {"min_run": N}} and when it set nothing it is empty, and an empty map means HC-OR003 does not fire
    And it returns the list of every Diagnostic the rules produced over this one source, an empty list meaning the source is clean
    And it never opens a file, never executes the application code it inspects, and never modifies anything
    And it raises nothing: a violation comes back as a Diagnostic, never as an exception

  Scenario: read_source
    Given path: str
    When read_source is called
    Then it pulls one file's complete text from disk and hands it back as a string, so the orchestrator can pass that text to check_source
    And path is the filesystem path of the one file to read, always a concrete source file because file discovery at the boundary has already dropped directories, nonexistent paths, unrecognized extensions and exclude-glob matches before check_paths runs, so none reach read_source
    And it returns that file's full contents as a string
    And it reads and does nothing else: it does not parse, check, or write
    And it declares no fault and names no absence case: the spec states no fault for a path that becomes unreadable after discovery and leaves whether such a path raises, and what it raises, undecided
    And its one side effect is reading the filesystem

  Scenario: load_config
    Given no parameters
    When load_config is called
    Then it finds honest-check.toml in the nearest ancestor directory of the working directory, reads it, and resolves the project's declared per-rule settings into the rule_config map the orchestrator passes to check_source
    And it takes no argument because the startup door has no --config flag and the config location is the nearest ancestor of where the host application runs
    And honest-check's one configurable rule is HC-OR003, whose single setting min_run has no built-in default; it does not configure HC-P008 (max_lines) or HC-P012 (max_mocks), which are honest-test's rules, so no other rule id ever appears as a key
    And it returns the empty map when honest-check.toml sets nothing or no honest-check.toml exists, because min_run has no documented default to fill in
    And it returns {"HC-OR003": {"min_run": N}} when the project sets min_run = N with the per-rule table [rules.HC-OR003] carrying min_run = N
    And a run configured with nothing is a run where HC-OR003 does not fire and check_source never has to invent a threshold
    And it reads the filesystem and resolves what it read: it does not parse source, check, or write
    And its one side effect is reading the filesystem

  Scenario: check_paths
    Given paths: list<str>
    When check_paths is called
    Then it pulls the project's resolved rule_config with load_config once at the start of the run and applies that one map to every file
    And for each path it was given it pulls that file's text with read_source and runs check_source over it under that same rule_config
    And it folds every file's diagnostics into one flat combined list, in the order the paths were given
    And one resolved configuration governs the whole run, so no file is checked under different settings and the result does not depend on how many files there are
    And paths is the list of filesystem paths to check, each already resolved to a concrete source file by boundary file discovery before this orchestrator runs
    And an empty path list returns [], and an empty returned list means every file was clean

  Scenario: startup_check
    Given paths: list<str> and on_error: str and severity: str
    When startup_check is called
    Then it is the door the framework's development-mode startup integration calls; it hands paths to check_paths, gets back the folded diagnostics, decides whether any finding reaches the blocking severity, acts per on_error, and returns the same diagnostic list check_paths produced
    And paths is the list of source paths to check, for example ['src/'], handed straight to check_paths
    And at startup it runs only the startup_rules set: HC-SYN runs first because a file that does not parse has no architecture to check, then HC001, HC002, HC003, HC006, HC007, HC011, HC-SM01, HC-SM02, HC-SM05, because the full-codebase non_startup_rules are too slow for startup
    And HC-SYN emits error when the source does not parse; HC001, HC002, HC006, HC007, HC-SM01, HC-SM02 and HC-SM05 are error-only; HC003 emits error on a decidable Set-versus-Set recognizer overlap and info when a predicate is involved; HC011 fires through actual construction and rejects a catch-all recognizer at error severity
    And severity is the minimum severity a diagnostic must reach to count as a block, one of 'error', 'warning' or 'info'; the documented setting is 'error', so only error-severity diagnostics block while warnings and infos are reported but never block, and a diagnostic below this threshold never triggers on_error
    And on_error is exactly one of three words: 'warn' prints the blocking violations to stderr and lets startup continue; 'raise' raises HonestCheckError carrying the full report, stopping startup by exception; 'halt' prints the blocking violations to stderr and then exits the process with code 1
    And the process exit belongs to the 'halt' path only: after printing it exits with code 1 and startup_check does not return in that case
    And its one side effect is writing to stderr: both 'warn' and 'halt' print the blocking violations there, while 'raise' writes nothing because it carries the report in the exception
    And it raises HonestCheckError only when on_error is 'raise' and at least one diagnostic reaches severity, the error carrying the full report

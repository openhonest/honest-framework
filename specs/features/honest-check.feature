Feature: honest-check — the static checker, the honesty gate
  One scenario per declared function (18 total). One pure core folds the whole rule
  catalogue over a declaration graph; two orchestrators pull files and share that core;
  two doors reach the world (startup integration and the CLI); the rest read the
  filesystem, parse the argument vector, or render the report.

  Scenario: check_source runs the declared rule catalogue over one source's declaration graph
    Given source: str and path: str and rule_config: RuleConfig
    When check_source is called
    Then it parses the source under the grammar honest-parse detects from path's extension, resolves the framework's construction call sites (vocabulary, binding, chain, composed, state_machine), and builds the declaration graph
    And it runs every rule in the RuleId catalogue — both startup_rules and non_startup_rules — over that graph, not over raw ASTs, and returns the findings as a list of Diagnostic
    And an empty list means the source is clean, and HC-OR003 fires only when rule_config carries a min_run for it
    But it never opens a file, never executes the application code, never modifies anything, and raises nothing: a violation comes back as a Diagnostic

  Scenario: read_source pulls one file's complete text from disk
    Given path: str
    When read_source is called
    Then it reads that one concrete source file and returns its full contents as a string, and does nothing else — no parse, no check, no write
    And its one side effect is reading the filesystem

  Scenario: load_config resolves the project's per-rule settings into a RuleConfig
    Given no arguments
    When load_config is called
    Then it finds honest-check.toml in the nearest ancestor directory of the working directory and resolves the [rules] per-rule settings into a RuleConfig map
    And it returns {"HC-OR003": {"min_run": N}} when the project sets min_run = N, and the empty map when the file sets nothing or no honest-check.toml exists, because min_run has no default to fill in
    And its one side effect is reading the filesystem

  Scenario: check_paths folds every path's diagnostics under one resolved config
    Given paths: list<str>
    When check_paths is called
    Then it pulls the project's rule_config once with load_config, then for each path reads that file's text with read_source and runs check_source over it under that same rule_config
    And it returns one flat list of every Diagnostic across all files, in the order the paths were given, and an empty list means every file was clean

  Scenario: startup_check is the development-mode startup door that runs only the startup rules
    Given paths: list<str> and on_error: str and severity: str
    When startup_check is called
    Then it hands paths to check_paths, runs only the startup_rules subset with HC-SYN first, and returns the same diagnostic list check_paths produced
    And it decides a block when a finding reaches severity, then acts per on_error: 'warn' prints the blocking violations to stderr and lets startup continue; 'halt' prints them to stderr and exits the process with code 1; 'raise' writes nothing and raises HonestCheckError carrying the full report
    And it raises HonestCheckError only when on_error is 'raise' and at least one diagnostic reaches severity
    And its one side effect is writing to stderr

  Scenario: parse_args turns the raw argv into a resolved CliArgs
    Given argv: list<str>
    When parse_args is called
    Then it reads the positional paths and the base-mode flags and returns a CliArgs: --config into config_path, --format into format, --severity into severity, repeatable --rule into include_rules, repeatable --no-rule into exclude_rules, and --report into report_mode
    And it resolves absence to an explicit bounded value at the boundary: an omitted --format becomes 'human' and an omitted --severity becomes 'warning', so no downstream function tells 'chose' from 'forgot'
    But it opens no file and performs no check, and it ignores --fix and --watch, which this layer does not carry

  Scenario: enforced_rules_of returns the cumulative rules a level enforces
    Given level: AdoptionLevel
    When enforced_rules_of is called
    Then it returns every HC rule enforced at that level per the cumulative section 9.4 membership: always_rules hold everywhere, Structural adds structural_rules, Boundary adds boundary_rules, Typed adds typed_rules, and Declared adds declared_rules to return the whole AdoptionRule set
    And its length is the enforced_count the adoption line prints, and a rule not in the result is one prepare_report downgrades to info
    And it reads nothing and returns pure data

  Scenario: prepare_report turns the raw findings into the report formatters render
    Given diagnostics: list<Diagnostic> and args: CliArgs and adoption: AdoptionLevel
    When prepare_report is called
    Then it applies, in order, the adoption downgrade — a diagnostic whose rule is not in enforced_rules_of(adoption) is downgraded to info — then the --severity threshold in args, then the --rule/--no-rule filters in args
    And it counts the surviving findings into errors, warnings and infos, fills rule_counts with each rule's count only when args.report_mode is set and leaves it empty otherwise, and records adoption, enforced_count and total_count 50 for the adoption line
    And it does not re-resolve suppression directives, which check_source resolved earlier, and it reads nothing and returns the CheckReport

  Scenario: format_human renders the human-readable CLI default
    Given report: CheckReport
    When format_human is called
    Then it opens with the adoption line, renders one block per diagnostic (a file:line:col header split from source_location, the message and reference line, and the quoted context lines), and closes with the 'Found N errors, M warnings.' tally
    And when report.report_mode is set it instead renders the per-rule table from report.rule_counts, one row per rule with its severity, finding count and whether the declared level enforces it
    And it returns the finished text and performs no I/O

  Scenario: format_json renders the JSON machine format for CI and tooling
    Given report: CheckReport
    When format_json is called
    Then it produces an object with version, timestamp, a summary carrying errors, warnings, infos, adoption and enforced_rules, and a diagnostics array whose entries split source_location into file, line and col and carry rule, severity, message, context and fixable
    And when report.report_mode is set it carries the per-rule counts from report.rule_counts
    And it returns the JSON text as a string and performs no I/O

  Scenario: format_github renders GitHub Actions workflow-command annotations
    Given report: CheckReport
    When format_github is called
    Then it emits one line per diagnostic, '::error' for an error-severity finding and '::warning' otherwise, each carrying file, line and col from source_location, title=<rule id>, and the message as the body, so findings surface inline on a pull request
    And it emits the adoption line as a leading annotation or notice so every run still states its level
    And it returns the annotation text and performs no I/O

  Scenario: format_junit renders JUnit XML for CI systems that consume it
    Given report: CheckReport
    When format_junit is called
    Then it produces a <testsuites name="honest-check"> document with one <testsuite> per file carrying that file's failure count, and within each a <testcase> holding a <failure> whose message is the finding and whose body quotes the offending source line
    And it returns the XML text and performs no I/O

  Scenario: resolve_exit_code decides the process exit code from the prepared report
    Given report: CheckReport
    When resolve_exit_code is called
    Then when report.report_mode is true the code is '0' always, because --report reports and does not judge
    And otherwise the code is '1' when report.errors is greater than zero and '0' when no error survived, because warnings and infos never block
    But it never returns '2', which is reserved for a configuration error or internal failure the door applies, since no function on this path is declared to detect such a failure

  Scenario: discover_files walks the paths and keeps only recognized, non-excluded files
    Given paths: list<str> and exclude: list<str>
    When discover_files is called
    Then for each path it keeps a file when no exclude glob matches it, and recursively walks a directory keeping every file whose extension honest-parse recognizes and that no exclude glob matches, asking honest-parse rather than carrying its own extension table
    And it returns the flat list of concrete source files, filtering out directories, nonexistent paths and files of unrecognized extension, so every path that reaches read_source is a concrete recognized source file
    And its one side effect is reading the filesystem

  Scenario: load_project_config reads the honest-check.toml [check] section
    Given no arguments
    When load_project_config is called
    Then it finds honest-check.toml in the nearest ancestor directory of the working directory and returns the [check] settings: the exclude globs discover_files drops matches of and the adoption level section 9.4 grades against
    And exclude is the empty list when [check] exclude is unset, and adoption is 'Declared' when [check] adoption is absent, distinct from load_config which returns only the [rules] RuleConfig
    And its one side effect is reading the filesystem

  Scenario: write_report prints the rendered report text to stdout
    Given text: str
    When write_report is called
    Then it prints the already-rendered report text to standard output and returns whether the write completed, formatting and deciding nothing
    And it is a terminus that calls nothing inward, and its one side effect is writing stdout

  Scenario: run_check orchestrates the whole CLI path and returns the exit code
    Given argv: list<str>
    When run_check is called
    Then it parses the arguments with parse_args, pulls the [check] settings with load_project_config and the per-rule settings with load_config each once, discovers the concrete source files with discover_files, and for each file pulls its text with read_source and runs check_source over it under the one resolved RuleConfig, folding every file's diagnostics into one list
    And it prepares the combined findings with prepare_report, selects the renderer with the by_format dispatch on the resolved format and renders the report to text, writes that text to stdout through write_report, and returns the ExitCode resolve_exit_code decides

  Scenario: main is the command-line door that hands argv to the orchestrator
    Given argv: list<str>
    When main is called
    Then it receives the argument vector, hands it straight to run_check, and exits the process with the ExitCode run_check returns, holding no parsing, discovery or checking logic
    And the process exit is the door's output to the shell: 0 means success, 1 means the gate failed with one or more errors at or below the declared adoption level, and 2 means the run could not complete

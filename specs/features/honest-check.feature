Feature: honest-check — the static checker, the honesty gate
  One scenario per declared function (21 total). One pure core folds the whole rule
  catalogue over a declaration graph; a second pure core crosses a module's .hd against
  its whole package; two orchestrators pull files and share those cores; two doors reach
  the world (startup integration and the CLI); the rest read the filesystem, parse the
  argument vector, pair a path with its text, or render the report.

  Scenario: check_source runs the declared rule catalogue over one source's declaration graph
    Given source: str and path: str and rule_config: RuleConfig
    When check_source is called
    Then it parses the source under the grammar honest-parse detects from path's extension, resolves the framework's construction call sites (vocabulary, binding, chain, composed, state_machine), and builds the declaration graph
    And it runs every single-source rule in the RuleId catalogue — both startup_rules and non_startup_rules — over that graph, not over raw ASTs, and returns the findings as a list of Diagnostic
    And it runs none of the five declaration-crossing rules, which need a declaration check_source does not hold; an empty list means the source is clean, and HC-OR003 fires only when rule_config carries a min_run for it
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
    And it reads the two crossing-mode flags: --declaration into declaration (the path to the one module .hd to cross against the code) and --exports into exports (the path to the package's export module HC-REF005 reads)
    And it resolves absence to an explicit bounded value at the boundary: an omitted --format becomes 'human', an omitted --severity becomes 'warning', and an omitted --declaration or --exports becomes the empty string, so no downstream function tells 'chose' from 'forgot' and an empty declaration is the signal run_check reads to stay in base mode
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
    And it counts the surviving findings into errors, warnings and infos, fills rule_counts with each rule's count only when args.report_mode is set and leaves it empty otherwise, and records adoption, enforced_count and total_count 53 for the adoption line
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
    But it never returns '2': exit code 2 is the run-could-not-complete code the door applies when read_declaration's Fault is routed out, and that Fault never reaches this function, having been routed out ahead of prepare_report

  Scenario: pair_source joins a path and its already-read text into a SourceFile
    Given path: str and text: str
    When pair_source is called
    Then it joins the path discover_files walked to with the text read_source pulled into one SourceFile record and returns it
    And it exists because the declaration's producer model credits only a reader's answer or a function's return as a type's producer, and neither read_source (answers a str) nor discover_files (answers a str) answers a SourceFile
    But it reads nothing, opens nothing and decides nothing — it only joins the two values

  Scenario: cross_declaration crosses one .hd declaration against the whole package and returns the crossing findings
    Given sources: list<SourceFile> and declaration: Declaration and export_source: str and rule_ids: list<CrossingRule>
    When cross_declaration is called
    Then it is the crossing-mode counterpart of check_source: it crosses the one parsed .hd declaration against the module's whole package of source files at once and returns the declaration-crossing findings as a list of Diagnostic, running only the crossing rules named in rule_ids — an empty rule_ids runs all five
    And it takes the package as a list of SourceFile, not a single source, because HC-REF005 crosses the declared function set against the package's entire defined-function set, which needs every file's definitions in view together; it parses each file under the grammar honest-parse detects from its path extension, reads from the code each fact it states outright (each function's name, whether it is async def, whether it can return the host nothing, whether its body yields, its call graph), and crosses those against the same-named declared function
    And the per-rule crossing logic (HC-R002, HC-R003, HC-R004, HC-R005, HC-REF005) is nested here as data exactly as check_source holds the construction rules, and the exact diagnostic each rule produces for a given package and declaration is pinned by the conformance suite, not by any per-rule function
    But it opens no file, executes no application code, modifies nothing, and raises nothing: a disagreement comes back as a Diagnostic; an empty list means the declaration and the package agree

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

  Scenario: read_declaration loads a named .hd and returns its parsed declaration or a Fault
    Given hd_path: str
    When read_declaration is called
    Then it reads the named .hd file's text from disk and parses it through honest-design's read_hd, returning the one parsed module (a Declaration) that cross_declaration crosses against the code
    And it returns a Fault when the .hd is missing or honest-design cannot parse it — the configured read failure §HC-R002 routes to exit code 2, because a gate that reports clean over a declaration it could not open is no gate; the Fault is a value that travels by return, never an exception
    But it does not check, does not touch the source tree, and does not construct the declaration shape, which is honest-design's to own; its one side effect is reading the filesystem

  Scenario: run_check orchestrates the whole CLI path and returns the exit code or routes the Fault out
    Given argv: list<str>
    When run_check is called
    Then it parses the arguments with parse_args, pulls the [check] settings with load_project_config once, and discovers the concrete source files with discover_files, then runs in one of two modes chosen by whether CliArgs.declaration is empty
    And in base mode (empty declaration) it pulls the per-rule settings with load_config and, for each discovered file, pulls its text with read_source and runs check_source over it under the one resolved RuleConfig, folding every file's diagnostics into one list
    And in declaration-crossing mode (non-empty declaration) it pulls the one parsed module with read_declaration, pulls the export module's text with read_source when CliArgs.exports is non-empty, pulls each file's text with read_source and joins each path to its text with pair_source into a list<SourceFile>, then runs cross_declaration once over that whole-package batch running only the crossing rules named in CliArgs.include_rules
    And when read_declaration answers a Fault it checks nothing over a declaration it could not open and routes that Fault straight outward as its own answer; otherwise it prepares the combined findings with prepare_report, selects the renderer with the by_format dispatch, writes the text through write_report, and returns the ExitCode resolve_exit_code decides

  Scenario: main is the command-line door that hands argv to the orchestrator
    Given argv: list<str>
    When main is called
    Then it receives the argument vector, hands it straight to run_check, and holds no parsing, discovery or checking logic
    And on an ExitCode answer it exits the process with it: 0 means success (warnings may have printed) and 1 means the gate failed with one or more errors at or below the declared adoption level
    And on the declaration-read Fault run_check routed outward (a configured .hd that was missing or did not parse, §HC-R002) it discharges it at exit code 2, the run-could-not-complete code, raising HonestCheckError carrying the Fault's problem and remedy rather than returning a clean code over a declaration it could not open
    But it raises HonestCheckError only on that declaration-read failure; this door is the one place a Fault crosses from a value into a world effect

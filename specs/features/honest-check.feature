Feature: honest-check — generated, one scenario per function (87 functions, 89 scenarios: run_check carries one per decision path)

  Derived from python/honest-check/honest-check.hd alone: its signatures, roles, notes, bounded
  vocabularies (RuleId, CrossingRule, Format, Severity, AdoptionLevel, ExitCode, Direction), the
  by_format dispatch, and the cli and cli-seam chains. honest-check is the static checker, the
  honesty gate: it reads honest-framework application source (the languages honest-parse recognizes),
  resolves the framework's construction call sites into a declaration graph, and runs the HC rules
  over that graph. The world enters only through doors — startup_check, main, check_seams — each
  handing its inputs to one orchestrator and then to the pure cores. run_check runs in two modes and
  its crossing-mode read can fail, so it carries one scenario per decision path.

  # --- The per-file engine: context builder and rule core -----------------------

  Scenario: build_context
    Given source: bytes and path: str and rule_config: RuleConfig
    When build_context is called
    Then it parses source under the grammar honest-parse selects from path, calls resolve_aliases over the parsed tree and the source bytes to resolve the import-alias map, walks the syntax-tree nodes into the node list, reads the declared function-to-role map, and merges honest-check's one configurable rule's documented value (HC-OR003 min_run = 3) over the project's declared rule_config in the open; it returns one CheckContext holding the parsed root, the node list, the alias map, the role map, the source bytes, the path and the resolved per-rule settings; it is the only builder of the CheckContext, runs no rule, does no input or output, and raises nothing

  Scenario: check_source
    Given context: CheckContext and declaration: Declaration | NOTHING
    When check_source is called
    Then it runs every rule in the RuleId catalogue (startup_rules and non_startup_rules) over the declaration graph the context carries by threading it through check_construction and check_per_file, then runs apply_suppression over their combined findings; the three boundary rules HC-P002, HC-P004 and HC-P005 consult declaration only on the path where they would otherwise flag a non-boundary function and drop the finding when the .hd marks that same function boundary_in, boundary_out or reader, while NOTHING leaves the decorator verdict standing; it returns the list of every Diagnostic the rules produced (an empty list means clean), opens no file, executes none of the code it inspects, parses nothing itself, and raises nothing

  Scenario: read_source
    Given path: str
    When read_source is called
    Then it reads the one file's complete contents from disk and returns them as raw bytes, not a decoded string, because honest-parse parses bytes and reports byte offsets; path is always a concrete, honest-parse-recognized source file that discovery already filtered to, so it does not decode, parse, check or write; the spec states no fault for a path that becomes unreadable after discovery, so it declares none and names no absence case; its one side effect is reading the file

  Scenario: resolve_rule_config
    Given data: dict<str, any>
    When resolve_rule_config is called
    Then it builds the [rules] RuleConfig from the parsed honest-check.toml table, returning {"HC-OR003": {"min_run": N}} when the project set min_run and the empty map otherwise; it is pure, calls nothing, and fills in no documented default, because build_context supplies the documented min_run = 3 later

  Scenario: load_config
    Given no arguments
    When load_config is called
    Then it finds honest-check.toml in the nearest ancestor directory, reads it, and hands back the raw parsed [rules] table as data (the empty dict when no [rules] section or no file exists); it takes no argument because the startup door has no --config flag, builds no record of its own, and calls nothing; its one side effect is reading the file

  Scenario: check_paths
    Given paths: list<str> and severity: str
    When check_paths is called
    Then it pulls the raw [rules] table with load_config once and builds the RuleConfig with resolve_rule_config, then for each path reads the file with read_source, builds the file's CheckContext with build_context, and runs check_source over it with NOTHING for the declaration (startup crosses no .hd), folding every file's diagnostics into one list; it then resolves the blocking threshold from severity and runs blocking_findings over the combined list, and returns a StartupFindings carrying both the full folded list (all) and the blocking subset (blocking); the orchestrator does no reading, parsing or checking itself

  Scenario: blocking_findings
    Given diagnostics: list<Diagnostic> and threshold: int
    When blocking_findings is called
    Then it returns only the diagnostics whose severity reaches the blocking threshold, so the blocking decision is made off the door; it is pure

  Scenario: startup_check
    Given paths: list<str> and on_error: str and severity: str
    When startup_check is called
    Then it hands paths and severity to check_paths and gets back a StartupFindings, then acts per on_error over the blocking subset: 'warn' prints the blocking violations to stderr and lets startup continue, 'raise' raises HonestCheckError carrying the full all list, and 'halt' prints the blocking violations to stderr and then exits the process with code 1; it runs only the startup_rules set (HC-SYN first, because a file that does not parse has no architecture to check), returns the full all list; its one side effect is writing stderr; it raises HonestCheckError only when on_error is 'raise' and at least one diagnostic reaches severity

  # --- The CLI pure core --------------------------------------------------------

  Scenario: parse_args
    Given argv: list<str>
    When parse_args is called
    Then it turns the raw argument vector into the resolved CliArgs, reading the positional paths and the flags and resolving absence at the boundary to explicit bounded values: an omitted --format becomes 'human', an omitted --severity becomes 'warning', an omitted --declaration or --exports becomes the empty string, and --rule/--no-rule/--report/--config are collected into include_rules/exclude_rules/report_mode/config_path; it opens no file, performs no check, ignores --fix and --watch, and returns the CliArgs

  Scenario: enforced_rules_of
    Given level: AdoptionLevel
    When enforced_rules_of is called
    Then it returns every HC rule enforced at the given adoption level under the cumulative section 9.4 membership: always_rules at every level, plus structural_rules at Structural, plus boundary_rules at Boundary, plus typed_rules at Typed, plus declared_rules at Declared (the whole 53-rule AdoptionRule set); its length is the enforced_count the adoption line prints, and a rule absent from the result is one prepare_report downgrades to info; it reads nothing and returns pure data

  Scenario: prepare_report
    Given diagnostics: list<Diagnostic> and args: CliArgs and adoption: AdoptionLevel
    When prepare_report is called
    Then it applies, in order, the adoption downgrade (every diagnostic whose rule is not in enforced_rules_of(adoption) is downgraded to info), the --severity threshold in args (findings below it are dropped), and the --rule/--no-rule filters in args; it counts the survivors into errors, warnings and infos, fills rule_counts when args.report_mode is set and leaves it empty otherwise, and records adoption, enforced_count and total_count (53); it does not re-resolve suppression (check_source did that), reads nothing, and returns the CheckReport

  Scenario: format_human
    Given report: CheckReport
    When format_human is called
    Then it renders the human-readable default: the adoption line, then one block per diagnostic (a file:line:col header split from source_location, the message and reference line, and the quoted context lines), closing with the 'Found N errors, M warnings.' tally; when report.report_mode is set it instead renders the per-rule table from report.rule_counts; it returns the finished text and performs no I/O

  Scenario: format_json
    Given report: CheckReport
    When format_json is called
    Then it renders the JSON machine format: an object with version, timestamp, a summary carrying errors, warnings, infos, adoption and enforced_rules, and a diagnostics array whose entries split source_location into file, line and col and carry rule, severity, message, context and fixable; it carries the per-rule counts when report.report_mode is set; it returns the JSON text and performs no I/O

  Scenario: format_github
    Given report: CheckReport
    When format_github is called
    Then it renders GitHub Actions workflow-command annotations: one ::error line for an error-severity finding and ::warning otherwise, each carrying file, line and col and title=<rule id> with the message as the body, and the adoption line as a leading annotation; it returns the annotation text and performs no I/O

  Scenario: format_junit
    Given report: CheckReport
    When format_junit is called
    Then it renders a <testsuites name="honest-check"> JUnit XML document with one <testsuite> per file and a <testcase>/<failure> per finding; it returns the XML text and performs no I/O

  Scenario: resolve_exit_code
    Given report: CheckReport
    When resolve_exit_code is called
    Then it returns ExitCode '0' always when report.report_mode is true (--report reports, it does not judge), otherwise '1' when report.errors is greater than zero and '0' when no error survived; it never returns '2', which is reserved for a configuration error or internal failure the door applies

  # --- The declaration-crossing core (--declaration) ----------------------------

  Scenario: pair_source
    Given path: str and text: bytes
    When pair_source is called
    Then it joins one discovered path with its already-read bytes into a SourceFile, the record the whole-package cores are fed; it reads nothing, opens nothing and decides nothing, and returns the SourceFile carrying the path and the raw bytes

  # hd: python/honest-check/honest-check.hd::_read_all
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: _read_all reads literal export names including an empty list
    Given export_source: bytes contains one module-level __all__ assignment to ["read", "write", "read"] or []
    When _read_all is called
    Then it returns the set containing "read" and "write" for the first assignment and the empty set for the second

  # hd: python/honest-check/honest-check.hd::_read_all
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: _read_all returns NOTHING when no unique literal export list is present
    Given export_source: bytes is a nonempty initializer with no __all__ assignment, a computed assignment, multiple competing assignments, a list with a non-string item, a list with a nonliteral item, or malformed Python containing an otherwise literal-looking __all__ list
    When _read_all is called
    Then it returns NOTHING for each initializer

  # hd: python/honest-check/honest-check.hd::_read_all
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: _read_all distinguishes direct export list writes from ordinary reads
    Given export_source: bytes contains the literal module-level assignment __all__ = ["read"] followed in separate cases by __all__.extra = "write", __all__[0] = "write", the plain read alias = __all__.copy, or the assignment collector[__all__] = 1 that reads __all__ as a key
    When _read_all is called
    Then it returns NOTHING for each write attempt on __all__ and the set containing only "read" for each read of __all__

  # hd: python/honest-check/honest-check.hd::_exported_names
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: _exported_names returns an empty set when export source is omitted
    Given export_source: bytes is empty, the sentinel for no supplied initializer
    When _exported_names is called
    Then it returns the empty set

  # hd: python/honest-check/honest-check.hd::_exported_names
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: _exported_names preserves the supplied initializer result
    Given export_source: bytes is a nonempty initializer containing a literal list with "read", a literal empty list, or a computed export list
    When _exported_names is called
    Then it returns the set containing "read", the empty set, or NOTHING, respectively

  # hd: python/honest-check/honest-check.hd::exported_exception_names
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: exported_exception_names recognizes explicit and builtin type exception classes
    Given sources: list<SourceFile> supplies package definitions, and export_source: bytes has literal __all__ listing "ExplicitError" declared as a class inheriting Exception and "ConstructedError" assigned using the unshadowed builtin type with literal bases (Exception,)
    When exported_exception_names is called
    Then it returns the set containing only "ExplicitError" and "ConstructedError"

  # hd: python/honest-check/honest-check.hd::exported_exception_names
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: exported_exception_names resolves a same-package from-import to its public alias
    Given sources: list<SourceFile> includes a same-package file declaring LocalError as an Exception subclass and export_source: bytes lists "PublicError" in literal __all__ and binds it with a from-import alias of LocalError
    And sources also supplies exactly one Python __init__.py whose bytes match export_source
    When exported_exception_names is called
    Then it returns the set containing only "PublicError"

  # hd: python/honest-check/honest-check.hd::exported_exception_names
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: exported_exception_names excludes unresolved and non-exception bindings
    Given sources: list<SourceFile> does not contain the source for one exported from-import and export_source: bytes lists that import, a dynamically rebound name, an ordinary class, and an ordinary function in literal __all__
    When exported_exception_names is called
    Then it returns an empty set

  # hd: python/honest-check/honest-check.hd::exported_exception_names
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: exported_exception_names uses supplied initializer bytes for direct bindings
    Given export_source: bytes contains a literal __all__ naming LocalError and directly declares LocalError as an Exception subclass, and sources: list<SourceFile> contains only an initializer whose bytes differ and whose LocalError is an ordinary class
    When exported_exception_names is called
    Then it returns the set containing only "LocalError", using the supplied initializer bytes

  # hd: python/honest-check/honest-check.hd::exported_exception_names
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: exported_exception_names requires one byte-identical Python initializer for from-imports
    Given export_source: bytes lists "PublicError" in literal __all__ and binds it with a from-import alias of LocalError, and sources: list<SourceFile> has matching LocalError exception definitions for the candidate packages
    And separate cases supply no initializer, a mismatched Python initializer, only byte-identical non-Python source as the initializer, two byte-identical Python initializer paths in either order, a single matching Python initializer whose import target is supplied only as non-Python source, or a single matching Python initializer with a Python target and additional byte-identical non-Python source
    When exported_exception_names is called
    Then only the last case returns the set containing "PublicError" and the other cases return the empty set

  # hd: python/honest-check/honest-check.hd::exported_exception_names
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: exported_exception_names follows only one same-package import hop
    Given sources: list<SourceFile> has a unique Python initializer matching export_source: bytes, the initializer imports its listed public alias from one same-package Python file, and that file imports its binding from another same-package file containing an Exception subclass
    When exported_exception_names is called
    Then it returns the empty set because the exception requires a second import hop

  # hd: python/honest-check/honest-check.hd::cross_declaration
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: cross_declaration accepts a verified raised exception export without function arity
    Given sources: list<SourceFile> and export_source: bytes establish an actual exported exception class, declaration: Declaration names the same public binding in raises without a function card for it, and rule_ids: list<CrossingRule> contains only HC-REF005
    When cross_declaration is called
    Then it returns no HC-REF005 finding for that exception export

  # hd: python/honest-check/honest-check.hd::cross_declaration
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: cross_declaration requires a verified exception export to be named in raises
    Given sources: list<SourceFile> and export_source: bytes establish an actual exported exception class, declaration: Declaration omits its public name from raises and has no function card for it, and rule_ids: list<CrossingRule> contains only HC-REF005
    When cross_declaration is called
    Then it returns the HC-REF005 missing-declaration finding for that public name

  # hd: python/honest-check/honest-check.hd::cross_declaration
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: cross_declaration keeps findings for unresolved exports and ordinary functions despite raises
    Given sources: list<SourceFile> and export_source: bytes expose an unresolved from-import, an ordinary function with no function card, and an ordinary function whose definition and function card have different arity, declaration: Declaration names all three export names in raises, and rule_ids: list<CrossingRule> contains only HC-REF005
    When cross_declaration is called
    Then it returns missing-declaration findings for the unresolved binding and the ordinary function without a card, and the arity finding for the declared function

  # hd: python/honest-check/honest-check.hd::cross_declaration
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: cross_declaration reports a supplied initializer with no export list
    Given sources: list<SourceFile> and declaration: Declaration agree on the package functions, export_source: bytes is a supplied nonempty Python initializer without __all__, and rule_ids: list<CrossingRule> contains only HC-REF005
    When cross_declaration is called
    Then it returns an HC-REF005 error explaining that the package needs a literal export list

  # hd: python/honest-check/honest-check.hd::cross_declaration
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: cross_declaration reports a supplied initializer with a computed export list
    Given sources: list<SourceFile> and declaration: Declaration agree on the package functions, export_source: bytes is a supplied nonempty Python initializer assigning __all__ from a function call, and rule_ids: list<CrossingRule> contains only HC-REF005
    When cross_declaration is called
    Then it returns an HC-REF005 error explaining that the package needs a literal export list

  # hd: python/honest-check/honest-check.hd::cross_declaration
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: cross_declaration uses a synthetic label for an invalid initializer without a known path
    Given sources: list<SourceFile> supplies neither a known initializer path nor a package root, export_source: bytes supplies a nonempty invalid export declaration, declaration: Declaration has no source location identifying the package, and rule_ids: list<CrossingRule> contains only HC-REF005
    When cross_declaration is called
    Then it returns an HC-REF005 error for the invalid export list at the synthetic label "__init__.py"
    And the diagnostic makes no claim that a file at that label exists

  # hd: python/honest-check/honest-check.hd::cross_declaration
  # spec: HC-REF005 (as cited by the declaration)
  Scenario: cross_declaration preserves arity findings when the export list is invalid
    Given sources: list<SourceFile> defines one function with two parameters, declaration: Declaration declares that function with one parameter, export_source: bytes contains a nonempty initializer with a computed __all__, and rule_ids: list<CrossingRule> contains only HC-REF005
    When cross_declaration is called
    Then it reports the invalid export list and the independent arity mismatch without inferring per-export findings from the invalid list

  Scenario: cross_declaration
    Given sources: list<SourceFile> and declaration: Declaration and export_source: bytes and rule_ids: list<CrossingRule>
    When cross_declaration is called
    Then it crosses one module's .hd against the whole package of source files at once and runs only the crossing rules named in rule_ids (an empty list runs all five): HC-R002 errors when a boundary_out function calls an orchestrator or boundary_in, HC-R003 when async-ness disagrees with the declared awaited, HC-R004 when the code can provably return the host nothing while the card names no absence arm, or provably returns a value every time while the card names one, staying silent on a function whose answer passes through an expression it cannot resolve to present-or-absent (a subscript, a .get, an unfollowed call), HC-R005 when a body yields while the card returns a value and it is not a context manager, and HC-REF005 when the declared, defined and exported function sets do not resolve to each other or a declared parameter count disagrees (reading export_source for __all__, the empty bytes when --exports was absent and ignored by the other four rules, erroring when no literal __all__ is present); it returns the list<Diagnostic>, opens no file, executes no application code, and raises nothing

  Scenario: check_references
    Given sources: list<SourceFile> and format_vocabulary: FormatVocabulary | NOTHING
    When check_references is called
    Then it resolves cross-file references over the whole discovered set: HC-REF001 resolves each template hx-* action site against the route map the code's route_table() data declares, HC-REF002 resolves include/extends targets against the template set, HC-REF003 resolves static and scripted CSS classes against the union of defined class selectors, and HC-REF004 resolves authored hf-* values against format_vocabulary (the NOTHING arm stands HC-REF004 down, and an empty route map stands HC-REF001 down); a non-literal reference is traced to the closed source it ranges over and a trace reaching an unclosed source raises the alarm there rather than skipping; all four rules are error severity; it returns the list<Diagnostic>, opens no file, executes nothing, and raises nothing

  Scenario: check_roles
    Given sources: list<SourceFile> and declaration: Declaration | NOTHING
    When check_roles is called
    Then it runs the whole-program orphan rule HC-R001: a top-level function is roled when it carries a role decorator or the declaration names it; it builds the whole-program call graph, computes the functions reachable from the roled set, and emits one HC-R001 error for each top-level function that is neither roled nor reachable; when there are no roled functions at all (no role decorator anywhere and declaration is NOTHING) it emits nothing rather than flagging every function; it returns the list<Diagnostic> at error severity, opens no file, executes nothing, and raises nothing

  Scenario: check_auth
    Given sources: list<SourceFile>
    When check_auth is called
    Then it runs the two whole-program identity rules over the project's code as one set: a provider is registered when some file calls register_auth_provider and an authorizing link is a function decorated @link(authorizes=True); HC-A001 emits one warning when no provider is registered and the set holds at least one authorizing link, and HC-A002 emits one error per authorizing link whose body does not reference the boundary-resolved name actor when a provider is registered; the two are mutually exclusive over the set; it returns the list<Diagnostic> (HC-A001 warning, HC-A002 error), opens no file, executes nothing, and raises nothing

  # --- The CLI boundaries -------------------------------------------------------

  Scenario: discover_files
    Given paths: list<str> and exclude: list<str>
    When discover_files is called
    Then for each requested path it keeps a file whose extension honest-parse recognizes and that no exclude glob matches, recursively walks a directory keeping every such file, and filters out a directory, a nonexistent path and a file of an unrecognized extension, so every path that reaches read_source is a concrete recognized source file; it asks honest-parse whether each extension is recognized (it names no language itself) and returns the flat list; its one side effect is reading the file

  Scenario: resolve_project_config
    Given data: dict<str, any>
    When resolve_project_config is called
    Then it builds the [check] ProjectConfig from the parsed honest-check.toml table, resolving the exclude globs, the adoption level (the strictest 'Declared' when the key is absent or names no level the vocabulary carries), and the format_manifest path, and yields the default config for the empty table; it is pure

  Scenario: load_project_config
    Given no arguments
    When load_project_config is called
    Then it finds honest-check.toml in the nearest ancestor directory and hands back the raw parsed [check] table as data: whatever the file declared under [check], and the empty dict when there is no [check] section or no file; it takes no argument, builds no record of its own, and calls nothing, so the documented defaults (exclude the empty list, adoption 'Declared', format_manifest the empty string) are applied later by resolve_project_config off the boundary, not here; it is distinct from load_config which reads the [rules] table of the same file; its one side effect is reading the file

  Scenario: write_report
    Given text: str
    When write_report is called
    Then it prints the already-rendered report text to standard output and returns whether the write completed; it neither formats nor decides anything and calls nothing inward; its one side effect is writing stdout

  Scenario: read_fault
    Given reason: str
    When read_fault is called
    Then it builds honest-check's own {problem, remedy} Fault off the boundary from the raw read-failure reason read_declaration returned, filling problem (what went wrong, carried from the reason) and remedy (correct the --declaration path, or fix the declaration so honest-design can parse it); it is pure, reads nothing, raises nothing, and returns the one Fault run_check routes to the door, which discharges it as exit code 2

  Scenario: read_declaration
    Given hd_path: str
    When read_declaration is called
    Then it reads the named .hd file's text and parses it through honest-design's read_hd, returning the parsed Declaration on success and a raw read-failure reason (a plain str, never honest-check's Fault) when the .hd is missing or honest-design cannot parse it; run_check calls it only when CliArgs.declaration is non-empty; it does not check or construct the declaration shape; its one side effect is reading the file

  Scenario: read_format_manifest
    Given path: str
    When read_format_manifest is called
    Then it returns the NOTHING absence arm for an empty path, standing HC-REF004 down, and for a configured path reads honest-format's manifest.json and returns the FormatVocabulary it carries (each enumerated hf-* attribute mapped to its closed list of values); the spec states no fault for a configured path that cannot be read or does not parse, so it names none and answers NOTHING; it does not scan templates or scrape the client runtime; its one side effect is reading the file

  # --- The CLI orchestrator: one scenario per decision path ---------------------

  # hd: python/honest-check/honest-check.hd::run_check
  Scenario: run_check runs in base mode
    Given argv: list<str> whose CliArgs.declaration is the empty string (base mode)
    When run_check is called
    Then it parses the arguments, builds the ProjectConfig with load_project_config and resolve_project_config, and discovers the source files with discover_files; in base mode it builds the RuleConfig with load_config and resolve_rule_config, and for each discovered file reads it with read_source, builds the CheckContext with build_context, and runs check_source over it with the nearest enclosing module .hd (read through read_declaration, or NOTHING when the file lies under none) as the declaration; it then runs check_references once over the whole template/stylesheet/script/code set (paired through pair_source), check_roles once per module-.hd group of code files, and check_auth once over all code files as one set, folding every finding into one list; it prepares the findings with prepare_report, renders with the by_format dispatch, writes to stdout with write_report, and returns the ExitCode resolve_exit_code decides

  # hd: python/honest-check/honest-check.hd::run_check
  Scenario: run_check completes configured declaration crossing
    Given argv: list<str> whose CliArgs.declaration names an .hd that reads and parses (declaration-crossing mode)
    When run_check is called
    Then it parses the arguments, builds the ProjectConfig, and discovers the files; it pulls the one parsed module with read_declaration over CliArgs.declaration, reads the export module's text with read_source over CliArgs.exports when non-empty, reads each discovered file with read_source and pairs it through pair_source into a SourceFile, and runs cross_declaration once over the whole-package batch (crossing the one declaration against every file together, running only the crossing rules named in CliArgs.include_rules so HC-REF005 sees the entire defined-function set); it feeds the combined list into the same tail — prepare_report, by_format, write_report — and returns the ExitCode resolve_exit_code decides

  # hd: python/honest-check/honest-check.hd::run_check
  Scenario: run_check returns a fault when the configured declaration cannot be read
    Given argv: list<str> whose CliArgs.declaration names an .hd that is missing or does not parse (crossing-mode read failure)
    When run_check is called
    Then read_declaration answers a raw read-failure reason (a str, not a Fault), and run_check checks nothing over a declaration it could not open: it assembles honest-check's Fault from that reason through the pure read_fault off the boundary and routes that Fault straight outward as its ExitCode | Fault answer, which the door discharges as exit code 2

  # --- The CLI door -------------------------------------------------------------

  Scenario: main
    Given argv: list<str>
    When main is called
    Then it carries only I/O: it hands argv straight to run_check and turns run_check's answer into the process exit; on an ExitCode it exits the process with it (0 means success though warnings may have printed, 1 means the gate failed with errors at or below the declared adoption level); on the declaration-read Fault it discharges it at exit code 2, raising HonestCheckError carrying the Fault's problem and remedy rather than returning a clean code over a declaration it could not open; it raises HonestCheckError only on that declaration-read failure

  # --- The cross-module seam rules (HC-REF006, HC-REF007) -----------------------

  # hd: python/honest-check/honest-check.hd::_is_world
  # spec: HC-REF006, HC-REF007 and HC-REF012
  Scenario: _is_world identifies recognized world and resource targets
    Given target: str is "DOM", "HTTP", "file", "env:POOL_SIZE", "honest-persist", or ""
    When _is_world is called
    Then it returns true for the four world or resource targets and false for "honest-persist" and the empty target

  # hd: python/honest-check/honest-check.hd::_bare_seam
  # spec: HC-REF006, HC-REF007 and HC-REF012
  Scenario: _bare_seam keeps only a standalone bare module target
    Given caller: str is "save" and effect: SideEffect is a parsed writes effect without module or door information
    And the target is "", "file", "env:POOL_SIZE", "not a module", or "honest-persist"
    When _bare_seam is called
    Then it returns an empty list for the first four targets
    And for "honest-persist" it returns one Seam with caller "save", module "honest-persist", an empty door, and direction writes

  # hd: python/honest-check/honest-check.hd::_seam_of
  # spec: HC-REF006, HC-REF007 and HC-REF012
  Scenario: _seam_of preserves a qualified seam and skips an empty target
    Given caller: str is "save" and effect: SideEffect is a parsed reads_writes effect targeting "honest-persist.open", the bare module "honest-persist", or ""
    When _seam_of is called
    Then the qualified effect returns one Seam with caller "save", module "honest-persist", door "open" and direction reads_writes
    And the bare module returns the same record with an empty door, and the empty target returns an empty list

  # hd: python/honest-check/honest-check.hd::declared_seams
  Scenario: declared_seams
    Given module: Declaration is parsed without semantic validation and its first function "save" declares targets "", "DOM", and "honest-persist" in that order, and its second function "load" declares targets "env:POOL_SIZE" and "honest-parse.parse_source" in that order
    And "save" declares writes for the bare module and "load" declares reads for the qualified seam
    When declared_seams is called
    Then it returns, in order, one Seam for caller "save", module "honest-persist", empty door and direction writes, and one Seam for caller "load", module "honest-parse", door "parse_source" and direction reads
    And it returns an empty list when the module has only empty or world targets
    And it opens no file and does not certify side-effect validity

  Scenario: check_hc_ref006
    Given module: Declaration and declarations: dict<str, Declaration> and path: str
    When check_hc_ref006 is called
    Then it invokes declared_seams and, for each seam, skips a seam whose door is the empty string (that bare-module case is HC-REF008's) and a seam whose named module is not a key in declarations (not assumed absent, because a gate whose answer changes with how it was invoked is not a gate); for a seam whose named module is present but declares no function of the seam's door name it emits one HC-REF006 error naming the caller, the module and the door; path stamps each diagnostic's source_location; it reads nothing, returns one Diagnostic per dead seam at error severity, and raises nothing

  Scenario: check_hc_ref007
    Given module: Declaration and declarations: dict<str, Declaration> and path: str
    When check_hc_ref007 is called
    Then it invokes declared_seams and applies the same two skips as HC-REF006 (door the empty string, named module not in declarations); for a seam whose named module declares a function of the door name but whose role is not boundary_in it emits one HC-REF007 error naming the caller, the module, the door and the role the module gave that door; path stamps each diagnostic's source_location; it reads nothing, returns one Diagnostic per such seam at error severity, and raises nothing

  Scenario: run_seam_rules
    Given declarations: dict<str, Declaration> and paths: dict<str, str> and manifest_deps: dict<str, list<str>> and in_scope: list<str>
    When run_seam_rules is called
    Then for each module named in in_scope (or every loaded module when in_scope is empty) it runs check_hc_ref006, check_hc_ref007 and check_ref012 over that module's declaration, the whole declarations map and the module's .hd path, handing check_ref012 the module's manifest_deps entry (the empty list when absent) and the workspace module names, concatenating their diagnostics in that order across every in-scope module; it resolves each in-scope module's seams against the complete declarations map, not the in-scope subset, so the gate's verdict on a module is the same whether a commit staged one module or swept the framework; it reads nothing, opens no file, returns the flat combined list<Diagnostic>, and raises nothing

  # hd: python/honest-check/honest-check.hd::run_seam_rules
  Scenario: run_seam_rules checks scoped pure calls alongside I/O seams
    Given declarations: dict<str, Declaration> includes an in-scope caller with one pure call to a valid target, one pure call to a known target that fails the pure-role requirement, and an I/O seam to a missing door
    And all target modules are outside the reporting scope and present in declarations
    And paths: dict<str, str> gives the declaration paths, manifest_deps: dict<str, list<str>> names both pure-call targets' modules as dependencies of the caller, and in_scope: list<str> names only the caller
    When run_seam_rules is called
    Then it reports HC-REF007 for the invalid pure target and HC-REF012 for that dependency
    And it reports no HC-REF012 for the dependency with a resolved pure call
    And it reports HC-REF006 for the I/O seam to the missing door

  # hd: python/honest-check/honest-check.hd::resolve_pure_calls
  Scenario: resolve_pure_calls preserves resolved occurrences in declaration order
    Given module: Declaration has a reader declaring "utils.answer", "utils.other" and "utils.answer" in that order followed by a function without pure_calls, and declarations: dict<str, Declaration> includes the boundaryless utils module whose answer and other functions are plain fn with no side effects
    When resolve_pure_calls is called
    Then it returns the three occurrences in order with the reader as caller, utils as module, and status resolved

  # hd: python/honest-check/honest-check.hd::resolve_pure_calls
  Scenario: resolve_pure_calls returns unresolved for malformed targets
    Given module: Declaration contains a function declaring the unqualified pure_call target "answer", and declarations: dict<str, Declaration> holds the loaded declarations
    When resolve_pure_calls is called
    Then it returns one resolution with the authored target "answer", an empty module name and status unresolved

  # hd: python/honest-check/honest-check.hd::resolve_pure_calls
  Scenario: resolve_pure_calls returns unresolved for missing targets
    Given module: Declaration named consumer contains a function declaring "absent.answer", "utils.unknown" and "consumer.answer", and declarations: dict<str, Declaration> contains utils with no function named unknown and consumer with answer but no module named absent
    When resolve_pure_calls is called
    Then it returns unresolved for all three occurrences in annotation order, preserving each authored target and parsed module name

  # hd: python/honest-check/honest-check.hd::resolve_pure_calls
  Scenario: resolve_pure_calls returns invalid_role for impure targets
    Given module: Declaration contains a function declaring separate pure calls to a known boundary role, a plain fn declaring a side effect, and a side-effect-free plain fn in a module with a boundary, and declarations: dict<str, Declaration> includes those target modules and functions
    When resolve_pure_calls is called
    Then it returns invalid_role for each occurrence in annotation order

  # hd: python/honest-check/honest-check.hd::pure_call_findings
  Scenario: pure_call_findings reports ordered errors at the caller declaration path
    Given calls: list<PureCallResolution> contains an invalid_role occurrence by caller "load" for "world.read", a resolved occurrence, and an unresolved occurrence by caller "build" for "absent.answer", and path: str is "consumer.hd"
    When pure_call_findings is called
    Then it returns two errors at "consumer.hd" in order, first HC-REF007 naming "load" and "world.read", then HC-REF006 naming "build" and "absent.answer"

  Scenario: check_seams
    Given declarations: dict<str, Declaration> and paths: dict<str, str> and manifest_deps: dict<str, list<str>> and in_scope: list<str>
    When check_seams is called
    Then it is the single door the honest-pre-commit dogfood gate reaches into the cross-module seam checks: it hands its four inputs straight to run_seam_rules and returns the combined diagnostic list, holding no resolution logic itself; the declarations arrive already parsed, so it opens no file; it returns the flat list of every HC-REF006, HC-REF007 and HC-REF012 Diagnostic over the in-scope modules (resolved against every declaration) and raises nothing

  # hd: python/honest-check/honest-check.hd::distribution_pure_dependencies
  Scenario: distribution_pure_dependencies includes only resolved calls from the caller distribution
    Given module_name: str names the manifest owner, paths: dict<str, str> puts the owner and a sibling logical module in the same manifest directory and another logical module outside it, and calls_by_module: dict<str, list<PureCallResolution>> gives the owner a resolved call to "utils", the sibling a resolved call to "math" and failed calls to "missing" and "world", and the other logical module a resolved call to "external"
    When distribution_pure_dependencies is called
    Then it returns the set containing only "utils" and "math"

  # hd: python/honest-check/honest-check.hd::check_seams
  Scenario: check_seams accepts a resolved pure call as manifest dependency evidence
    Given declarations: dict<str, Declaration> includes a manifest owner and its sibling logical module with a resolved pure call to a boundaryless dependency outside the reporting scope, paths: dict<str, str> puts the owner and sibling in the same manifest directory, manifest_deps: dict<str, list<str>> lists the dependency for the owner, and in_scope: list<str> names only the owner
    When check_seams is called
    Then it reports no HC-REF012 diagnostic for that dependency even without an I/O seam to it

  # hd: python/honest-check/honest-check.hd::check_seams
  Scenario: check_seams rejects a failed pure call as manifest dependency evidence
    Given declarations: dict<str, Declaration> includes a caller with a pure call to a known target that fails the pure-role requirement and no seam to that dependency, paths: dict<str, str> supplies each declaration path, manifest_deps: dict<str, list<str>> names the dependency for the caller, and in_scope: list<str> includes the caller
    When check_seams is called
    Then it reports HC-REF007 for the invalid target and HC-REF012 for the dependency without valid evidence

  Scenario: check_ref012
    Given module: Declaration and manifest_deps: list<str> and workspace_module_names: list<str> and path: str
    When check_ref012 is called
    Then it invokes declared_seams to collect the modules this declaration already names a cross-module seam onto (the module field of each Seam), then for each dependency in manifest_deps it skips one outside workspace_module_names (an external package, no seam to hold it to) and emits one HC-REF012 error for a workspace dependency the declaration names no seam onto, so a packaging import that otherwise lives only in Python is forced onto the record; it reads nothing, opens no file, returns the list<Diagnostic> of HC-REF012 errors (empty when every workspace dependency is already a declared seam), and raises nothing

  # --- The shared extraction API (exported for honest-test) ---------------------

  Scenario: resolve_aliases
    Given root: Node and source: bytes
    When resolve_aliases is called
    Then it reads every import statement off the parsed tree and returns the map from each local name an honest-framework import bound to that import's canonical framework name (a direct alias maps v -> vocabulary, a module alias maps ht.* -> honest_type.*); build_context calls it from inside the core to seed each CheckContext's alias map, and nothing outside honest-check imports it; it opens no file, executes none of the code it reads, returns the empty map when nothing framework is imported, and raises nothing

  # --- The shared AST helper layer ----------------------------------------------

  Scenario: diagnostic
    Given ctx: CheckContext and rule_id: str and severity: str and message: str and node: Node
    When diagnostic is called
    Then it returns one Diagnostic assembled the one way every rule shares: it fills rule_id, severity and message from its arguments, derives source_location as file:line:col from node's byte span within ctx (the path from ctx, the line and column from the span over ctx's source bytes), quotes context verbatim from that line and leaves it the empty string when the finding has no single line to quote, and sets fixable from whether rule_id names a rule in honest-check's conservative auto-fix subset; it reads nothing and raises nothing, since a violation is data, not an exception

  Scenario: literal_string
    Given node: Node
    When literal_string is called
    Then it returns the Python string a `string` node spells, with its quotes stripped

  Scenario: string_members
    Given ctx: CheckContext and node: Node
    When string_members is called
    Then it returns the string values a set, list or tuple node holds, in source order

  Scenario: call_arguments
    Given ctx: CheckContext and call_node: Node
    When call_arguments is called
    Then it returns the positional nodes and the keyword-name-to-value-node map of a call

  Scenario: canonical_name
    Given ctx: CheckContext and call_node: Node
    When canonical_name is called
    Then it returns the framework constructor name a call resolves to (a direct constructor-name call, or an aliased one resolved through the import), or NOTHING when the call is not a framework constructor

  Scenario: base_types_of
    Given ctx: CheckContext and dictionary_node: Node
    When base_types_of is called
    Then it returns the base-type map of a vocabulary's first argument, each name mapped to a (kind, payload) where kind is 'set' with a frozenset of members or 'predicate' with the recognizer's value node (an opaque recognizer honest-check cannot run), serving HC009

  Scenario: predicate_is_risky
    Given value: Node
    When predicate_is_risky is called
    Then it returns true when a predicate's expression holds a node that throws on a non-matching input — a call to bare `int` or `float`, a subscript access, or a `/` or `//` division — because a predicate that throws is a recognizer that rejects by exception (HC009)

  Scenario: enclosing_function
    Given node: Node
    When enclosing_function is called
    Then it returns the nearest enclosing function_definition of the node, climbing parents, or NOTHING at module scope

  Scenario: underscore_self_name
    Given target: Node
    When underscore_self_name is called
    Then it returns the attribute name of a `self._name` assignment target whose name starts with an underscore, or NOTHING when the target is not that shape (HC-P007)

  Scenario: called_name
    Given ctx: CheckContext and call_node: Node
    When called_name is called
    Then it returns the name a call invokes — a bare identifier, or the final attribute of a dotted call such as window.addEventListener — or NOTHING (HC-P011)

  # hd: python/honest-check/honest-check.hd::called_name
  # spec: HC-P011
  Scenario: called_name returns the final name of a qualified JavaScript call
    Given ctx: CheckContext for JavaScript source and call_node: Node for view.componentDidMount()
    When called_name is called
    Then it returns "componentDidMount"

  Scenario: own_body
    Given fdef: Node
    When own_body is called
    Then it returns the body descendants belonging to the function itself, not descending into a deeper nested def, lambda or decorated def, whose statements are the inner scope's own

  # hd: python/honest-check/honest-check.hd::own_body
  # spec: HC008
  Scenario: own_body includes expression roots and excludes nested JavaScript bodies
    Given fdef: Node is an inline JavaScript arrow with an expression body Math.random(), or a function expression with a block returning process.env and a nested function returning document.cookie
    When own_body is called
    Then the arrow result includes its Math.random() call node itself
    And the block result includes its own return of process.env and excludes the nested return and document.cookie read

  # hd: python/honest-check/honest-check.hd::_descend
  # spec: HC008
  Scenario: _descend retains JavaScript scope nodes without visiting their bodies
    Given node: Node is a JavaScript block containing a direct statement, a nested function declaration with a distinct read in its body, and another direct statement, in that order
    When _descend is called
    Then it returns named descendants in source order including both direct statements and the nested function boundary node
    And it omits the nested function descendants, including its read

  Scenario: nonlocal_names
    Given statements: list<Node>
    When nonlocal_names is called
    Then it returns the names declared by the `nonlocal` statements directly in a function body

  Scenario: decorators_of
    Given ctx: CheckContext and fdef: Node
    When decorators_of is called
    Then it returns the decorator nodes applied to a function — the decorator children of the enclosing decorated_definition — or the empty list for an undecorated function, the boundary signal HC-P002/HC-P004/HC-P005 and the cache signal HC-P006 read

  Scenario: decorator_expression
    Given decorator: Node
    When decorator_expression is called
    Then it returns the expression a decorator applies — the identifier, attribute or call after the `@` — which a parsed decorator always carries as its first named child

  Scenario: decorator_target
    Given decorator: Node
    When decorator_target is called
    Then it returns the final name a decorator names — `boundary` from @boundary, `lru_cache` from @functools.lru_cache(maxsize=1) — or NOTHING when it is neither a plain nor a dotted name

  Scenario: is_boundary_decorator
    Given ctx: CheckContext and decorator: Node
    When is_boundary_decorator is called
    Then it returns true when a decorator declares its function a boundary — @boundary (bare or called) or @link(boundary=True)

  Scenario: in_non_boundary_function
    Given ctx: CheckContext and node: Node
    When in_non_boundary_function is called
    Then it returns true when a node's nearest enclosing function exists, carries no boundary decorator, and the declaration gives its name no door role — the scope HC-P002, HC-P004 and HC-P005 fire in — and false at module scope or inside a boundary function

  Scenario: is_immutable_value
    Given value: Node
    When is_immutable_value is called
    Then it returns true when a module-level binding's right side is provably immutable — a number, a string, a bool, None, a tuple literal, a negated immutable, or a frozenset(...) call — and false for everything else (a list, dict or set literal, a comprehension, and so on)

  Scenario: module_mutable_globals
    Given ctx: CheckContext
    When module_mutable_globals is called
    Then it returns the module-level names bound to a mutable (or not provably immutable) value, the globals a read of which makes a link impure; a name bound to an immutable value and an imported or def/class name are not included (HC008)

  Scenario: param_names
    Given param: Node
    When param_names is called
    Then it returns the names a single parameter node binds — a bare identifier, or the name of a typed or defaulted parameter — binding nothing for a splat or other shape

  Scenario: link_locals
    Given fdef: Node and body: list<Node>
    When link_locals is called
    Then it returns the names local to a link — its parameters plus the names it assigns in its own body — so a read of one of these is not a read of a module global (HC008)

  Scenario: is_attribute_suffix
    Given node: Node
    When is_attribute_suffix is called
    Then it returns true when an identifier is the attribute part of an `x.name` access, because reading config.timeout reads config, not a global called timeout (HC008)

  Scenario: is_keyword_name
    Given node: Node
    When is_keyword_name is called
    Then it returns true when an identifier is a keyword argument's name — the `k` in f(k=v) — which names a parameter of the callee, not a global read (HC008)

  # hd: python/honest-check/honest-check.hd::watched
  Scenario: watched
    Given target: Node and watch: set<str>
    When watched is called
    Then it returns true when the bare or dotted spelling of a call target or supplied read reference is on the watch list — an exact entry matches by equality and an entry carrying a `*` matches as a glob (a trailing `.*` names any attribute of a module, a trailing `*` is a prefix, a `*` between dots is one segment)
    And a supplied os.environ attribute matches an exact os.environ entry, a supplied __file__ identifier matches __file__, and the unqualified identifier environ does not match os.environ

  # hd: python/honest-check/honest-check.hd::watched
  # spec: HC008
  Scenario: watched resolves static JavaScript member names independent of spacing
    Given target: Node is Math.random, Math . random, Math["random"], or makeMath().random, and watch: set<str> contains only "Math.random"
    When watched is called
    Then it returns true for the first two references and false for the computed member and the call-result receiver

  # hd: python/honest-check/honest-check.hd::watched
  Scenario: watched matches static Ruby methods and Go selectors
    Given target: Node is parsed from a Ruby File.read or IO.read call or a Go os.Open or ioutil.ReadFile selector, with the corresponding spelling on watch: set<str>
    When watched is called
    Then each target matches its own spelling
    And a differently named receiver or operand does not match that spelling
    And a Ruby static receiver spelling containing a namespace separator retains that separator for matching

  # hd: python/honest-check/honest-check.hd::_call_target_watched
  Scenario: _call_target_watched matches only supported static operation heads
    Given ctx: CheckContext and call: Node for each matching static head, using Python os.open, JavaScript fetch and direct new XMLHttpRequest(), Ruby File.read and IO.read, and Go os.Open and ioutil.ReadFile
    And watch: set<str> contains the corresponding static spellings
    When _call_target_watched is called
    Then each listed operation matches
    And a JavaScript computed member or a member on a call result does not match the corresponding static spelling
    And an operation with a different static head and a constructor with a different name do not match the supplied spellings

  # hd: python/honest-check/honest-check.hd::_hc_p004
  Scenario: _hc_p004 reports watched operations in named non-boundary host functions
    Given ctx: CheckContext parses JavaScript named function declarations calling fetch and members of localStorage and sessionStorage or directly constructing XMLHttpRequest
    And Ruby named methods and singleton methods call File.read and IO.read, and Go named functions and methods call os.Open and ioutil.ReadFile
    And each language also has a non-watched call inside a named function and a watched operation outside a named callable
    When _hc_p004 is called for each context
    Then it returns one HC-P004 error at each watched operation in a named non-boundary function
    And neither the non-watched calls nor the operations outside named callables produce HC-P004 errors

  # hd: python/honest-check/honest-check.hd::_hc_p004
  Scenario: _hc_p004 uses the nearest owner and its own boundary evidence
    Given ctx: CheckContext contains a JavaScript named function declaration with a // honest: boundary comment immediately above it, and a separate named function declaration with the comment on its declaration line
    And each contains a watched operation and an unmarked nested named function with another watched operation
    And other cases contain a watched operation in a recognized named JavaScript, Ruby or Go function with a same-name companion declaration role of boundary_in, boundary_out or reader
    And a separate JavaScript function containing a watched operation has the comment separated from its declaration by a blank line
    When _hc_p004 is called for each context
    Then the only HC-P004 errors occur at the watched operations in the unmarked nested functions and in the function separated from its comment by a blank line

  # hd: python/honest-check/honest-check.hd::check_per_file
  Scenario: check_per_file reports HC-P004 for named JavaScript Ruby and Go functions
    Given ctx: CheckContext parses a named non-boundary function calling fetch in JavaScript, File.read in Ruby, or os.Open in Go
    And the same operation also appears inside a recognized same-name host function whose companion declaration marks it as a boundary
    When check_per_file is called for each context
    Then its HC-P004 findings contain one error at the watched call in the non-boundary function and none at the call in the declared boundary

  Scenario: is_main_guard
    Given ctx: CheckContext and node: Node
    When is_main_guard is called
    Then it returns true when an `if` node is exactly the script guard `if __name__ == "__main__"` — the one `if` HC-P001 exempts — reading the condition only to recognize this guard; an elif_clause is never the guard and any other `if` fires on the keyword alone

  Scenario: within_class_init
    Given ctx: CheckContext and node: Node
    When within_class_init is called
    Then it returns true when a node's nearest enclosing function is an `__init__` that is a method of a class — the scope HC-P007 reads for hidden instance state

  Scenario: mutated_names
    Given ctx: CheckContext and statements: list<Node>
    When mutated_names is called
    Then it returns the names an assignment or augmented assignment targets directly in a function body — the left of each `x = ...` or `x += ...` whose target is a plain identifier

  Scenario: is_empty_default
    Given ctx: CheckContext and value: Node
    When is_empty_default is called
    Then it returns true when a parameter's default stands for absence rather than a baked-in value — None, False, a zero number, an empty string, an empty list/dict/tuple literal, or an empty-constructor call — and false for a populated literal or a non-zero number (HC-P015)

  # hd: python/honest-check/honest-check.hd::_number_is_zero
  # spec: HC-P015
  Scenario: _number_is_zero recognizes zero by literal value and syntax
    Given value: Node is the parsed Python expression for each case
    When _number_is_zero is called
    Then it returns true for `0`, `0_0`, `0x0`, `0O_0`, `0B_0`, `0.0`, `0e3`, `0J`, `(-0x0)`, and `((+0.0))`
    And it returns false for `0x1`, `0o7`, `0b10`, `1e-3`, `1j`, `-(1)`, `(+0.5)`, `~0`, `0 + 0`, `zero`, and `make_zero()`
    And it inspects each expression without evaluating it

  # hd: python/honest-check/honest-check.hd::is_empty_default
  # spec: HC-P015
  Scenario: is_empty_default accepts zero spellings and rejects nonzero defaults
    Given ctx: CheckContext is for Python and value: Node is a default expression for 0x0, 0O_0, 0B_0, 0_0, 0.0, 0e3, 0j, (-0), (+0.0), 0x2, -1.5, or 1j
    When is_empty_default is called
    Then the zero spellings including the signed and parenthesized zeros return true, and each nonzero default returns false

  Scenario: dotted_target
    Given ctx: CheckContext and call_node: Node
    When dotted_target is called
    Then it returns the dotted name a call invokes — `open`, `os.system`, `requests.get`, `urllib.request.urlopen` — or NOTHING when the target is not a plain or dotted name, such as a call on a call's result (HC008)

  # hd: python/honest-check/honest-check.hd::link_is_impure
  Scenario: link_is_impure
    Given ctx: CheckContext and fdef: Node and watch: set<str> and mutable_globals: set<str>
    When link_is_impure is called
    Then it returns true when a link's own body calls a watched function or reads a module-level mutable global, the body search not descending into a nested def or lambda (HC008)
    And with the corresponding watch entries and no file-local mutable globals, its own body reads of os.environ, sys.argv, sys.version, sys.path, __file__ or __name__ each make the link impure, including sys.argv as the base of sys.argv[0]
    And string text, an attribute suffix alone, a name used only as a write target, and reads confined to a nested def or lambda do not make the link impure

  # hd: python/honest-check/honest-check.hd::link_is_impure
  # spec: HC008
  Scenario: link_is_impure detects watched JavaScript calls and value reads
    Given ctx: CheckContext is for JavaScript, fdef: Node is an inline link callback, watch: set<str> contains "Math.random", "process.env", "process.argv" and "document.cookie", and mutable_globals: set<str> is empty
    And independent callback bodies call Math.random(), read process.env, read process.argv, read document.cookie, assign document.cookie without reading it, read the suffix env through another receiver, contain the string "process.env", or contain a nested callback whose body alone reads process.env
    When link_is_impure is called
    Then it returns true for the direct member call and the three own-body value reads
    And it returns false for the write-only target, unrelated suffix, string and nested callback cases

  Scenario: has_decorator
    Given ctx: CheckContext and fdef: Node and name: str
    When has_decorator is called
    Then it returns true when a function carries a decorator whose target is `name`, bare or called — the @link HC008 and HC001 read, or the @orchestrator HC-OR001 and HC-OR003 read

  Scenario: local_function_links
    Given ctx: CheckContext
    When local_function_links is called
    Then it returns each function defined in this file mapped to whether it carries a @link decorator, so a chain positional resolving to one of these names is a local link declaration honest-check can read (HC001)

  Scenario: canonical_body
    Given fdef: Node
    When canonical_body is called
    Then it returns a function body's structural signature with every literal value blanked — each body node reduced to its grammar type, except an identifier which keeps its name — so two bodies match when they differ only in the constants they name (HC-P014)

  Scenario: body_has_call
    Given fdef: Node
    When body_has_call is called
    Then it returns true when a function's own body contains a call, the mark of behaviour worth sharing, because a body with no call carries no logic two functions could collapse into one (HC-P014)

  Scenario: body_statement_count
    Given fdef: Node
    When body_statement_count is called
    Then it returns the count of statements in a function's own body, not descending into nested scopes, the threshold that keeps a two-member group from firing on a trivial shared shape (HC-P014)

  Scenario: persist_write_targets
    Given ctx: CheckContext
    When persist_write_targets is called
    Then it returns the dotted call targets that resolve to a honest-persist database writer through this file's own imports (HC-ST001)

  Scenario: dom_collect_names
    Given ctx: CheckContext
    When dom_collect_names is called
    Then it returns the local names this JavaScript file binds to honest-dom's `collect` through its own imports, the empty result when the file imports `collect` from no honest-dom module, which stands HC-ST002 down

  Scenario: value_calls_collect
    Given value_node: Node and collect_names: any
    When value_calls_collect is called
    Then it returns true when a bound value calls one of the resolved `collect` names anywhere inside it (HC-ST002)

  Scenario: longest_shared_run
    Given ctx: CheckContext and calls_a: list<str> and calls_b: list<str>
    When longest_shared_run is called
    Then it returns the length of the longest run of consecutive equivalent call names two call sequences share — a contiguous common substring over the two lists found by the standard row-by-row dynamic program — and 0 when they share no adjacent run (HC-OR003)

  # hd: python/honest-check/honest-check.hd::longest_shared_run
  # spec: HC-OR003 (as cited by the declaration)
  Scenario: longest_shared_run counts only consecutive matches across both sequences
    Given ctx: CheckContext and each pair of calls_a: list<str> and calls_b: list<str> below
    When longest_shared_run is called
    Then it returns 0 for `[]` and `["a"]`, for `["a"]` and `[]`, and for `["a", "b"]` and `["x", "y"]`
    And it returns 1 for `["a"]` and `["a"]`
    And it returns 2 for `["a", "b", "c"]` and `["x", "a", "b"]`, for those two lists in the opposite order, and for `["a", "b", "gap", "c"]` and `["a", "b", "c"]`
    And it returns 3 for `["r", "gap", "r", "r", "s"]` and `["r", "r", "other", "r", "r", "s"]`
    And it counts only consecutive matches, starting a new run after a mismatch

  Scenario: link_declares_emits
    Given ctx: CheckContext and fdef: Node
    When link_declares_emits is called
    Then it returns true when a function carries a @link decorator that passes an `emits` keyword — the emits vocabulary HC-P017 requires of an HTTP-producing link — read from the decorator call the way is_boundary_decorator reads `boundary`

  Scenario: construction_maps
    Given ctx: CheckContext
    When construction_maps is called
    Then it returns each file-local variable bound to a vocabulary(...) or a binding(...) call, mapped to that construction call node; a name bound to anything else, or one honest-check cannot resolve to those two constructors, is not included (HC004, HC005)

  Scenario: features_vocabulary
    Given ctx: CheckContext
    When features_vocabulary is called
    Then it returns the feature-flag vocabulary this module declares — each flag name mapped to the set of states its FEATURES[flag]["states"] set names — read only from a module-scope FEATURES dict literal (HC-HF001, HC-HF002)
    And both a readable empty FEATURES literal and no readable local FEATURES literal return an empty map

  Scenario: feature_state_flag
    Given ctx: CheckContext and call_node: Node
    When feature_state_flag is called
    Then it returns the flag a feature_state(state, "flag") call names — its second positional string literal — or NOTHING when the call names fewer than two positionals or a dynamic (non-literal) flag, the call resolved by name through called_name (HC-HF rules)

  Scenario: module_dict_literals
    Given ctx: CheckContext
    When module_dict_literals is called
    Then it returns each module-scope name bound to a dict literal, mapped to the set of string keys the literal declares; a name bound to anything but a module-scope dict literal is not included (HC-HF002)

  # hd: python/honest-check/honest-check.hd::module_dict_literals
  Scenario: module_dict_literals distinguishes an empty FEATURES literal from an unreadable binding
    Given ctx: CheckContext is for source with FEATURES = {}, no FEATURES binding, or FEATURES assigned a call result
    When module_dict_literals is called
    Then the returned map contains FEATURES mapped to an empty set for the literal, and contains no FEATURES key in the other cases

  # hd: python/honest-check/honest-check.hd::_value_names
  Scenario: _value_names reads an optional capture base name
    Given ctx: CheckContext resolves maybe imported by from honest_type import maybe to the Honest Type constructor, and node: Node | NOTHING is "Part", maybe("Part"), maybe(dynamic_name), unrelated.maybe("Part"), or NOTHING
    When _value_names is called
    Then it returns the singleton set containing "Part" for the literal and its canonical optional form, and an empty set for the dynamic, unrelated qualified or absent case

  Scenario: vocabulary_types
    Given ctx: CheckContext and vocab_call: Node
    When vocabulary_types is called
    Then it returns the type surface of a vocabulary(...) call — its base-type names, its composed-type names, the base names its composed types require, and the base names its composed types capture — reading the first-argument dictionary through base_types_of (HC004, HC005)

  # hd: python/honest-check/honest-check.hd::vocabulary_types
  Scenario: vocabulary_types preserves composed names from positional declarations
    Given ctx: CheckContext and vocab_call: Node for a vocabulary declaring base type "Part" and composed type "Combined" in its second positional argument
    When vocabulary_types is called
    Then it returns base_names containing "Part" and composed_type_names containing "Combined"

  # hd: python/honest-check/honest-check.hd::vocabulary_types
  Scenario: vocabulary_types preserves composed names from keyword declarations
    Given ctx: CheckContext and vocab_call: Node for a vocabulary declaring base type "Part" and composed type "Combined" in its composed_types keyword argument
    When vocabulary_types is called
    Then it returns base_names containing "Part" and composed_type_names containing "Combined"

  # hd: python/honest-check/honest-check.hd::vocabulary_types
  Scenario: vocabulary_types returns empty composed fields when declarations are omitted
    Given ctx: CheckContext and vocab_call: Node for a vocabulary declaring base type "Part" with no composed declarations
    When vocabulary_types is called
    Then it returns base_names containing "Part" and empty composed_type_names and composed

  # hd: python/honest-check/honest-check.hd::vocabulary_types
  Scenario: vocabulary_types preserves the base name inside an optional capture
    Given ctx: CheckContext contains a vocabulary with one composed type named by the literal "Combined" and a second with a dynamic name argument, both capturing maybe("Part") imported from Honest Type, and vocab_call: Node is that vocabulary call
    When vocabulary_types is called
    Then each composed declaration contains "Part" in captures_bases
    And the first declaration carries its own "Combined" literal Node in name_node and the second carries NOTHING

  Scenario: binding_keys
    Given ctx: CheckContext and binding_call: Node
    When binding_keys is called
    Then it returns the type names a binding(...) call binds — the keys of its first-argument table (HC004, HC005)

  Scenario: vocabulary_binding_pairs
    Given ctx: CheckContext
    When vocabulary_binding_pairs is called
    Then it returns each (vocabulary calls, binding call) a classify or link pairs by name: a classify(tokens, vocab, bind=b) pairs positional 2 with the `bind` keyword with the one vocab as its vocabulary list, and a link(accepts=v, emits=e, bind=b) pairs by its keywords (HC004, HC005)

  # --- The two rule sub-cores and the suppression pass --------------------------

  # hd: python/honest-check/honest-check.hd::_links
  # spec: HC008
  Scenario: _links selects direct top-level JavaScript link callbacks
    Given ctx: CheckContext contains program-scope const initializers link({}, () => Math.random()) and link({accepts: V}, function () { return process.env; })
    And separate controls use a bare function declaration, lib.link, a referenced callback, a nested wrapper, a nonliteral options expression or literal options with an explicit boundary property
    When _links is called
    Then it returns only the two inline callbacks with statically readable metadata that omits boundary, including the expression and block bodies

  # hd: python/honest-check/honest-check.hd::check_construction
  Scenario: check_construction
    Given ctx: CheckContext
    When check_construction is called
    Then it runs the construction-time rules — HC001, HC003, HC006, HC007, HC011 and the state-machine rules HC-SM01, HC-SM02, HC-SM05 — dispatched by the framework constructor each call site resolves to, reaching the shared vocabulary-and-binding helper layer (canonical_name, call_arguments, string_members, literal_string, base_types_of, vocabulary_types, binding_keys, construction_maps, vocabulary_binding_pairs) and building each finding with diagnostic; the per-rule logic nests here as data, it returns the construction-time findings, and it raises nothing
    And for a recognized non-boundary Python link whose only impurity is reading a name on the Python watch list it returns one HC008 warning for the link
    And a boundary link with the same watched read contributes no HC008 warning

  # hd: python/honest-check/honest-check.hd::check_construction
  # spec: HC008
  Scenario: check_construction anchors JavaScript HC008 warnings to inline callbacks
    Given ctx: CheckContext contains separate program-scope const direct links with static options omitting boundary and inline callbacks, one an arrow expression that calls Math.random() and another a function block that reads process.env
    And other controls are an explicit boundary wrapper with the same watched call, a direct link whose only such read is nested, and a direct link without watched behavior
    When check_construction is called
    Then it returns exactly one HC008 warning anchored to each of the two impure inline callbacks and no HC008 warning for the controls

  # hd: python/honest-check/honest-check.hd::check_construction
  # spec: HC008, Honest Check §4.2
  Scenario: check_construction warns for published JavaScript watch-list calls
    Given ctx: CheckContext is for JavaScript source with a separate program-scope declaration `const name = link({}, () => expression)` for each call below
    And the calls include `fs.readFile()`, `fsp.readFile()`, `fetch()`, `http.request()`, `https.request()`, and `navigator.sendBeacon()`
    And the calls include `localStorage.getItem()`, `sessionStorage.setItem()`, `indexedDB.open()`, and `caches.open()`
    And the calls include `process.stdout.write()`, `process.stderr.write()`, `process.stdin.read()`, `console.log()`, `console.error()`, `console.warn()`, `console.info()`, and `console.debug()`
    And the calls include `pg.query()`, `mongodb.connect()`, `redis.createClient()`, `mysql.createConnection()`, and `sqlite3.open()`
    And the calls include `Math.random()`, `crypto.getRandomValues()`, `crypto.randomUUID()`, `Date.now()`, `performance.now()`, and `process.cwd()`
    When check_construction is called
    Then it returns one HC008 warning anchored to each watched inline callback

  # hd: python/honest-check/honest-check.hd::check_construction
  Scenario: check_construction checks optional capture base names with HC006
    Given ctx: CheckContext contains composed types named "First" and "Second" on different source lines, both capturing maybe("Part") imported from Honest Type, in a vocabulary that either declares "Part" as a base type or omits it
    When check_construction is called
    Then there is no HC006 error for the declared base
    And the missing base produces two HC006 errors naming the unknown captured base "Part", one at the "First" literal name node and one at the "Second" literal name node

  # hd: python/honest-check/honest-check.hd::_hc_p003
  # spec: HC-P003, §5.3
  Scenario: _hc_p003 reports implicit object inheritance when no actual Python base is declared
    Given ctx: CheckContext parses four Python classes with no base list, an empty base list, only metaclass=ABCMeta, and only a keyword dictionary expansion
    When _hc_p003 is called
    Then it returns one HC-P003 error at each class declaration in source order
    And each error identifies the absence of a declared base

  # hd: python/honest-check/honest-check.hd::_hc_p003
  # spec: HC-P003, §5.3
  Scenario: _hc_p003 accepts the four approved direct Python bases
    Given ctx: CheckContext parses separate Python classes directly inheriting TypedDict, Protocol, ABC, and Exception
    And a fifth class directly inherits ABC and supplies metaclass=ABCMeta and a keyword dictionary expansion
    When _hc_p003 is called
    Then it returns no HC-P003 error

  # hd: python/honest-check/honest-check.hd::_hc_p003
  # spec: HC-P003, §5.3
  Scenario: _hc_p003 reports each disallowed direct Python base in source order
    Given ctx: CheckContext parses a Python class with direct bases TypedDict, NamedTuple, and Enum in that order
    And a following class has direct bases ABCMeta and Exception in that order
    When _hc_p003 is called
    Then it returns two HC-P003 errors at the first class declaration naming NamedTuple and Enum in that order
    And it returns one HC-P003 error at the second class declaration naming ABCMeta

  # hd: python/honest-check/honest-check.hd::_hc_p003
  # spec: HC-P003, §5.3
  Scenario: _hc_p003 preserves class-level fallback for disputed and unresolved Python bases
    Given ctx: CheckContext parses four Python classes whose base lists, in source order, are (BaseException), (typing.Protocol), (Protocol, BaseException), and (Protocol, typing.Protocol)
    When _hc_p003 is called
    Then it returns exactly two HC-P003 errors in source order, one anchored to each of the first two class declarations
    And it returns no HC-P003 finding for either class with the approved direct Protocol sibling

  Scenario: check_per_file
    Given ctx: CheckContext
    When check_per_file is called
    Then it runs the static per-file rules — the HC-P purity rules including HC-P014, the chain and link rules HC009, HC010, HC004 and HC005, the per-file state rules HC-ST001 and HC-ST002, and the HC-HF feature-flag rules — folded over the declaration graph, reaching the shared AST helper layer (the scope, decorator, impurity, state and feature helpers) and building each finding with diagnostic; the per-rule logic nests here as data, it returns the per-file findings, and it raises nothing

  # hd: python/honest-check/honest-check.hd::check_per_file
  # spec: HC-P003, §5.3
  Scenario: check_per_file reports a disallowed Python base alongside an approved base
    Given ctx: CheckContext parses a Python class with direct bases Protocol and Enum and metaclass=ABCMeta
    When check_per_file is called
    Then its HC-P003 findings contain exactly one error at the class declaration naming Enum

  # hd: python/honest-check/honest-check.hd::check_per_file
  # spec: HC-P015
  Scenario: check_per_file reports only real-valued Python numeric defaults
    Given ctx: CheckContext contains a Python function whose distinct default parameters have values 0x0, 0O_0, 0B_0, 0_0, 0.0, 0e3, 0j, (-0), (+0.0), 0x2, -1.5, and 1j
    When check_per_file is called
    Then it returns one HC-P015 error at each of the last three default parameters and none at the zero defaults

  # hd: python/honest-check/honest-check.hd::check_per_file
  # spec: HC-P011
  Scenario: check_per_file reports qualified JavaScript lifecycle calls
    Given ctx: CheckContext contains one JavaScript call to view.componentDidMount(), one to componentDidMount(), and one to view.render()
    When check_per_file is called
    Then each componentDidMount call produces one HC-P011 error at its call location naming the lifecycle hook
    And the message directs the caller to HTMX attributes or server-rendered HTML
    And view.render() produces no HC-P011 finding
    And qualified componentWillUnmount and componentDidUpdate calls in JavaScript and qualified ngOnInit and ngOnDestroy calls in TypeScript each produce the same error naming their own hook

  # hd: python/honest-check/honest-check.hd::check_per_file
  # spec: HC-P017 and Honest Page template rendering
  Scenario: check_per_file identifies a declared template response without an emits vocabulary
    Given ctx: CheckContext contains a Python function annotated to return TemplateResponse and it has no declared emits vocabulary
    When check_per_file is called
    Then it returns one HC-P017 error located at the response-producing function

  # hd: python/honest-check/honest-check.hd::check_per_file
  Scenario: check_per_file reports an unknown literal flag against an explicitly empty FEATURES vocabulary
    Given ctx: CheckContext contains a module-level FEATURES = {} and calls feature_state(state, "missing") and feature_state(state, dynamic_flag)
    When check_per_file is called
    Then the literal call produces one HC-HF001 error at the call naming "missing", and the nonliteral call produces no HC-HF001 error

  # hd: python/honest-check/honest-check.hd::check_per_file
  Scenario: check_per_file skips local feature rules when FEATURES is absent or unreadable
    Given ctx: CheckContext contains feature_state(state, "missing") and either lacks a local FEATURES binding or assigns FEATURES from a nonliteral expression
    When check_per_file is called
    Then it returns no HC-HF001 or HC-HF002 findings from those calls

  # hd: python/honest-check/honest-check.hd::check_per_file
  Scenario: check_per_file reports an emitted type neither produced nor accepted without a companion declaration
    Given ctx: CheckContext represents a source link declaring an emitted type absent from both its manifest assignments and its accepted types, with no companion .hd
    When check_per_file is called
    Then its findings include an HC010 warning for the missing type

  # hd: python/honest-check/honest-check.hd::check_per_file
  Scenario: check_per_file allows an emitted type produced by a manifest assignment
    Given ctx: CheckContext represents a source link whose only declared emitted type is produced by a manifest assignment
    When check_per_file is called
    Then its findings contain no HC010 warning

  # hd: python/honest-check/honest-check.hd::check_per_file
  Scenario: check_per_file allows an emitted type accepted by the link
    Given ctx: CheckContext represents a source link whose only declared emitted type is accepted by that link and is absent from its manifest assignments
    When check_per_file is called
    Then its findings contain no HC010 warning

  # hd: python/honest-check/honest-check.hd::check_per_file
  Scenario: check_per_file does not warn on a link with no declared emitted types
    Given ctx: CheckContext represents a source link with no declared emitted types
    When check_per_file is called
    Then its findings contain no HC010 warning

  # hd: python/honest-check/honest-check.hd::check_construction
  Scenario: check_construction leaves HC010 to the per-file rule group
    Given ctx: CheckContext represents a source link declaring an emitted type absent from both its manifest assignments and its accepted types
    When check_construction is called
    Then its findings contain no HC010 warning

  # hd: python/honest-check/honest-check.hd::check_per_file
  Scenario: check_per_file allows an explicit binding for a declared base type
    Given ctx: CheckContext for an explicit binding whose key names a base type in the applicable vocabulary
    When check_per_file is called
    Then its findings contain no HC005 warning for that key

  # hd: python/honest-check/honest-check.hd::check_per_file
  Scenario: check_per_file allows an explicit binding for a declared composed type
    Given ctx: CheckContext for an explicit binding whose key names a composed type in the applicable vocabulary
    When check_per_file is called
    Then its findings contain no HC005 warning for that key

  # hd: python/honest-check/honest-check.hd::check_per_file
  Scenario: check_per_file warns for an unknown explicit binding key
    Given ctx: CheckContext for an explicit binding with one key absent from both the applicable base and composed names
    When check_per_file is called
    Then its findings include one HC005 warning naming that key

  # hd: python/honest-check/honest-check.hd::check_per_file
  Scenario: check_per_file skips automatic binding
    Given ctx: CheckContext for a vocabulary use with automatic binding
    When check_per_file is called
    Then its findings contain no HC005 warning for that use

  # hd: python/honest-check/honest-check.hd::check_construction
  Scenario: check_construction leaves HC005 to the per-file rule group
    Given ctx: CheckContext for a file with a vocabulary and an explicit binding
    When check_construction is called
    Then the construction-time findings contain no HC005 diagnostic

  # hd: python/honest-check/honest-check.hd::_is_directive
  # spec: Honest Check §7 (as cited by the declaration)
  Scenario: _is_directive recognizes the stripped honest prefix
    Given text: str is "  honest: ignore HC-P004", "honest:", "note: honest: ignore HC-P004", or "just a comment"
    When _is_directive is called
    Then it returns true for the first two strings and false for the last two

  # hd: python/honest-check/honest-check.hd::_directive_record
  # spec: Honest Check §7 (as cited by the declaration)
  Scenario: _directive_record extracts recognized rules and reason presence
    Given comment: Node is an actual comment at source line 2 containing "honest: disable HC-P004, HC-P005 HC-P011: a reason: with a colon"
    When _directive_record is called
    Then it returns the same node, line 2, verb disable, exactly the rule set HC-P004, HC-P005 and HC-P011, and has_reason true
    And a recognized directive with an all-whitespace reason has has_reason false
    And an unrecognized verb or empty rule list returns NOTHING

  # hd: python/honest-check/honest-check.hd::_directives
  # spec: Honest Check §7 (as cited by the declaration)
  Scenario: _directives retains the ranges each recognized directive owns
    Given ctx: CheckContext contains a disable of HC-P004 and HC-P005 on line 1, a repeated disable of HC-P004 on line 2, an enable of HC-P004 on line 4, and an ignore of HC-P011 on line 5
    When _directives is called
    Then it returns the four recognized directives in source order
    And the first owns HC-P004 from line 2 through 3 and HC-P005 from line 2 through NOTHING
    And the repeated disable and the enable own no ranges, and the ignore owns HC-P011 only on line 5

  # hd: python/honest-check/honest-check.hd::_diag_line
  # spec: Honest Check §7 (as cited by the declaration)
  Scenario: _diag_line reads the line from the right of a source location
    Given diag: Diagnostic has source_location "drive:folder/demo.py:17:4" or only "demo.py"
    When _diag_line is called
    Then it returns 17 for the location with a line and NOTHING for the file-only location

  # hd: python/honest-check/honest-check.hd::_matches
  # spec: Honest Check §7 (as cited by the declaration)
  Scenario: _matches checks inclusive ranges and excludes policy findings
    Given directive: ScopedSuppression owns HC-P004 from line 2 through 4, and diag: Diagnostic varies by rule and source line
    When _matches is called
    Then HC-P004 matches at lines 2 and 4 but not at lines 1 and 5, and a different rule or a location with no line does not match
    And a diagnostic for HC-SUP001 or HC-SUP002 never matches, even when the directive names that rule and owns its line
    And an enable with no ranges never matches

  # hd: python/honest-check/honest-check.hd::_resolve_one
  # spec: Honest Check §7 (as cited by the declaration)
  Scenario: _resolve_one preserves findings while downgrading matching severity
    Given diag: Diagnostic is an error with rule, location, message, context and fixability, and directives: list<ScopedSuppression> either contains a matching range or does not
    When _resolve_one is called
    Then in the matching case it returns a copy with severity info and all other fields unchanged
    And in the unmatched case it returns the original finding unchanged

  # hd: python/honest-check/honest-check.hd::_suppression_findings
  # spec: Honest Check §7 (as cited by the declaration)
  Scenario: _suppression_findings reports dead and missing reason findings in order
    Given ctx: CheckContext contains a reasoned matching ignore, a blank-reason redundant disable with no owned range, a matching ignore without a reason, and an enable, in that source order
    And directives: list<ScopedSuppression> contains their recognized directives and owned ranges and raw_diagnostics: list<Diagnostic> contains the original findings that match the two ignores
    When _suppression_findings is called
    Then it returns HC-SUP001 followed by HC-SUP002 at the redundant disable and HC-SUP002 at the matching reasonless ignore
    And the reasoned matching ignore and the enable each contribute no policy finding

  # hd: python/honest-check/honest-check.hd::apply_suppression
  # spec: Honest Check §7 (as cited by the declaration)
  Scenario: apply_suppression closes only the enabled rule in a mixed list
    Given ctx: CheckContext has a top-of-file comment "honest: disable HC-P004, HC-P005 HC-P011: legacy behavior" on line 1 and "honest: enable HC-P004" on line 3
    And raw_diagnostics: list<Diagnostic> contains an error for each listed rule on line 2 and each on line 4
    When apply_suppression is called
    Then all three line 2 findings become info
    And on line 4 HC-P004 keeps error severity while HC-P005 and HC-P011 become info because their ranges never closed
    And it preserves raw finding order and adds no policy finding

  # hd: python/honest-check/honest-check.hd::apply_suppression
  # spec: Honest Check §7 (as cited by the declaration)
  Scenario: apply_suppression reports redundant disables and blank reasons
    Given ctx: CheckContext has "honest: disable HC-P004: legacy I/O" on line 1 and a second disable for HC-P004 on line 2 whose reason after the colon is only whitespace
    And raw_diagnostics: list<Diagnostic> contains one HC-P004 error on line 3
    When apply_suppression is called
    Then the original disable downgrades the line 3 finding to info
    And the redundant disable does not replace its range or claim its finding
    And the redundant directive adds HC-SUP001 followed by HC-SUP002 at line 2

  # hd: python/honest-check/honest-check.hd::apply_suppression
  # spec: Honest Check §7 (as cited by the declaration)
  Scenario: apply_suppression ignores unrecognized verbs and preserves policy findings
    Given ctx: CheckContext contains a comment "honest: reverb HC-P004: unrecognized verb" on line 1 and a comment "honest: ignore HC-SUP001, HC-SUP002: attempted suppression" on line 2
    And raw_diagnostics: list<Diagnostic> contains one HC-P004 error on line 1 and the two policy errors HC-SUP001 and HC-SUP002 on line 2
    When apply_suppression is called
    Then all raw findings keep their severity and order
    And reverb neither suppresses nor creates a policy finding
    And the recognized ignore adds one HC-SUP001 for matching no eligible finding

  Scenario: apply_suppression
    Given ctx: CheckContext and raw_diagnostics: list<Diagnostic>
    When apply_suppression is called
    Then it reads the inline and file-level suppression directives off the parse in ctx and applies them to raw_diagnostics: a suppressed finding is downgraded to info rather than dropped, a directive that suppressed nothing is reported as HC-SUP001 (dead directive) and a directive carrying no reason as HC-SUP002, each built with diagnostic; it returns the suppression-resolved diagnostics and raises nothing

  # --- The generalized HC-REF012 cross-module pure dependency (§HC-REF012) -------

  # hd: python/honest-check/honest-check.hd::pure_target_is_callable
  Scenario: pure_target_is_callable
    Given target: str is one qualified "<module>.<function>" pure_call string and declarations: dict<str, Declaration> is every loaded module's parsed .hd keyed by module name
    When pure_target_is_callable is called
    Then it splits target once on the first dot into the target module name and the target function name, reads the target module's Declaration off declarations without constructing one, touches no world and opens no file, and returns the single boolean, true only when the target module name is a key in declarations and that module declares a function of the target name whose role is the plain fn, declares no side effect at all, and is published by the target module as a pure way in through a valid entry or export; it raises nothing

  # hd: python/honest-check/honest-check.hd::pure_target_is_callable
  Scenario: pure_target_is_callable returns true for a published pure fn
    Given target: str is "utils.answer" and declarations: dict<str, Declaration> includes utils, which declares answer as a plain fn with no side effects and publishes it through a valid entry or export
    When pure_target_is_callable is called
    Then it returns true, because the target names a function another module publishes as a pure way in, the same published-pure-function evidence HC-REF007 and the entry checker resolve

  # hd: python/honest-check/honest-check.hd::pure_target_is_callable
  Scenario: pure_target_is_callable returns false for a target the module does not declare
    Given target: str is "utils.absent" and declarations: dict<str, Declaration> includes utils, which declares no function named absent
    When pure_target_is_callable is called
    Then it returns false, because the function does not exist and a missing function is not callable

  # hd: python/honest-check/honest-check.hd::pure_target_is_callable
  Scenario: pure_target_is_callable returns false for a side-effecting target
    Given target: str is "utils.read_file" and declarations: dict<str, Declaration> includes utils, which declares read_file with at least one declared side effect
    When pure_target_is_callable is called
    Then it returns false, because a side-effecting target is a side-effect seam and not a pure dependency, and naming a world-touching call as a pure dependency would hide the I/O it does

  # hd: python/honest-check/honest-check.hd::pure_target_is_callable
  Scenario: pure_target_is_callable returns false for a target whose role is edge
    Given target: str is "utils.edgefn" and declarations: dict<str, Declaration> includes utils, which declares edgefn with the retired edge role
    When pure_target_is_callable is called
    Then it returns false, because the edge role names no new surface and is refused here the way the spec retires it

  # hd: python/honest-check/honest-check.hd::pure_target_is_callable
  Scenario: pure_target_is_callable returns false for an interior unpublished function
    Given target: str is "utils.helper" and declarations: dict<str, Declaration> includes utils, which declares helper as a plain fn with no side effects but exposes it through no entry or export, so no entry reaches it
    When pure_target_is_callable is called
    Then it returns false, because a pure dependency onto an unexported interior function is the same reach into the core HC-REF007 refuses for a seam

  # hd: python/honest-check/honest-check.hd::pure_target_is_callable
  Scenario: pure_target_is_callable returns false for a malformed target with no module half
    Given target: str is "answer" with no dot and declarations: dict<str, Declaration> holds the loaded declarations
    When pure_target_is_callable is called
    Then it returns false, because a string with no dot has no module half and is not a callable target

  # hd: python/honest-check/honest-check.hd::resolve_pure_calls
  Scenario: resolve_pure_calls returns invalid_role for an edge target
    Given module: Declaration contains a function declaring a pure call to a target whose function exists in a module in view but carries the retired edge role, and declarations: dict<str, Declaration> includes that target module and function
    When resolve_pure_calls is called
    Then it returns invalid_role for the occurrence, because the function exists but is not the plain fn role, so pure_target_is_callable says false and the occurrence provides no dependency evidence

  # hd: python/honest-check/honest-check.hd::resolve_pure_calls
  Scenario: resolve_pure_calls returns invalid_role for an interior unpublished target
    Given module: Declaration contains a function declaring a pure call to a plain side-effect-free fn in a module in view that no entry or export publishes, and declarations: dict<str, Declaration> includes that target module and function
    When resolve_pure_calls is called
    Then it returns invalid_role for the occurrence, because the function exists but is interior and unpublished, so pure_target_is_callable says false and the occurrence provides no dependency evidence

  # hd: python/honest-check/honest-check.hd::check_ref012
  Scenario: check_ref012 accepts a resolved pure call as dependency evidence
    Given module: Declaration has a manifest dependency onto a workspace module its declaration couples to only through a resolved pure_call onto that module's published pure fn, manifest_deps: list<str> is the dependencies the orchestrator has left after subtracting every dependency a resolved pure dependency evidences, workspace_module_names: list<str> holds the workspace modules, and path: str is the module's .hd path
    When check_ref012 is called
    Then it emits no HC-REF012 error for that dependency, because the resolved pure dependency satisfies the manifest dependency the same way a side-effect seam does, the orchestrator having already removed it from manifest_deps before this function runs

  # hd: python/honest-check/honest-check.hd::check_ref012
  Scenario: check_ref012 errors on a dependency with neither a seam nor a pure call
    Given module: Declaration has a manifest dependency onto a workspace module its declaration covers with neither a declared side-effect seam nor a resolved cross-module pure_call onto it, manifest_deps: list<str> still carries that dependency, workspace_module_names: list<str> includes the dependency module, and path: str is the module's .hd path
    When check_ref012 is called
    Then it emits one HC-REF012 error naming the module and that dependency at error severity, because a dependency reaching this function is covered by neither kind of coupling, telling the author to name it as a side-effect seam if the call touches the world or as a pure dependency with a pure_call if the call is pure

  # hd: python/honest-check/honest-check.hd::check_ref012
  Scenario: check_ref012 errors on a dependency whose only pure call is non-callable
    Given module: Declaration has a manifest dependency onto a workspace module its declaration couples to only through a pure_call whose target is non-callable (does not exist, is side-effecting, is edge, or is interior and unpublished), so resolve_pure_calls returned invalid_role and the orchestrator subtracted nothing, leaving that dependency in manifest_deps: list<str>, with workspace_module_names: list<str> including the dependency module and path: str the module's .hd path
    When check_ref012 is called
    Then it emits one HC-REF012 error naming the module and that dependency at error severity, because an invalid_role pure call satisfies the dependency with neither kind of coupling

  # hd: python/honest-check/honest-check.hd::check_ref012
  Scenario: check_ref012 needs no honest-parse deferral once honest-parse publishes its pure functions
    Given module: Declaration is honest-check, which imports honest-parse's pure functions and couples to honest-parse only through resolved pure_call annotations onto them, honest-parse now publishes each of those pure functions as a valid way in through an entry or export, manifest_deps: list<str> is the dependencies left after the orchestrator subtracts every dependency a resolved pure dependency evidences, workspace_module_names: list<str> includes honest-parse, and path: str is honest-check's .hd path
    When check_ref012 is called
    Then it emits no HC-REF012 error for the honest-parse dependency, because honest-check's resolved pure_call onto honest-parse's published pure functions satisfies the manifest dependency, so the honest-check to honest-parse HC-REF012 coupling needs no hardcoded per-module deferral or exemption

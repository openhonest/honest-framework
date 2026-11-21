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

  Scenario: run_check
    Given argv: list<str> whose CliArgs.declaration is the empty string (base mode)
    When run_check is called
    Then it parses the arguments, builds the ProjectConfig with load_project_config and resolve_project_config, and discovers the source files with discover_files; in base mode it builds the RuleConfig with load_config and resolve_rule_config, and for each discovered file reads it with read_source, builds the CheckContext with build_context, and runs check_source over it with the nearest enclosing module .hd (read through read_declaration, or NOTHING when the file lies under none) as the declaration; it then runs check_references once over the whole template/stylesheet/script/code set (paired through pair_source), check_roles once per module-.hd group of code files, and check_auth once over all code files as one set, folding every finding into one list; it prepares the findings with prepare_report, renders with the by_format dispatch, writes to stdout with write_report, and returns the ExitCode resolve_exit_code decides

  Scenario: run_check
    Given argv: list<str> whose CliArgs.declaration names an .hd that reads and parses (declaration-crossing mode)
    When run_check is called
    Then it parses the arguments, builds the ProjectConfig, and discovers the files; it pulls the one parsed module with read_declaration over CliArgs.declaration, reads the export module's text with read_source over CliArgs.exports when non-empty, reads each discovered file with read_source and pairs it through pair_source into a SourceFile, and runs cross_declaration once over the whole-package batch (crossing the one declaration against every file together, running only the crossing rules named in CliArgs.include_rules so HC-REF005 sees the entire defined-function set); it feeds the combined list into the same tail — prepare_report, by_format, write_report — and returns the ExitCode resolve_exit_code decides

  Scenario: run_check
    Given argv: list<str> whose CliArgs.declaration names an .hd that is missing or does not parse (crossing-mode read failure)
    When run_check is called
    Then read_declaration answers a raw read-failure reason (a str, not a Fault), and run_check checks nothing over a declaration it could not open: it assembles honest-check's Fault from that reason through the pure read_fault off the boundary and routes that Fault straight outward as its ExitCode | Fault answer, which the door discharges as exit code 2

  # --- The CLI door -------------------------------------------------------------

  Scenario: main
    Given argv: list<str>
    When main is called
    Then it carries only I/O: it hands argv straight to run_check and turns run_check's answer into the process exit; on an ExitCode it exits the process with it (0 means success though warnings may have printed, 1 means the gate failed with errors at or below the declared adoption level); on the declaration-read Fault it discharges it at exit code 2, raising HonestCheckError carrying the Fault's problem and remedy rather than returning a clean code over a declaration it could not open; it raises HonestCheckError only on that declaration-read failure

  # --- The cross-module seam rules (HC-REF006, HC-REF007) -----------------------

  Scenario: declared_seams
    Given module: Declaration
    When declared_seams is called
    Then for each function in the module and each side effect it declares, it skips a side effect whose module half is the empty string (it names the world and carries no module to resolve) and turns a side effect whose module half is non-empty into one Seam carrying the function name as caller, the named module, the door (the dotted target's door half, the empty string when the target named a module and no door) and the direction; it reads nothing, opens nothing, and returns the list of seams (empty when the module declares no cross-module side effect)

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

  Scenario: check_seams
    Given declarations: dict<str, Declaration> and paths: dict<str, str> and manifest_deps: dict<str, list<str>> and in_scope: list<str>
    When check_seams is called
    Then it is the single door the honest-pre-commit dogfood gate reaches into the cross-module seam checks: it hands its four inputs straight to run_seam_rules and returns the combined diagnostic list, holding no resolution logic itself; the declarations arrive already parsed, so it opens no file; it returns the flat list of every HC-REF006, HC-REF007 and HC-REF012 Diagnostic over the in-scope modules (resolved against every declaration) and raises nothing

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

  Scenario: own_body
    Given fdef: Node
    When own_body is called
    Then it returns the body descendants belonging to the function itself, not descending into a deeper nested def, lambda or decorated def, whose statements are the inner scope's own

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

  Scenario: watched
    Given target: Node and watch: set<str>
    When watched is called
    Then it returns true when a call's dotted target is on the watch list — an exact entry matches by equality and an entry carrying a `*` matches as a glob (a trailing `.*` names any attribute of a module, a trailing `*` is a prefix, a `*` between dots is one segment)

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

  Scenario: dotted_target
    Given ctx: CheckContext and call_node: Node
    When dotted_target is called
    Then it returns the dotted name a call invokes — `open`, `os.system`, `requests.get`, `urllib.request.urlopen` — or NOTHING when the target is not a plain or dotted name, such as a call on a call's result (HC008)

  Scenario: link_is_impure
    Given ctx: CheckContext and fdef: Node and watch: set<str> and mutable_globals: set<str>
    When link_is_impure is called
    Then it returns true when a link's own body calls a watched function or reads a module-level mutable global, the body search not descending into a nested def or lambda (HC008)

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

  Scenario: feature_state_flag
    Given ctx: CheckContext and call_node: Node
    When feature_state_flag is called
    Then it returns the flag a feature_state(state, "flag") call names — its second positional string literal — or NOTHING when the call names fewer than two positionals or a dynamic (non-literal) flag, the call resolved by name through called_name (HC-HF rules)

  Scenario: module_dict_literals
    Given ctx: CheckContext
    When module_dict_literals is called
    Then it returns each module-scope name bound to a dict literal, mapped to the set of string keys the literal declares; a name bound to anything but a module-scope dict literal is not included (HC-HF002)

  Scenario: vocabulary_types
    Given ctx: CheckContext and vocab_call: Node
    When vocabulary_types is called
    Then it returns the type surface of a vocabulary(...) call — its base-type names, its composed-type names, the base names its composed types require, and the base names its composed types capture — reading the first-argument dictionary through base_types_of (HC004, HC005)

  Scenario: binding_keys
    Given ctx: CheckContext and binding_call: Node
    When binding_keys is called
    Then it returns the type names a binding(...) call binds — the keys of its first-argument table (HC004, HC005)

  Scenario: vocabulary_binding_pairs
    Given ctx: CheckContext
    When vocabulary_binding_pairs is called
    Then it returns each (vocabulary calls, binding call) a classify or link pairs by name: a classify(tokens, vocab, bind=b) pairs positional 2 with the `bind` keyword with the one vocab as its vocabulary list, and a link(accepts=v, emits=e, bind=b) pairs by its keywords (HC004, HC005)

  # --- The two rule sub-cores and the suppression pass --------------------------

  Scenario: check_construction
    Given ctx: CheckContext
    When check_construction is called
    Then it runs the construction-time rules — HC001, HC003, HC006, HC007, HC011 and the state-machine rules HC-SM01, HC-SM02, HC-SM05 — dispatched by the framework constructor each call site resolves to, reaching the shared vocabulary-and-binding helper layer (canonical_name, call_arguments, string_members, literal_string, base_types_of, vocabulary_types, binding_keys, construction_maps, vocabulary_binding_pairs) and building each finding with diagnostic; the per-rule logic nests here as data, it returns the construction-time findings, and it raises nothing

  Scenario: check_per_file
    Given ctx: CheckContext
    When check_per_file is called
    Then it runs the static per-file rules — the HC-P purity rules including HC-P014, the chain and link rules HC009, HC010, HC004 and HC005, the per-file state rules HC-ST001 and HC-ST002, and the HC-HF feature-flag rules — folded over the declaration graph, reaching the shared AST helper layer (the scope, decorator, impurity, state and feature helpers) and building each finding with diagnostic; the per-rule logic nests here as data, it returns the per-file findings, and it raises nothing

  Scenario: apply_suppression
    Given ctx: CheckContext and raw_diagnostics: list<Diagnostic>
    When apply_suppression is called
    Then it reads the inline and file-level suppression directives off the parse in ctx and applies them to raw_diagnostics: a suppressed finding is downgraded to info rather than dropped, a directive that suppressed nothing is reported as HC-SUP001 (dead directive) and a directive carrying no reason as HC-SUP002, each built with diagnostic; it returns the suppression-resolved diagnostics and raises nothing

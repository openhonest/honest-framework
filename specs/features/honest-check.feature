Feature: honest-check — the static checker, the honesty gate
  One scenario per declared function (34 total). One pure core folds the whole rule
  catalogue over a declaration graph; a second pure core crosses a module's .hd against
  its whole package; a third pure core crosses references across the whole file set; a
  fourth pure core runs the whole-program orphan pass over a package's code; a fifth pure
  core runs the whole-program authentication pass over the project's code; three
  orchestrators pull files and seams and share those cores; three
  doors reach the world (startup integration, the CLI, and the hd-check seam gate); the
  cross-module seam checks resolve the references one module's .hd writes into others; the
  rest read the filesystem, parse the argument vector, pair a path with its text, or render
  the report.

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

  Scenario: check_references crosses references across the whole file set and returns the unresolved ones
    Given sources: list<SourceFile>
    When check_references is called
    Then it is the pure cross-file reference core of the base-mode CLI path, the whole-set counterpart of check_source for references that resolve across files rather than within one: it takes the whole discovered set of the project's template, stylesheet and script files, already read and paired into SourceFile records, parses each under the grammar honest-parse detects from its path extension, builds from the whole set at once the two resolvable sets the reference rules need, resolves each template's include/extends targets and class references against those sets, and returns the findings as a list of Diagnostic
    And sources is that whole-set view, a list of SourceFile each pairing one discovered template, stylesheet or script file with the filesystem path it was read from — the path used to detect the grammar and to stamp each diagnostic's source_location, and check_references does not re-open it; off each file it reads what that file states: a template's (.html, under the Jinja grammar) include/extends targets and static or interpolated class values, a stylesheet's (.css) class selectors, and a script's (.js) string-literal classList add/remove/toggle/replace/contains arguments and className assignment tokens
    And HC-REF002 resolves each template's literal include/extends target against the set of templates the whole set holds — a target resolves when it matches a template file relative to any search root the way the engine's loader searches — and emits an error for a literal target that matches no template, skipping a dynamic target that carries no string literal; HC-REF003 resolves each static class a template emits and each string-literal class a script adds against the union of the class selectors every discovered stylesheet defines and emits an error for a class no stylesheet defines, skipping an interpolated class value or a non-literal classList/className argument as the stated bound of the check; both rules are error severity
    And the per-rule crossing logic is nested here as data exactly as check_source holds its construction rules — HC-REF002 and HC-REF003 are not separately declared functions, and the exact Diagnostic each produces for a given set of files is pinned by the conformance suite, not by any per-rule function
    But it opens no file (read_source does that), parses no .hd, executes none of the code it inspects, modifies nothing, and raises nothing: a dead reference comes back as a Diagnostic; an empty list means every literal include/extends target and every static class reference resolved

  Scenario: check_roles runs the whole-program orphan pass over a package's code and returns the unrooted functions
    Given sources: list<SourceFile> and declaration: Declaration | NOTHING
    When check_roles is called
    Then it is the pure whole-program core of the orphan-function rule HC-R001, the whole-package counterpart of check_source for the one role rule no single file can decide: it takes the package's code files (the SourceFile records of the languages honest-parse recognizes as source — Python, JavaScript or TypeScript, Ruby, Go — not templates or stylesheets) and the package's parsed .hd module, or the absence value NOTHING when the code has no module .hd, parses each SourceFile under the grammar honest-parse detects from its path extension, reads each file's top-level function definitions and call sites, builds the whole-program call graph across all the sources, and returns one HC-R001 error per top-level function that is neither roled nor reachable from a roled one, as a list of Diagnostic all at error severity
    And a top-level function is roled when it carries a role decorator — @link, @recognizer, @boundary, @helper or @orchestrator — or when the declaration names it, because every function a .hd declares carries a role there even when its code wears no decorator, so it reads the declared function set off the Declaration to seed the roled set, computes the set reachable from the roled set through the call graph, and flags the rest as orphans that auto-generation cannot reach — so no test is generated for them and the code is dishonest
    And it takes the whole package as a list<SourceFile> rather than one source because a function orphaned in one file may be reached by a call from another, so reachability is answerable only with every file's definitions and call sites in view at once, the same reason check_references takes the whole template/stylesheet/script set and cross_declaration takes the whole crossing package; the per-rule HC-R001 logic nests here as data exactly as check_source holds its construction rules, HC-R001 is not a separately declared function, and the exact Diagnostic it produces for a given package and declaration is pinned by the conformance suite, not by any per-rule function
    And when no function is roled at all — no role decorator on any function and declaration is NOTHING — the role system is not in use for this package, so it emits nothing and never floods a codebase that has not adopted roles with a finding on every function; sources pairs each code file with the path used to detect its grammar and stamp each diagnostic's source_location, and declaration is always a bounded value so the rule never has to tell 'absent' from 'forgot'
    But it opens no file (read_source does that), parses no .hd (honest-design's job), executes none of the code it inspects, modifies nothing, and raises nothing: an orphan comes back as a Diagnostic, never as an exception; an empty list means every top-level function is roled or reachable, or the package has adopted no roles at all

  Scenario: check_auth runs the whole-program authentication pass over the project's code and returns the identity findings
    Given sources: list<SourceFile>
    When check_auth is called
    Then it is the pure whole-program core of the two identity rules HC-A001 and HC-A002, the whole-package counterpart of check_source for the two rules that turn on project-wide authentication-provider registration: it takes the project's code files (the SourceFile records of the languages honest-parse recognizes as source — Python, JavaScript or TypeScript, Ruby, Go — not templates or stylesheets), parses each under the grammar honest-parse detects from that file's path extension, and returns every HC-A001 and HC-A002 finding as a list of Diagnostic, HC-A001 at warning severity and HC-A002 at error severity
    And both rules are whole-program and not per-file because provider registration is project-wide — a provider registered in any one file governs every authorizing link across the whole project, so the register-is-present question is answerable only with the whole set in view at once, the same reason check_roles takes the whole package and check_references takes the whole template/stylesheet/script set; a provider is registered when some file in the set calls honest-auth's register_auth_provider(...), the call that installs the boundary validator which resolves an actor, and an authorizing link is a top-level function decorated @link(authorizes=True), a link that acts on behalf of an actor whose actor the framework resolves at the boundary and passes inward as the name actor
    And HC-A001 fires at warning severity when no file in the set registers a provider and the set holds at least one authorizing link, emitting one warning that names those links and says to register a provider or remove the actor dependency, because those links act on behalf of an actor but no boundary validator resolves one so the identity they act under is unverifiable; it is a warning because an application with no authentication may be intentional, so the gap is surfaced without blocking the gate
    And HC-A002 fires at error severity when a provider is registered, emitting one error at the location of each authorizing link whose body does not reference the name actor, because such a link sources identity from forgeable request input — body, query string, form fields, the manifest — instead of the boundary-resolved actor that must flow inward as the data named actor
    And the provider-registered gate makes the two mutually exclusive over one set, so no authorizing link is ever reported by both — a link is flagged by HC-A001 only when no provider is registered anywhere, and by HC-A002 only when one is; sources is the whole-package code view, each SourceFile pairing one code file with the path used to detect its grammar and stamp each diagnostic's source_location, and the per-rule HC-A001 and HC-A002 logic nests here as data exactly as check_source holds its construction rules, pinned by the conformance suite, not by any per-rule function
    But it opens no file (read_source does that), parses no .hd, executes none of the code it inspects, modifies nothing, and raises nothing: a finding comes back as a Diagnostic, never as an exception; an empty list means either a provider is registered and every authorizing link references actor, or no provider is registered and the set holds no authorizing link

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

  Scenario: declared_seams collects every cross-module seam one module declares
    Given module: Declaration
    When declared_seams is called
    Then for each function in module.functions and each side effect that function declares, it keeps only the side effects whose module half is non-empty, turning each into one Seam carrying the function's name as caller, the named module, the door (the side effect's door half, which may be the empty string when the target named a module and no door), and the direction (reads, writes or reads_writes)
    And it skips a side effect whose module half is the empty string, because that names the world — reads "HTTP", writes "DOM", reads "env:POOL_SIZE" — and carries no module to resolve
    And it is the one derivation check_hc_ref006 and check_hc_ref007 each invoke, so a module's seams are derived once and named in one place
    But it reads nothing, opens nothing, and decides nothing beyond this selection, returning the list of seams, empty when the module declares no cross-module side effect

  Scenario: check_hc_ref006 flags a seam into a present module that declares no function of that door name
    Given module: Declaration and declarations: dict<str, Declaration> and path: str
    When check_hc_ref006 is called
    Then it invokes declared_seams to get the module's seams, then for a seam whose named module is a key in declarations but whose functions include no function named the seam's door, it emits one HC-REF006 error naming the caller, the module and the door — a dead reference, the artifact reads as working and the door it points at is absent
    And it skips a seam whose door is the empty string (a module named with no door, HC-REF008's case, not this rule's) and skips a seam whose named module is not a key in declarations, not assumed absent, because a workspace may name a module from outside it and a gate whose answer changes with how it was invoked is not a gate
    And module is the one declaration whose seams are resolved, declarations is every loaded declaration keyed by its module name (the gate supplies them and the rule judges only those), and path is the filesystem path of module's .hd stamped into each diagnostic's source_location
    But it reads nothing and raises nothing, returning one Diagnostic per dead seam at error severity; the empty list means every door name a seam of this module named resolved to a function in the named module

  Scenario: check_hc_ref007 flags a seam whose door name is declared but is not a boundary_in
    Given module: Declaration and declarations: dict<str, Declaration> and path: str
    When check_hc_ref007 is called
    Then it invokes declared_seams to get the module's seams, then for a seam whose named module is in declarations and declares a function of the seam's door name whose role is not boundary_in, it emits one HC-REF007 error naming the caller, the module, the door and the role the module gave that door — the world is reaching that module somewhere other than its entrance
    And it applies the same two skips as HC-REF006: a seam whose door is the empty string is skipped (HC-REF008's case), and a seam whose named module is not a key in declarations is skipped, not assumed absent, because a gate whose answer changes with how it was invoked is not a gate
    And module is the one declaration whose seams are resolved, declarations is every loaded declaration keyed by its module name, and path is the filesystem path of module's .hd stamped into each diagnostic's source_location
    But it reads nothing and raises nothing, returning one Diagnostic per such seam at error severity; the empty list means every door a seam of this module named is a boundary_in of the module it named

  Scenario: run_seam_rules folds the two cross-module seam rules over every in-scope module
    Given declarations: dict<str, Declaration> and paths: dict<str, str> and in_scope: list<str>
    When run_seam_rules is called
    Then for each module named in in_scope — or every loaded module when in_scope is empty — it calls check_hc_ref006 then check_hc_ref007 with that module's declaration, the whole declarations map and the module's .hd path, concatenating their diagnostics in that order across every in-scope module
    And it resolves each in-scope module's seams against the complete declarations map, not the in-scope subset, because a seam one in-scope module wrote may enter a module outside the scope and must still resolve to a door, which keeps the gate's verdict on a module independent of how it was invoked
    And it never derives seams itself and never calls declared_seams directly, because each rule it invokes derives that module's seams once through declared_seams
    But it reads nothing, opens no file and touches no world — the declarations arrive already parsed from the door — returning the flat combined list of every Diagnostic the two rules produced across the in-scope modules, empty when every in-scope module's seams resolve, and raising nothing

  Scenario: check_seams is the hd-check gate door that routes the seam inputs to the orchestrator
    Given declarations: dict<str, Declaration> and paths: dict<str, str> and in_scope: list<str>
    When check_seams is called
    Then it is the single entry point the external hd-check dogfood gate reaches into the cross-module seam checks: it hands its three inputs straight to the orchestrator run_seam_rules and returns the combined diagnostic list the orchestrator produced, holding no resolution logic itself
    And declarations is every loaded module's parsed declaration keyed by its module name, the whole map in view because resolving an in-scope module's seam into module M needs M's declaration whether or not M is in scope; paths is each module's .hd path keyed by the same name, stamped into each diagnostic; in_scope is the affected set to report on, the empty list meaning every loaded module is in scope
    And it returns the flat list of every Diagnostic the cross-module rules produced — one HC-REF006 error per seam into a module that declares no function of the named door, one HC-REF007 error per seam onto a function that is not a boundary_in — and the empty list when every in-scope module's seams resolve
    But because the gate supplies the declarations already parsed, this door opens no file, reads no world and writes none, and raises nothing: an unresolved seam comes back as a Diagnostic

  Scenario: resolve_aliases recovers the import aliases a framework call resolves through
    Given root: Node and source: bytes
    When resolve_aliases is called
    Then it reads every import statement off the parsed tree and returns the map from each local name the source bound an honest-framework import to, to that import's canonical framework name, so an aliased import (from honest_type import vocabulary as v) is still recognized as the framework call it names
    And the returned map goes local_name -> canonical_name: a direct alias (vocabulary as v) maps v -> vocabulary, and a module alias (import honest_type as ht) maps ht.* -> honest_type.* so a dotted call through the alias resolves
    And root is the parsed syntax-tree node honest-test produced with honest-parse's parse, and source is that file's full source bytes — code in a language honest-parse recognizes (Python, JavaScript or TypeScript, Ruby, Go), never a .hd declaration — which it reads to recover each import statement's text
    And honest-test calls it once per file and hands the resulting map to extract_chains and extract_state_machines, so the alias resolution the two extractors rely on is derived one time
    But it opens no file, executes none of the code it reads, raises nothing, and returns the empty map when the source imports nothing from the framework

  Scenario: extract_chains recognizes every chain the source declares
    Given root: Node and source: bytes and aliases: dict<str, str>
    When extract_chains is called
    Then it finds every chain the source declares — each chain() construction, recognized through the aliases map so an aliased chain import still counts — and returns one ChainDecl per chain, carrying the chain's declared name and the ordered names of its link functions
    And this is the same chain construct HC002 crosses adjacent links' vocabularies over and HC-R002 reads, recognized once here so honest-check and honest-test never derive 'what is a chain' independently and drift silently
    And root is the parsed tree honest-test produced with honest-parse's parse, source is the file's full source bytes honest-parse parsed — code in a language honest-parse recognizes and never a .hd — and aliases is the local-name-to-canonical-name map resolve_aliases returned for this same file
    And honest-test binds each returned name to a live object through the imported module and enumerates the chain exhaustively
    But it opens no file, executes none of the code it reads, raises nothing, and returns the empty list when the file declares no chain — a construct it cannot recognize is absent from the list, never an error

  Scenario: extract_state_machines recognizes every state machine the source declares
    Given root: Node and source: bytes and aliases: dict<str, str>
    When extract_state_machines is called
    Then it finds every state machine the source declares — each state_machine() construction, recognized through the aliases map so an aliased import still counts — and returns one MachineDecl per machine, carrying the machine's declared name
    And this is the same state_machines construct the HC-SM rules (HC-SM01, HC-SM02, HC-SM05) check, recognized once here so honest-check and honest-test never derive it independently and drift silently
    And root is the parsed tree honest-test produced with honest-parse's parse, source is the file's full source bytes honest-parse parsed — code in a language honest-parse recognizes and never a .hd — and aliases is the local-name-to-canonical-name map resolve_aliases returned for this same file
    And honest-test binds each returned name to a live object through the imported module and enumerates the machine exhaustively
    But it opens no file, executes none of the code it reads, raises nothing, and returns the empty list when the file declares no state machine — a construct it cannot recognize is absent from the list, never an error

  Scenario: template_class_references returns the static CSS classes a component template references
    Given template: str
    When template_class_references is called
    Then it reads a component template's text and returns one ClassRef per static CSS class the template references, so honest-test can prove two components do not share a CSS namespace against exactly the classes HC-REF003 resolves
    And template is the template's full text — the markup of one component template, read as text, not a parsed node and not source bytes, because the class references are read from the template text itself
    And each returned ClassRef carries one statically-known class token, and a class value carrying interpolation (class="card {{ variant }}") is dynamic and is skipped whole, exactly as HC-REF003 skips it, so every ClassRef names a fully static class the template really references
    But it opens no file, executes nothing, raises nothing, and returns the empty list when the template references no static class

  Scenario: matches_watchlist tests whether a dotted call name matches a watchlist entry
    Given name: str and watchlist: list<str>
    When matches_watchlist is called
    Then it answers whether a dotted call name matches an entry in a watchlist: an entry that carries no '*' matches by exact equality, and an entry that carries a '*' matches as a glob, the same membership HC008 runs against its IO_WATCH_LIST and NONDETERMINISTIC_WATCH_LIST
    And name is the dotted call name read off a call site — for example 'time.time', 'os.environ.get', 'requests.get' — and watchlist is the list of watchlist entries to test against, each a dotted name, some carrying a '*' glob (for example 'random.*', 'subprocess.run', 'fs.*'), exactly the entries IO_WATCH_LIST and NONDETERMINISTIC_WATCH_LIST hold for a language
    And it is exposed for honest-test so honest-test checks its own non-determinism watchlist against honest-check's and the two tools trap exactly the same calls
    And it returns true when name matches any entry and false when it matches none
    But it reads nothing, opens nothing, executes nothing, and raises nothing
  Scenario: diagnostic is part of the split check_source rule engine
    Given a parsed source and its check context
    When diagnostic is called
    Then diagnostic: a helper of the split check_source rule engine (section 3.4).

  Scenario: literal_string is part of the split check_source rule engine
    Given a parsed source and its check context
    When literal_string is called
    Then The Python string a `string` node spells, quotes stripped.

  Scenario: string_members is part of the split check_source rule engine
    Given a parsed source and its check context
    When string_members is called
    Then The string values a set/list/tuple node holds, in source order.

  Scenario: call_arguments is part of the split check_source rule engine
    Given a parsed source and its check context
    When call_arguments is called
    Then The (positional nodes, keyword name -> value node) of a call.

  Scenario: import_aliases is part of the split check_source rule engine
    Given a parsed source and its check context
    When resolve_aliases is called
    Then Map each local name bound by a honest_type import to its canonical constructor name (section 3.3), so a call under an alias resolves to the real constructor.

  Scenario: canonical_name is part of the split check_source rule engine
    Given a parsed source and its check context
    When canonical_name is called
    Then The constructor name a call resolves to, or None when the call is not a framework constructor. A direct constructor-name call counts, and an aliased one resolves through the import (section 3.3).

  Scenario: base_types_of is part of the split check_source rule engine
    Given a parsed source and its check context
    When base_types_of is called
    Then The base-type map of a vocabulary's first argument: name -> (kind, payload). kind is 'set' with a frozenset of members, or 'predicate' with the recognizer's value node (a lambda or any other opaque recognizer honest-check cannot run). HC009

  Scenario: predicate_is_risky is part of the split check_source rule engine
    Given a parsed source and its check context
    When predicate_is_risky is called
    Then True when a predicate's expression holds a node that throws on a non-matching input (§HC009): a call to bare `int` or `float`, a subscript access, or a `/` or `//` division. A predicate that throws is a recognizer that rejects by exception 

  Scenario: enclosing_function is part of the split check_source rule engine
    Given a parsed source and its check context
    When enclosing_function is called
    Then The nearest enclosing function_definition of a node, climbing parents, or None at module scope. A node's nearest enclosing function is the scope that owns it, so a nonlocal or a mutation reads as belonging to the function it sits directly i

  Scenario: underscore_self_name is part of the split check_source rule engine
    Given a parsed source and its check context
    When underscore_self_name is called
    Then The attribute name of a `self._name` assignment target whose name starts with an underscore, or None when the target is not that shape (§HC-P007).

  Scenario: called_name is part of the split check_source rule engine
    Given a parsed source and its check context
    When called_name is called
    Then The name a call invokes — a bare identifier, or the final attribute of a dotted call such as `window.addEventListener` — or None (§HC-P011).

  Scenario: own_body is part of the split check_source rule engine
    Given a parsed source and its check context
    When own_body is called
    Then The body descendants belonging to a function itself, not descending into a deeper nested def, lambda or decorated def — those statements are the inner scope's own (§4.2). A `nonlocal` and a mutation count only where they sit directly in thi

  Scenario: nonlocal_names is part of the split check_source rule engine
    Given a parsed source and its check context
    When nonlocal_names is called
    Then The names declared by the `nonlocal` statements directly in a function body.

  Scenario: decorators_of is part of the split check_source rule engine
    Given a parsed source and its check context
    When decorators_of is called
    Then The decorator nodes applied to a function — the `decorator` children of the enclosing `decorated_definition`, or an empty list for an undecorated function. The boundary signal HC-P002, HC-P004 and HC-P005 read, and the cache signal HC-P006 

  Scenario: decorator_expression is part of the split check_source rule engine
    Given a parsed source and its check context
    When decorator_expression is called
    Then The expression a decorator applies — the identifier, attribute or call after the `@`. A parsed decorator always carries that expression as its first named child.

  Scenario: decorator_target is part of the split check_source rule engine
    Given a parsed source and its check context
    When decorator_target is called
    Then The final name a decorator names — `boundary` from `@boundary`, `lru_cache` from `@functools.lru_cache(maxsize=1)` — or None when it is neither a plain nor a dotted name, called or bare (§4.2, §5.6).

  Scenario: is_boundary_decorator is part of the split check_source rule engine
    Given a parsed source and its check context
    When is_boundary_decorator is called
    Then True when a decorator declares its function a boundary — `@boundary` (bare or called) or `@link(boundary=True)` (§4.2).

  Scenario: in_non_boundary_function is part of the split check_source rule engine
    Given a parsed source and its check context
    When in_non_boundary_function is called
    Then True when a node's nearest enclosing function exists, carries no boundary decorator, and the declaration gives its name no door role — the scope HC-P002, HC-P004 and HC-P005 fire in (§4.2, §5.4, §5.5). A node at module scope, or in a bounda

  Scenario: is_immutable_value is part of the split check_source rule engine
    Given a parsed source and its check context
    When is_immutable_value is called
    Then True when a module-level binding's right side is provably immutable (§5.4, §872): a number, a string, a bool, None, a tuple literal, a negated immutable, or a `frozenset(...)` call. Everything else — a list, dict or set literal, a comprehen

  Scenario: module_mutable_globals is part of the split check_source rule engine
    Given a parsed source and its check context
    When module_mutable_globals is called
    Then The module-level names bound to a mutable (or not provably immutable) value — the globals a read of which makes a link impure (§5.4, §872). A name bound to an immutable value, and an imported or def/class name (never an assignment target), 

  Scenario: param_names is part of the split check_source rule engine
    Given a parsed source and its check context
    When param_names is called
    Then The names a single parameter node binds — a bare identifier, or the `name` of a typed or defaulted parameter. A splat or other shape binds nothing here.

  Scenario: link_locals is part of the split check_source rule engine
    Given a parsed source and its check context
    When link_locals is called
    Then The names local to a link — its parameters plus the names it assigns in its own body. A read of one of these is not a read of a module global (§5.4).

  Scenario: is_attribute_suffix is part of the split check_source rule engine
    Given a parsed source and its check context
    When is_attribute_suffix is called
    Then True when an identifier is the attribute part of an `x.name` access — the `.name`, not a read of `name` itself. Reading `config.timeout` reads `config`, not a global called `timeout` (§5.4).

  Scenario: is_keyword_name is part of the split check_source rule engine
    Given a parsed source and its check context
    When is_keyword_name is called
    Then True when an identifier is a keyword argument's name — the `k` in `f(k=v)`, which names a parameter of the callee, not a global read (§5.4).

  Scenario: watched is part of the split check_source rule engine
    Given a parsed source and its check context
    When watched is called
    Then True when a call's dotted target is on a watch list: an exact entry matches by equality, and an entry carrying a `*` matches as a glob — a trailing `.*` names any attribute of a module, a trailing `*` is a prefix, a `*` between dots is one 

  Scenario: dispatch_variable is part of the split check_source rule engine
    Given a parsed source and its check context
    When dispatch_variable is called
    Then The variable name an `if`/`elif` condition dispatches on — the left identifier of an `identifier == <value>` equality test — or None when the condition is not that shape (§HC-P001).

  Scenario: within_class_init is part of the split check_source rule engine
    Given a parsed source and its check context
    When within_class_init is called
    Then True when a node's nearest enclosing function is an `__init__` that is a method of a class — the scope HC-P007 reads for hidden instance state (§4.2).

  Scenario: mutated_names is part of the split check_source rule engine
    Given a parsed source and its check context
    When mutated_names is called
    Then The names an assignment or augmented assignment targets directly in a function body — the left of each `x = ...` or `x += ...` whose target is a plain identifier.

  Scenario: is_empty_default is part of the split check_source rule engine
    Given a parsed source and its check context
    When is_empty_default is called
    Then True when a parameter's default stands for absence rather than a baked-in value (§HC-P015): None, False, a zero number, an empty string, an empty list/dict/tuple literal, or an empty-constructor call. A populated literal, a non-zero number,

  Scenario: dotted_target is part of the split check_source rule engine
    Given a parsed source and its check context
    When dotted_target is called
    Then The dotted name a call invokes — `open`, `os.system`, `requests.get`, `urllib.request.urlopen` — or None when the target is not a plain or dotted name, such as a call on a call's result (§5.4).

  Scenario: link_is_impure is part of the split check_source rule engine
    Given a parsed source and its check context
    When link_is_impure is called
    Then True when a link's own body calls a watched function or reads a module-level mutable global (§HC008). The body search does not descend into a nested def or lambda, whose statements are that inner scope's own.

  Scenario: is_link_decorated is part of the split check_source rule engine
    Given a parsed source and its check context
    When is_link_decorated is called
    Then True when a function carries a `@link` decorator, bare or called — the chain-link declaration HC008 and HC001 both read for a declared link (§HC008, §4.2).

  Scenario: local_function_links is part of the split check_source rule engine
    Given a parsed source and its check context
    When local_function_links is called
    Then Each function defined in this file, mapped to whether it carries a `@link` decorator (§4.2, HC001). A chain positional that resolves to one of these names is a local link declaration honest-check can read; a name not here is defined elsewhe

  Scenario: is_orchestrator is part of the split check_source rule engine
    Given a parsed source and its check context
    When is_orchestrator is called
    Then True when a function carries an `@orchestrator` decorator, bare or called — matched by decorator name the same way a boundary decorator is (§4.2, HC-OR001).

  Scenario: longest_shared_run is part of the split check_source rule engine
    Given a parsed source and its check context
    When longest_shared_run is called
    Then The length of the longest run of consecutive equivalent call names two call sequences share (§HC-OR003). A contiguous common substring over the two lists, found by the standard row-by-row dynamic program; 0 when they share no adjacent run.

  Scenario: link_declares_emits is part of the split check_source rule engine
    Given a parsed source and its check context
    When link_declares_emits is called
    Then True when a function carries a `@link` decorator that passes an `emits` keyword — the emits vocabulary HC-P017 requires of an HTTP-producing link (§HC-P017). Read the same way is_boundary_decorator reads `boundary`: from the decorator call'

  Scenario: construction_maps is part of the split check_source rule engine
    Given a parsed source and its check context
    When construction_maps is called
    Then Each file-local variable bound to a `vocabulary(...)` or a `binding(...)` call, mapped to that construction call node (§HC004, §HC005). A name bound to anything else is not here; a name honest-check cannot resolve to one of these two constr

  Scenario: features_vocabulary is part of the split check_source rule engine
    Given a parsed source and its check context
    When features_vocabulary is called
    Then The feature-flag vocabulary this module declares: each flag name mapped to the set of states its `FEATURES[flag]["states"]` set names (§7, HC-HF001/HC-HF002). Read only from a module-scope `FEATURES = {...}` dict literal — the same top-leve

  Scenario: feature_state_flag is part of the split check_source rule engine
    Given a parsed source and its check context
    When feature_state_flag is called
    Then The flag a `feature_state(state, "flag")` call names — its second positional, a string literal — or None when the call names fewer than two positionals or a dynamic (non-literal) flag (§7). The call is resolved by name through called_name.

  Scenario: module_dict_literals is part of the split check_source rule engine
    Given a parsed source and its check context
    When module_dict_literals is called
    Then Each module-scope name bound to a dict literal, mapped to the set of string keys the literal declares (§7, HC-HF002). A name bound to anything but a module-scope dict literal is not here, so a handler table that resolves to no such name is 

  Scenario: vocabulary_types is part of the split check_source rule engine
    Given a parsed source and its check context
    When vocabulary_types is called
    Then The type surface of a `vocabulary(...)` call: its base-type names, its composed-type names, the base names its composed types require, and the base names its composed types capture (§HC004, §HC005). base_types_of reads the first-argument di

  Scenario: binding_keys is part of the split check_source rule engine
    Given a parsed source and its check context
    When binding_keys is called
    Then The type names a `binding(...)` call binds — the keys of its first-argument table (§HC004, §HC005).

  Scenario: vocabulary_binding_pairs is part of the split check_source rule engine
    Given a parsed source and its check context
    When vocabulary_binding_pairs is called
    Then Each (vocabulary calls, binding call) a classify or link pairs by name (§HC004, §HC005). A `classify(tokens, vocab, bind=b)` pairs positional 2 with the `bind` keyword, and its vocabulary list is the one vocab. A `link(accepts=v, emits=e, b

  Scenario: check_construction is part of the split check_source rule engine
    Given a parsed source and its check context
    When check_construction is called
    Then Construction-time rules (section 4.1): HC001/HC003/HC006/HC007/HC011 and the HC-SM rules, dispatched by the framework constructor each call site resolves to. The per-rule logic nests here as data; ctx carries the parse.

  Scenario: check_per_file is part of the split check_source rule engine
    Given a parsed source and its check context
    When check_per_file is called
    Then Per-file rules (section 4.2): the HC-P purity rules, the HC chain/link rules, and the HC-HF feature rules, folded over the declaration graph. The per-rule logic nests here as data; ctx carries the parse.

  Scenario: apply_suppression is part of the split check_source rule engine
    Given a parsed source and its check context
    When apply_suppression is called
    Then Apply inline/file suppression to the raw diagnostics (section 7): downgrade a suppressed finding to info, and flag a directive that suppressed nothing (HC-SUP001) or carries no reason (HC-SUP002). The directive parsers nest here; ctx carrie

  Scenario: _canonical_name resolves a call to its framework constructor name
    Given a call node and the import-alias map
    When _canonical_name is called
    Then it returns the constructor name the call resolves to through the alias map, or NOTHING when the call is not a recognized construction

  Scenario: _constructor_assignments finds module-level name = constructor(...) assignments
    Given the parsed root, the alias map, and a constructor name
    When _constructor_assignments is called
    Then it returns the (call, target-name) pairs for each module-level assignment whose right side is that constructor, in source order

  Scenario: _positional_identifiers reads a call's positional identifier arguments
    Given a call node
    When _positional_identifiers is called
    Then it returns the identifier names of the call's positional arguments in source order, skipping keyword and non-identifier arguments

  Scenario: _first_child_of_type returns the first named child of a given type
    Given a node and a type name
    When _first_child_of_type is called
    Then it returns the first named child whose type matches, or NOTHING when the node has none

  Scenario: _is_interpolated detects a dynamic class value
    Given a class attribute value text
    When _is_interpolated is called
    Then it returns whether the value carries a jinja interpolation marker, making it dynamic and skipped whole

Feature: honest-test — generated, one scenario per function (61 total)

  Scenario: run_cli opens the CLI door and drives the whole run
    Given src_dir: str
    When run_cli is called
    Then it is the CLI door the host starts with `python -m honest_test [src_dir]`, hands src_dir to run_suite which drives the whole run, and returns what run_suite returned: the assembled RunReport on a completed run, or the Fault run_suite passed outward when the module source could not be parsed for mutation
    And it opens no file itself — the orchestrator's readers do the filesystem reads, and the sinks that print the report and write coverage.json run inside run_suite
    And it raises nothing: a run that could not complete comes back as a Fault for the host to discharge as a non-zero exit

  Scenario: check_test_body refuses a test body that rebinds a call target
    Given collector: handle
    When check_test_body is called
    Then it is the pytest plugin's collection-time hook, reads the collected test module's source through the injected collector, hands that source to run_body_check for the pure verdict, and returns the list of rejections the verdict produced
    And it raises collection_failure when that list is non-empty, naming each rebinding site, so a dishonest test body does not run; an empty list means the module collected clean
    And its one side effect is reading the collected module's source file

  Scenario: read_source pulls one source file's text from disk
    Given path: str
    When read_source is called
    Then it pulls one file's complete text from disk and returns it as a string, doing nothing else — it does not parse, generate or write
    And path is the filesystem path of one source file under src/, already resolved by discovery at the run boundary
    And its one side effect is reading the filesystem

  Scenario: load_under_test imports each module to obtain its live declarations
    Given src_dir: str
    When load_under_test is called
    Then it imports each module under test and returns a LiveModules record carrying the live vocabularies, bindings, links, link declarations, chains, state machines, schemas, components, providers and gates for the orchestrator to thread into the checks that must call real functions
    And loading runs each module's own top-level code, so it is a boundary: its side effects are reading the filesystem, reading the import system of the running process, and the honest-type seam (link_meta, is_link, vocabulary) that tells a link from an ordinary function and reads its declared vocabulary and binding

  # hd: python/honest-test/honest-test.hd::load_under_test
  # spec: Honest Test §11 (as cited by the declaration)
  Scenario: load_under_test reloads identical stems from the selected source directory
    Given src_dir: str is first one source directory and then a different one, each containing a module of the same stem with a distinct live declaration and a sibling that eagerly imports it
    And the original search-path object and unrelated cached module are observable before each load
    When load_under_test is called for each directory
    Then each LiveModules record contains the live declaration from its selected directory rather than that of the other directory
    And each eager sibling import sees the very same live module instance selected for that invocation
    And the original sys.path object and contents and the unrelated module binding are restored after each load

  # hd: python/honest-test/honest-test.hd::load_under_test
  # spec: Honest Test §11 (as cited by the declaration)
  Scenario: load_under_test restores process import state after a failed import
    Given src_dir: str contains a selected module whose top-level code throws during import
    And the process already holds a module binding of the same stem from another directory, an unrelated cached module, and its original sys.path object and contents
    When load_under_test is called and the selected import fails
    Then the original binding for the same stem and the unrelated module binding retain their original identities
    And the original sys.path object and contents are restored

  Scenario: read_config reads honest-test.toml and decodes it to a plain table
    Given path: str
    When read_config is called
    Then it reads honest-test.toml once at the start of a run and returns the decoded TOML as a plain map of maps, building no record and resolving nothing; the table is empty when no honest-test.toml exists
    And the resolution into the SuppliedConfig record is resolve_supplied_config, called after this pull
    And its one side effect is reading the filesystem

  Scenario: resolve_supplied_config reshapes the decoded table into the supplied-values record
    Given table: dict<str, any>
    When resolve_supplied_config is called
    Then it resolves the decoded honest-test.toml table into a SuppliedConfig: a map from each predicate name to its SuppliedEntry — the predicate's valid list, its invalid list, and its strategy (supplied_only or fibonacci)
    And it is the empty map when the table declares no predicates
    And it reads no world and returns pure data; the supplied values entered at the boundary in read_config and this function only reshapes them

  Scenario: read_template reads one shipped step-library template file
    Given path: str
    When read_template is called
    Then it reads one shipped step-library template file's complete text from honest-test's package and returns it as a string, so run_suite can write it into the adopter's scaffolding directory; it does not generate, resolve or write
    And path is the filesystem path of one shipped template file — the §8.4 protocol-assertion step library and the §8.6 value-assertion step library are each such a file
    And its one side effect is reading the filesystem

  Scenario: run_mutant_suite runs one source through the conformance suite out of process
    Given source: str
    When run_mutant_suite is called
    Then it launches a subprocess bounded in time and in memory, runs the module's conformance suite against the given source, and returns a MutantObservation: the suite's observed output as text and whether the run finished inside the bound
    And the mutant runs out of process, never inline, because an infinite-loop mutant must not run in honest-test's own process — a prior inline run reached 35 GB before it was killed
    And its one side effect is reaching into the running process's subprocesses; judging what it observed is classify_mutant_result's pure work

  Scenario: run_suite drives the whole CLI run from source directory to report
    Given src_dir: str
    When run_suite is called
    Then it pulls the decoded config once with read_config and resolves it with resolve_supplied_config, loads the modules under test once with load_under_test, then drives the pure core: parse and classify predicates, run the matching generators, enumerate sets and adversarial neighbors over the live declarations, run the honesty checks, chain contracts, auth, gate, state-machine, persist and component-isolation checks, mutate the source and judge each mutant out of process, generate and write scaffolding, build and emit each proof event, measure and assemble coverage, assemble and render the RunReport, print it to stdout and write coverage.json
    And it returns the assembled RunReport on a completed run, or the Fault mutate_source answers when the module source does not parse, passing it outward to the door rather than swallowing it
    And the value-oracle engine (evaluate_case) is not driven here: a sibling module's conformance runner enters it through its own door

  Scenario: run_body_check runs the test-body verdict over one collected module's source
    Given source: str
    When run_body_check is called
    Then it takes the one test module's source text the collection door read, runs test_body_violations over it, and returns the rejections for the door to act on, empty when the test body is honest
    And it holds the collection path's single decision — run the verdict over the source — and nothing else: it reads no world, keeps no state, and composes no other orchestrator

  # hd: python/honest-test/honest-test.hd::run_body_check
  Scenario: run_body_check reports runtime rebinding in supplied source
    Given source: str is a complete Python test module containing one runtime rebinding of an imported call target
    When run_body_check is called
    Then it returns the rejection for that statement with the rebinding location and the injection correction

  # hd: python/honest-test/honest-test.hd::parse_source
  Scenario: parse_source returns a recovered Python root for malformed source
    Given source: str is a malformed Python module with parser recovery descendants
    When parse_source is called
    Then it returns its recovered Python root with the recovery descendants available to the caller

  # hd: python/honest-test/honest-test.hd::parse_source
  Scenario: parse_source returns a Python root for UTF-8 source
    Given source: str is a syntactically valid Python module containing a non-ASCII literal
    When parse_source is called
    Then it returns the Python root for the UTF-8 encoding of the complete source

  # hd: python/honest-test/honest-test.hd::body_findings
  Scenario: body_findings reports one rejection per runtime rebinding
    Given root: Node is the recovered Python root for a test module containing runtime rebinding statements and unrelated statements
    When body_findings is called
    Then it returns one Finding for each runtime rebinding statement, carrying its location and the correction to pass the dependency as a parameter or inject a boundary plug

  # hd: python/honest-test/honest-test.hd::body_findings
  Scenario: body_findings returns empty for an honest test body
    Given root: Node is the Python root for a test module without runtime rebinding
    When body_findings is called
    Then it returns an empty list

  # hd: python/honest-test/honest-test.hd::test_body_violations
  Scenario: test_body_violations returns one rejection per runtime rebinding
    Given source: str
    When test_body_violations is called
    Then it returns one rejection Finding per statement that rebinds a call target at runtime: a monkeypatch fixture (setattr, setitem, delattr, setenv), a mock.patch or patch.object or an installed Mock, a setattr on an imported module, class or function, or an imported symbol rebound by attribute assignment, each carrying the rebinding site's location and the fix
    And the framework's own record-and-restore boundary instrumentation (io_monitor, call_monitor) is not a violation and never appears here, because it lives in framework code, not a test body, and restores the original
    And an empty list means the test body is honest; it reads nothing and raises nothing

  Scenario: print_report writes the rendered report text to stdout
    Given text: str
    When print_report is called
    Then it writes the already-rendered report text to standard output and does nothing else — no formatting, no decision; text is the finished report string render_report produced
    And it returns nothing; its one side effect is writing stdout

  Scenario: write_coverage writes the report's coverage as coverage.json
    Given report: RunReport
    When write_coverage is called
    Then it writes the report's CoverageReport as coverage.json, the file honest-check reads for HC-P009 and other cross-tool checks, making no decision because the coverage numbers are already measured
    And it returns nothing; its one side effect is writing the file

  Scenario: write_scaffolding writes one do-not-edit scaffolding file
    Given path: str and source: str
    When write_scaffolding is called
    Then it writes one do-not-edit scaffolding file into the configured scaffolding directory — the chain step module generate_scaffolding produced, or a shipped standard step-library template read_template read — making no decision because the source is already produced
    And path is the file to write under scaffolding_dir and source is the finished scaffolding text; the developer writes .feature files against these files and never edits them
    And it returns nothing; its one side effect is writing the file

  Scenario: emit_proof_event emits one proof event through the injected observe runtime
    Given event: ProofEvent and runtime: Callable
    When emit_proof_event is called
    Then it emits one hf.proof.checked event through honest-observe's emit and does nothing else, making no decision because the event is already built
    And runtime is the observe emit injected as a Callable so honest-test's core takes no import dependency on honest-observe; a pure local run with no runtime wired emits nothing
    And it returns nothing; its one side effect is writing to honest-observe through the injected runtime

  Scenario: parse_source parses one source file with tree-sitter
    Given source: str
    When parse_source is called
    Then it parses one source file's text with tree-sitter and returns the tree's root node, which extract_predicates walks for predicate nodes and mutate_source walks for the spans each change sits at
    And the parse is deterministic and reads no world; tree-sitter produces a tree with error nodes for malformed input rather than failing, so it returns a node, never a fault

  Scenario: extract_predicates returns the node of each recognizer predicate
    Given tree: Node
    When extract_predicates is called
    Then it walks a parsed source tree and returns one node per recognizer predicate found, each the body honest-test analyzes; an empty list means the file declares no predicates
    And it reads no world and returns pure data

  # hd: python/honest-test/honest-test.hd::extract_predicates
  # spec: Honest Test §2 (as cited by the declaration)
  Scenario: extract_predicates selects recognizers from a mixed source file
    Given tree: Node is the parsed root of a source file containing plain function plain, a function named step marked as a link, and functions first and second marked as recognizers
    When extract_predicates is called
    Then it returns exactly the two recognizer predicate nodes that belong to first and second

  Scenario: classify_predicate sorts one predicate into its generation class
    Given predicate_node: Node
    When classify_predicate is called
    Then it reads the node for the markers that decide the class and returns exactly one PredicateClass: numeric for int()/float()/a numeric comparison, length_bounded for a len(s) comparison, character_class for s.isdigit()/s.isalpha()/s.isupper(), external_lookup for a call to a function not in the codebase, composite for a call to a codebase-defined function (recursing into the callee at any depth), and catch_all for a predicate accepting nearly all inputs
    And it reads no world and returns pure data

  # hd: python/honest-test/honest-test-pure.hd::classify_predicate
  # spec: Honest Test §2 (as cited by the declaration)
  Scenario: classify_predicate selects generation classes for declared syntax markers
    Given predicate_node: Node is the parsed body of each of these predicates
      | expression                         | class           |
      | int(s)                             | numeric         |
      | float(s)                           | numeric         |
      | s > 1                              | numeric         |
      | s > 1.5                            | numeric         |
      | 1e3 < s                            | numeric         |
      | len(s) < 5                         | length_bounded  |
      | len(s) < 1.5                       | length_bounded  |
      | s.isdigit()                        | character_class |
      | s.isalpha()                        | character_class |
      | s.isupper()                        | character_class |
      | external_lookup_api(s)             | external_lookup |
      | external_lookup_api(s) > threshold | external_lookup |
    And external_lookup_api is not defined in the codebase and threshold has no declared numeric value
    When classify_predicate is called
    Then it returns the given class for each predicate

  Scenario: enumerate_lengths generates the strings for a length-bounded predicate
    Given predicate_node: Node
    When enumerate_lengths is called
    Then it reads the minimum and maximum length from the comparison operators (distinguishing == from <= from <) and returns a LengthCases: one valid string at every length in the range, and the invalid boundary lengths just outside — one over the maximum always, one under the minimum when the minimum exceeds one
    And a pure lower bound with no maximum is unbounded above and falls to supplied values rather than generating here
    And it reads no world and returns pure data

  # hd: python/honest-test/honest-test-pure.hd::enumerate_lengths
  # spec: Honest Test §3.4 (as cited by the declaration)
  Scenario: enumerate_lengths returns valid lengths and adjacent rejection boundaries
    Given predicate_node: Node is the parsed body for each length comparison
      | expression      | valid lengths | invalid lengths |
      | len(s) == 5     | 5             | 4, 6            |
      | len(s) <= 8     | 1 through 8   | 9               |
      | len(s) < 8      | 1 through 7   | 8               |
      | 3 <= len(s) <= 8 | 3 through 8   | 2, 9            |
      | 2 <= len(s) <= 3 | 2 through 3   | 1, 4            |
      | 3 < len(s) < 8   | 4 through 7   | 3, 8            |
      | len(s) == 37    | 37            | 36, 38          |
    When enumerate_lengths is called
    Then it returns a LengthCases record whose valid and invalid lists contain one string at each of their respective specified lengths
    And a string longer than the alphabet is generated by repeating it

  # hd: python/honest-test/honest-test-pure.hd::enumerate_lengths
  # spec: Honest Test §§3.4 and 3.6 (as cited by the declaration)
  Scenario: enumerate_lengths generates no local cases for an unbounded upper range
    Given predicate_node: Node is the parsed body for "len(s) >= 3" or "len(s) > 3", with no maximum
    When enumerate_lengths is called
    Then it returns a LengthCases record with both lists empty so the supplied-values route can provide cases

  Scenario: fibonacci_sequence generates the numeric probe values
    Given limit: int and negative: bool
    When fibonacci_sequence is called
    Then it returns the Fibonacci sequence from zero up to limit — the negatives followed by the non-negatives when negative is true, the non-negatives alone otherwise — giving logarithmically distributed values dense among small numbers and spaced among large ones
    And limit is the ceiling whose documented default is 1,000,000 and for a float predicate each value is divided by 100
    And it probes a numeric range rather than enumerating it, reads no world and returns pure data

  Scenario: supplied_cases resolves one predicate's programmer-supplied values
    Given predicate_name: str and supplied_values: SuppliedConfig
    When supplied_cases is called
    Then it returns a SuppliedCases carrying that predicate's valid and invalid values when the config has an entry, and missing true with empty lists when it does not — the case the runner turns into a missing_supplied_values warning rather than passing over
    And it reads no file: the supplied values entered through read_config at the boundary, and it reads only the record it was handed; it returns pure data

  Scenario: enumerate_sets generates every test case for a Set-based vocabulary
    Given vocab: Vocabulary
    When enumerate_sets is called
    Then it enumerates every member of every Set recognizer and produces the Cartesian product, no sampling — a vocabulary of three Sets of 5, 150 and 4 members yields all 3,000 cases — each case a manifest mapping each Set slot's name to its chosen member
    And a Maybe slot adds its absent arm, so a Maybe Set of 4 members yields 5; a predicate recognizer contributes no slot and a vocabulary of only predicate recognizers enumerates to one empty manifest
    And it reads no world and returns pure data

  # hd: python/honest-test/honest-test.hd::invoke_probe
  Scenario: invoke_probe returns the callback answer unchanged
    Given function: Callable records its received object and returns a known object, and argument: any is an object kept by the caller
    When invoke_probe is called
    Then the callback receives the identical argument once and the returned object is the identical callback answer

  # hd: python/honest-test/honest-test.hd::invoke_probe
  Scenario: invoke_probe leaves an awaitable answer untouched
    Given function: Callable returns an awaitable and argument: any is its input
    When invoke_probe is called
    Then it returns the identical awaitable without awaiting it

  # hd: python/honest-test/honest-test.hd::invoke_probe
  Scenario: invoke_probe propagates a callback exception
    Given function: Callable raises an exception for argument: any
    When invoke_probe is called
    Then that exception propagates

  # hd: python/honest-test/honest-test.hd::purity_findings
  Scenario: purity_findings reports different answers
    Given first: any is 1 and second: any is 2
    When purity_findings is called
    Then it returns one failure with code non_deterministic

  # hd: python/honest-test/honest-test.hd::purity_findings
  Scenario: purity_findings returns no finding for equal answers
    Given first: any is 1 and second: any is 1
    When purity_findings is called
    Then it returns an empty list

  # hd: python/honest-test/honest-test.hd::mutation_findings
  Scenario: mutation_findings reports a changed manifest
    Given before: Manifest contains count 1 and after: Manifest contains count 2
    When mutation_findings is called
    Then it returns one failure with code manifest_mutated containing the before and after representations

  # hd: python/honest-test/honest-test.hd::mutation_findings
  Scenario: mutation_findings returns no finding for equal manifests
    Given before: Manifest and after: Manifest both contain count 1
    When mutation_findings is called
    Then it returns an empty list

  # hd: python/honest-test/honest-test.hd::idempotency_findings
  Scenario: idempotency_findings reports different answers
    Given first: any is 1 and second: any is 2
    When idempotency_findings is called
    Then it returns one failure with code not_idempotent

  # hd: python/honest-test/honest-test.hd::idempotency_findings
  Scenario: idempotency_findings returns no finding for equal answers
    Given first: any is 1 and second: any is 1
    When idempotency_findings is called
    Then it returns an empty list

  # hd: python/honest-test/honest-test.hd::run_purity_check
  Scenario: run_purity_check uses a fresh copy for each call
    Given link: Callable records its input and mutates a nested value before returning it, and test_manifest: Manifest has that nested value
    When run_purity_check is called
    Then it calls the same link twice in order with independently copied input from the original manifest and leaves the original unchanged

  # hd: python/honest-test/honest-test.hd::run_mutation_check
  Scenario: run_mutation_check passes the original and detects its change
    Given link: Callable changes a nested value in its argument and test_manifest: Manifest contains that value
    When run_mutation_check is called
    Then it calls the link once with the original object and returns a manifest_mutated failure comparing the changed original with the saved deep copy

  # hd: python/honest-test/honest-test.hd::run_idempotency_check
  Scenario: run_idempotency_check uses a fresh deep copy for each call
    Given chain: Callable records its input and mutates a nested value before returning it, and test_manifest: Manifest has that nested value
    When run_idempotency_check is called
    Then it calls the chain twice in order with fresh, independent deep copies of the original manifest and compares the two answers

  # hd: python/honest-test/honest-test.hd::read_monitored_link
  Scenario: read_monitored_link passes the supplied link and manifest unchanged
    Given monitor: Callable records its inputs and returns a watched-call record, link: Callable is the link to monitor, and test_manifest: Manifest is the original object
    When read_monitored_link is called
    Then it calls the monitor once with the identical link and manifest and returns its watched-call record

  # hd: python/honest-test/honest-test.hd::read_monitored_link
  Scenario: read_monitored_link propagates monitor exceptions
    Given monitor: Callable raises an exception for the supplied link: Callable and test_manifest: Manifest
    When read_monitored_link is called
    Then the exception propagates

  # hd: python/honest-test/honest-test.hd::monitor_findings
  Scenario: monitor_findings reports watched calls from a non-boundary link
    Given link: Callable has non-boundary link metadata, record: list<str> contains a watched call, and kind: str is either nondeterminism, io or unrecognized
    When monitor_findings is called
    Then it returns a warning carrying the recorded calls, with code nondeterminism_detected for nondeterminism or io_detected for the other two kinds

  # hd: python/honest-test/honest-test.hd::monitor_findings
  Scenario: monitor_findings allows boundary links and empty records
    Given link: Callable is marked as a boundary or record: list<str> is empty, and kind: str selects a check
    When monitor_findings is called
    Then it returns an empty list

  # hd: python/honest-test/honest-test.hd::run_monitor_check
  Scenario: run_monitor_check judges the original manifest monitor record
    Given link: Callable has non-boundary metadata, test_manifest: Manifest is the original object, monitor: Callable records a watched call, and kind: str is unrecognized
    When run_monitor_check is called
    Then it asks the monitor once to observe the link with the original manifest and returns its io_detected warning

  # hd: python/honest-test/honest-test.hd::server_rejection
  Scenario: server_rejection recognizes only server-category faults
    Given answer: any is a downstream answer
    When server_rejection is called
    Then it returns true for a server-category fault and false for a non-server fault or a successful value

  # hd: python/honest-test/honest-test.hd::chain_contract_findings
  Scenario: chain_contract_findings reports a failed join only for server rejection
    Given rejected: bool records whether the downstream answer was a server rejection
    When chain_contract_findings is called
    Then it returns a single chain_contract failure for true and an empty list for false

  # hd: python/honest-test/honest-test.hd::run_chain_contract_check
  Scenario: run_chain_contract_check skips upstream faults and reports downstream server rejection
    Given links: list<Callable> contains adjacent links, vocab: Vocabulary and binding: Binding produce case manifests, and across the cases the upstream returns either a fault or a value passed to a downstream link that can return a server fault, another fault, or a successful value
    When run_chain_contract_check is called
    Then it skips the downstream call on upstream faults and returns a chain_contract failure only for a downstream server fault

  # hd: python/honest-test/honest-test.hd::auth_probe_mode
  Scenario: auth_probe_mode selects the mode for each token class
    Given token_class: TokenClass is one of valid, malformed, revoked, expired, missing or forged
    When auth_probe_mode is called
    Then it returns valid for valid, malformed for malformed, and faulting for revoked, expired, missing and forged

  # hd: python/honest-test/honest-test.hd::auth_probe_findings
  Scenario: auth_probe_findings accepts sound observations for each mode
    Given token_class: TokenClass and mode: str identify a probe, accepted: bool and resolved: any record its outcomes, and fault_mapping: dict<str, int> and expected: int describe the expected outcome
    When auth_probe_findings is called
    Then it returns no findings when a malformed token is rejected, a valid token is accepted and resolves ok, or an accepted faulting token resolves to a fault whose category maps to the expected status

  # hd: python/honest-test/honest-test.hd::auth_probe_findings
  Scenario: auth_probe_findings reports observations that violate the mode contract
    Given token_class: TokenClass and mode: str identify a probe, accepted: bool and resolved: any record an observation that violates that mode, and fault_mapping: dict<str, int> and expected: int describe the expected outcome
    When auth_probe_findings is called
    Then it returns the auth_honesty failure for that class

  # hd: python/honest-test/honest-test.hd::run_auth_honesty_check
  Scenario: run_auth_honesty_check probes token classes in order and resolves only eligible tokens
    Given provider: AuthProvider supplies token generation, recognition, resolution, and expected statuses
    When run_auth_honesty_check is called
    Then it probes valid, malformed, revoked, expired, missing, and forged in that order, generates and recognizes each token once, and resolves only accepted non-malformed tokens

  # hd: python/honest-test/honest-test.hd::run_auth_honesty_check
  Scenario: run_auth_honesty_check propagates unexpected callback errors
    Given provider: AuthProvider supplies a callback that raises an unexpected error during a probe
    When run_auth_honesty_check is called
    Then the unexpected error propagates

  # hd: python/honest-test/honest-test.hd::read_schema_probe
  Scenario: read_schema_probe returns real probe outcomes in contract order
    Given table_name: str names the declared table, table: any describes it, and connect: Callable opens a fresh injected real database where setup succeeds
    When read_schema_probe is called
    Then it returns attempted outcomes in round-trip, undeclared-column, first non-primary required field when present, and empty-set order

  # hd: python/honest-test/honest-test.hd::read_schema_probe
  Scenario: read_schema_probe propagates fixture setup failures
    Given table_name: str names the declared table, table: any describes it, and connect: Callable is the real database seam but connection or table creation fails
    When read_schema_probe is called
    Then the fixture setup failure propagates

  # hd: python/honest-test/honest-test.hd::run_persist_schema_check
  Scenario: run_persist_schema_check collects ordered findings from fresh databases
    Given schema: Schema declares tables in a given order, and connect: Callable opens a fresh real database for each table
    When run_persist_schema_check is called
    Then it probes the tables in declaration order and translates each table’s observed probe outcomes into findings in probe order

  # hd: python/honest-test/honest-test.hd::read_component_startup
  Scenario: read_component_startup records whether the loader returned
    Given load_component: Callable receives the supplied component: Component and either returns or raises an Exception
    When read_component_startup is called
    Then it calls the loader once with the exact component and returns its name with whether it returned

  # hd: python/honest-test/honest-test.hd::read_component_startup
  Scenario: read_component_startup propagates a non-Exception BaseException
    Given load_component: Callable raises a BaseException outside Exception for the supplied component: Component
    When read_component_startup is called
    Then the BaseException propagates

  # hd: python/honest-test/honest-test.hd::startup_cascade_findings
  Scenario: startup_cascade_findings reports forward failures that passed in reverse
    Given names: list<str> contains the components in original order, reverse: dict<str, bool> records reverse load outcomes, and forward: list<ComponentStartup> records named forward load outcomes
    When startup_cascade_findings is called
    Then it returns one failure for every component that loaded in reverse and failed in forward order, identifying the first earlier forward failure as the trigger when present

  # hd: python/honest-test/honest-test.hd::run_startup_isolation_check
  Scenario: run_startup_isolation_check loads components in reverse then forward order
    Given components: list<Component> gives an original order, and load_component: Callable observes each attempt and may fail
    When run_startup_isolation_check is called
    Then it loads each component once in reverse input order and then once in input order and judges the difference in original component order

  # hd: python/honest-test/honest-test.hd::verify_purity
  Scenario: verify_purity runs a link twice and flags a different result
    Given link: Callable and test_manifest: Manifest
    When verify_purity is called
    Then it runs the link twice on the same manifest and returns a non_deterministic failure when the two results differ, because a pure function must return the same output for the same input; the empty list when the link is pure
    And a link declared a boundary is exempt and is not handed here
    And it performs no I/O of its own; any effect belongs to the injected link

  # hd: python/honest-test/honest-test.hd::detect_mutation
  Scenario: detect_mutation flags a link that modified its input manifest
    Given link: Callable and test_manifest: Manifest
    When detect_mutation is called
    Then it deep-copies the manifest, runs the link, and returns a manifest_mutated failure carrying the diff when the manifest after the run differs from the copy, because a pure function must not modify its input; the empty list when the input was untouched
    And it performs no I/O of its own

  # hd: python/honest-test/honest-test.hd::test_idempotency
  Scenario: test_idempotency flags a chain that is not idempotent
    Given chain: Callable and test_manifest: Manifest
    When test_idempotency is called
    Then it runs the chain twice, the second time on a deep copy of the manifest, and returns a not_idempotent failure when the two results differ; the empty list when the chain is idempotent
    And a chain containing a boundary link is exempt and is not handed here
    And it performs no I/O of its own

  # hd: python/honest-test/honest-test.hd::verify_under_monitor
  Scenario: verify_under_monitor runs a link under the injected monitor
    Given link: Callable and test_manifest: Manifest and monitor: Callable and kind: str
    When verify_under_monitor is called
    Then it runs the link inside the injected monitor and returns a warning when the monitor recorded a watched call and the link is not declared a boundary — io_detected for kind io (boundary isolation, the io_monitor plug) and nondeterminism_detected for kind nondeterminism (the call_monitor plug trapping the non-deterministic watch-list symbols)
    And monitor is injected as a callable so honest-test takes back the record of detected calls, never reaching for a global; the warning reports and does not block
    And it returns the warning as a one-element list, or the empty list

  Scenario: io_monitor records the link's I/O calls while leaving its result unchanged
    Given link: Callable and test_manifest: Manifest
    When io_monitor is called
    Then it is the boundary-isolation monitor (section 4.4), the kind io plug run_suite injects into verify_under_monitor; it runs the link once inside record-and-restore instrumentation that temporarily patches the known I/O functions — open, print, input, and sys.stdout, sys.stderr and sys.stdin — so each records the call it was given, delegates to the real function, and is restored afterward, changing no result, so it is not the runtime rebinding section 4.8 forbids
    And link is the link under test, run once inside the instrumentation, and test_manifest is the one generated input it is run on; it returns the record of detected I/O calls as the list of call names, empty when the link did no I/O, the record verify_under_monitor judges against the link's boundary flag to decide the io_detected warning
    And it raises nothing; its one side effect is reaching into the running process to patch, run and restore — a process-level effect of the same breadth as load_under_test and run_mutant_suite, which is why it is a reader over the running process rather than a pure function

  Scenario: call_monitor records the link's non-deterministic calls while leaving its result unchanged
    Given link: Callable and test_manifest: Manifest
    When call_monitor is called
    Then it is the non-determinism monitor (section 4.5), the kind nondeterminism plug run_suite injects into verify_under_monitor, the parallel reader to io_monitor; it runs the link once inside record-and-restore instrumentation that temporarily patches the non-deterministic watch-list call-forms — time.time, time.monotonic, time.perf_counter, time.time_ns, random.random, random.randint, uuid.uuid4 and os.urandom — so each records the call it was given, delegates to the real function, and is restored afterward, changing no result, so it is not the runtime rebinding section 4.8 forbids
    And link is the link under test, run once inside the instrumentation, and test_manifest is the one generated input it is run on; it returns the record of detected non-deterministic call names as the list, empty when the link called none, the record verify_under_monitor judges against the link's boundary flag to decide the nondeterminism_detected warning
    And by patching the target symbols it catches non-determinism entering through an attribute chain or dynamic dispatch, the dynamic paths static HC008 misses; honest-test carries the trapped call-form subset itself rather than importing honest-check's NONDETERMINISTIC_WATCH_LIST, and its conformance verifies the subset against the published list so the two cannot drift
    And it raises nothing; its one side effect is reaching into the running process to patch, run and restore — a process-level effect of the same breadth as load_under_test and io_monitor, which is why it is a reader over the running process rather than a pure function

  # hd: python/honest-test/honest-test.hd::test_chain_contracts
  Scenario: test_chain_contracts checks each adjacent link join
    Given links: list<Callable> and vocab: Vocabulary and binding: Binding
    When test_chain_contracts is called
    Then for each adjacent pair it enumerates the input cases the upstream link accepts, runs the upstream link, and when that produces an ok manifest feeds it to the downstream link, returning a chain_contract failure when the downstream link rejects that valid output with a server fault
    And a client fault from the downstream link is not a contract failure — only a server fault indicates a broken join
    And it returns one failure per broken join, empty when every join holds; it performs no I/O of its own

  Scenario: enumerate_test_cases builds the input manifests a link accepts
    Given accepts: Vocabulary and binding: Binding
    When enumerate_test_cases is called
    Then it enumerates the vocabulary the way enumerate_sets does and resolves each combination into a manifest through the binding, so each case is a ready input for the link under test, the binding naming the slot each member fills
    And the same Maybe and predicate rules enumerate_sets follows hold here
    And it reads no world and returns pure data

  # hd: python/honest-test/honest-test.hd::test_auth_honesty
  Scenario: test_auth_honesty probes a provider with each token class
    Given provider: AuthProvider
    When test_auth_honesty is called
    Then for each of the six token classes it generates a token with the provider's test_token_generator and asserts the outcome, returning an auth_honesty failure when the provider accepts a malformed token at the recognizer, rejects a valid one, or does not fault correctly for a class
    And a malformed token must be rejected at the provider's actor_recognizer before resolve_actor; a valid token must resolve to ok(actor); every other class must fault with the expected HTTP status compute_expected_status derives
    And it returns one failure per class that behaved wrongly, empty when sound; it performs no I/O of its own

  Scenario: compute_expected_status maps one token class to its expected HTTP status
    Given token_class: TokenClass and fault_mapping: dict<str, int>
    When compute_expected_status is called
    Then it returns the expected status: 401 for revoked, expired, missing and forged (an unauthenticated fault), 400 or the provider's preferred status for malformed (rejected at the recognizer), and the ok path for valid carries no error status
    And the provider may override the default through fault_mapping
    And it reads no world and returns pure data

  Scenario: check_gate_honesty rejects a gate with no proof or an unbound proof
    Given gates: list<Gate>
    When check_gate_honesty is called
    Then it returns a gate_unverified rejection for a gate with no proof-of-failure test, and a gate_proof_unbound rejection for a proof that asserts only that some exception was raised rather than binding the specific failure type and message
    And honest-test never guesses which checks are gates — each gate declares itself; a gate that skips rather than fails must surface its skip and reason in the run output
    And it returns one rejection per dishonest gate, empty when every gate is proven; it reads no world and returns pure data

  Scenario: test_valid_transitions tests every declared transition
    Given machine: StateMachine and run_transition: Callable
    When test_valid_transitions is called
    Then for each (state, event) to next_state in the machine's transition table it applies the event and returns a transition_incorrect failure when the result is not ok of the expected next state
    And it returns one failure per wrong transition, empty when every declared transition is correct, driving transition coverage to 100 by construction; it performs no I/O of its own

  Scenario: test_invalid_transitions tests every undeclared state-event pair
    Given machine: StateMachine and run_transition: Callable
    When test_invalid_transitions is called
    Then for each state and each event with no declared transition it applies the event and returns an invalid_transition_accepted failure when the result is not a no_transition fault, because an undeclared pair must be refused
    And it returns one failure per undeclared pair that was accepted, empty when every undeclared pair faults correctly; it performs no I/O of its own

  Scenario: test_adversarial_state_machine tests adversarial neighbors of states and events
    Given machine: StateMachine and run_transition: Callable
    When test_adversarial_state_machine is called
    Then for each state it feeds each adversarial neighbor of that state the first valid event and returns an invalid_state failure when the neighbor is accepted; for each event it feeds the first valid state each adversarial neighbor and returns an invalid_event failure when the neighbor is accepted
    And the neighbors come from adversarial_neighbors, the same five classes used for Set members
    And it returns one failure per accepted neighbor, empty when every neighbor is rejected; it performs no I/O of its own

  Scenario: adversarial_neighbors generates the deduplicated union of the five neighbor classes
    Given value: str
    When adversarial_neighbors is called
    Then it returns the deduplicated union of edit-distance-1 neighbors, Unicode confusables, control-character injections, length extensions and encoding variants, with the original value removed — every neighbor must produce a rejection, and one that is accepted reveals a vocabulary overlap, a case-sensitivity bug, a normalization flaw or an encoding vulnerability
    And value is one Set member or one state or event token; it reads no world and returns pure data

  Scenario: edit_distance_1 generates the edit-distance-1 neighbor class
    Given value: str
    When edit_distance_1 is called
    Then it returns every single deletion, every single insertion from the alphanumeric alphabet, every single substitution, the lower, upper and title case variants, and the whitespace variants — a leading space, a trailing space, and an interior space after the first character
    And it reads no world and returns pure data

  Scenario: unicode_confusables generates the Unicode-confusable neighbor class
    Given value: str
    When unicode_confusables is called
    Then for each ASCII character in value that has a known visually-similar character in a different Unicode block it returns one neighbor with that character substituted at that position, plus one full-homoglyph neighbor with every replaceable character substituted at once
    And the confusable map is the curated subset of Unicode Technical Standard 39 the reference implementation exercises
    And it reads no world and returns pure data

  Scenario: control_characters generates the control-character neighbor class
    Given value: str
    When control_characters is called
    Then for each C0 and C1 control code, DEL, and the zero-width and bidirectional-override characters on the injection set it returns three neighbors — the character prepended, appended, and inserted at the midpoint of value — to reveal parsers that strip or mishandle control codes instead of rejecting them
    And it reads no world and returns pure data

  Scenario: length_extensions generates the length-extension neighbor class
    Given value: str
    When length_extensions is called
    Then it returns value repeated 10, 100 and 1000 times to shake out quadratic behaviour, and value padded to just below, at, and well beyond the uint16 boundary and toward one megabyte, to expose fixed-buffer assumptions, field-length confusion and downstream truncation
    And it reads no world and returns pure data

  Scenario: encoding_variants generates the encoding-variant neighbor class
    Given value: str
    When encoding_variants is called
    Then it returns value with a UTF-16 byte-order-mark prefix, an overlong UTF-8 encoding of its ASCII, a double percent-encoding, a mixed UTF-8 and latin-1 encoding, and whitespace-normalization attacks that replace a space with a non-breaking space or a line separator, targeting recognizers that accept after normalization rather than rejecting malformed input
    And it reads no world and returns pure data

  # hd: python/honest-test/honest-test.hd::schema_probe_findings
  # spec: Honest Test §6.1 (as cited by the declaration)
  Scenario: schema_probe_findings interprets round_trip_equal
    Given table: str is the declared table "widgets" and outcome: SchemaProbeOutcome is round_trip_equal
    When schema_probe_findings is called
    Then it returns an empty list

  # hd: python/honest-test/honest-test.hd::schema_probe_findings
  # spec: Honest Test §6.1 (as cited by the declaration)
  Scenario: schema_probe_findings interprets round_trip_mismatch
    Given table: str is the declared table "widgets" and outcome: SchemaProbeOutcome is round_trip_mismatch
    When schema_probe_findings is called
    Then it returns one Finding with kind "failure", code "round_trip_mismatch" and an empty location
    And the message identifies "widgets" and the broken round-trip contract

  # hd: python/honest-test/honest-test.hd::schema_probe_findings
  # spec: Honest Test §6.1 (as cited by the declaration)
  Scenario: schema_probe_findings interprets undeclared_column_rejected
    Given table: str is the declared table "widgets" and outcome: SchemaProbeOutcome is undeclared_column_rejected
    When schema_probe_findings is called
    Then it returns an empty list

  # hd: python/honest-test/honest-test.hd::schema_probe_findings
  # spec: Honest Test §6.1 (as cited by the declaration)
  Scenario: schema_probe_findings interprets undeclared_column_accepted
    Given table: str is the declared table "widgets" and outcome: SchemaProbeOutcome is undeclared_column_accepted
    When schema_probe_findings is called
    Then it returns one Finding with kind "failure", code "undeclared_column_accepted" and an empty location
    And the message identifies "widgets" and the broken undeclared-column rejection contract

  # hd: python/honest-test/honest-test.hd::schema_probe_findings
  # spec: Honest Test §6.1 (as cited by the declaration)
  Scenario: schema_probe_findings interprets missing_required_field_rejected
    Given table: str is the declared table "widgets" and outcome: SchemaProbeOutcome is missing_required_field_rejected
    When schema_probe_findings is called
    Then it returns an empty list

  # hd: python/honest-test/honest-test.hd::schema_probe_findings
  # spec: Honest Test §6.1 (as cited by the declaration)
  Scenario: schema_probe_findings interprets missing_required_field_accepted
    Given table: str is the declared table "widgets" and outcome: SchemaProbeOutcome is missing_required_field_accepted
    When schema_probe_findings is called
    Then it returns one Finding with kind "failure", code "missing_required_field_accepted" and an empty location
    And the message identifies "widgets" and the broken required-field rejection contract

  # hd: python/honest-test/honest-test.hd::schema_probe_findings
  # spec: Honest Test §6.1 (as cited by the declaration)
  Scenario: schema_probe_findings interprets empty_rows
    Given table: str is the declared table "widgets" and outcome: SchemaProbeOutcome is empty_rows
    When schema_probe_findings is called
    Then it returns an empty list

  # hd: python/honest-test/honest-test.hd::schema_probe_findings
  # spec: Honest Test §6.1 (as cited by the declaration)
  Scenario: schema_probe_findings interprets empty_set_faulted
    Given table: str is the declared table "widgets" and outcome: SchemaProbeOutcome is empty_set_faulted
    When schema_probe_findings is called
    Then it returns one Finding with kind "failure", code "empty_set_faulted" and an empty location
    And the message identifies "widgets" and the broken empty-set contract

  # hd: python/honest-test/honest-test.hd::test_persist_schema_contract
  Scenario: test_persist_schema_contract checks a schema against a real in-memory database
    Given schema: Schema and connect: Callable
    When test_persist_schema_contract is called
    Then for every table it checks four contracts against a real in-memory database (never a mock) and returns a failure for each that breaks: round_trip_mismatch when a row read back does not equal the row written, undeclared_column_accepted when a query builder referencing an undeclared column is not rejected at build time, missing_required_field_accepted when an insert omitting a non-nullable column is not rejected, and empty_set_faulted when a select matching no rows returns a fault instead of ok of an empty list
    And connect is honest-persist's one I/O seam injected, returning a fresh ephemeral in-memory database recreated per table; the only side effect is through that injected real driver
    And it returns one failure per broken contract per table, empty when every table's contract holds

  # hd: python/honest-test/honest-test.hd::test_persist_schema_contract
  # spec: Honest Test §6.1 (as cited by the declaration)
  Scenario: test_persist_schema_contract reports a valid empty-set read fault
    Given schema: Schema and connect: Callable for a real in-memory database where setup succeeds and the driver faults on a valid select for a key absent from the declared table
    When test_persist_schema_contract is called
    Then it returns an empty_set_faulted finding of kind failure for that table

  Scenario: enumerate_check_constraints enumerates the CHECK-constraint contract cases
    Given schema: Schema
    When enumerate_check_constraints is called
    Then for each CHECK declared on a table it produces one CheckCase carrying a conforming row the real database must accept and a violating row it must reject, both derived from the closed, finite constraint vocabulary
    And it returns the list of cases for the contract runner to drive against the real database; it reads no world and returns pure data, the running against the database being test_persist_schema_contract's injected connect

  Scenario: test_css_isolation checks that two components share no CSS class name
    Given component_a: Component and component_b: Component
    When test_css_isolation is called
    Then it extracts each component's CSS classes from its template and returns a css_namespace_collision failure naming the shared classes when the two sets intersect, because each component must namespace under its own BEM block; empty when their class namespaces are disjoint
    And it reads no world and returns pure data

  Scenario: test_route_isolation checks that no two components define the same route path
    Given components: list<Component>
    When test_route_isolation is called
    Then it accumulates every component's route paths and returns a route_collision failure naming both components when a path is defined twice; one failure per collided path, empty when every route path is unique
    And it reads no world and returns pure data

  # hd: python/honest-test/honest-test.hd::test_startup_isolation
  Scenario: test_startup_isolation checks that components are independently loadable
    Given components: list<Component> and load_component: Callable
    When test_startup_isolation is called
    Then it returns a startup_cascade failure when one component failing to load causes another to fail to load, empty when each component's load failure is isolated, because when one component fails every other must still load
    And load_component is the injected loader driving the genuine load; the effect of loading belongs to it and honest-test only observes which loads then fail

  Scenario: extract_css_classes pulls the CSS class names out of a template
    Given template: str
    When extract_css_classes is called
    Then it returns the set of CSS class names the component's rendered HTML references, for test_css_isolation to intersect against another component's
    And it reads no world and returns pure data

  Scenario: coverage_ratio computes one coverage dimension's numbers
    Given exercised: int and total: int
    When coverage_ratio is called
    Then it returns a Coverage carrying exercised, total and their whole-number percentage — the share of the things that could be exercised that were — one computation serving all four dimensions (vocabulary, chain, honesty, state-machine)
    And for chain coverage the total is the fault exits an input can reach, not every fault exit; the exits no input can reach are named elsewhere, never folded into this ratio
    And it reads no world and returns pure data

  Scenario: build_coverage_report assembles the four coverage dimensions
    Given vocabularies: dict<str, Coverage> and chains: dict<str, Coverage> and honesty: dict<str, Coverage> and state_machines: dict<str, Coverage>
    When build_coverage_report is called
    Then it assembles the four coverage dimensions into the CoverageReport write_coverage writes as coverage.json, stamping the format version
    And each argument is a map from a declaration's name to its Coverage, already computed by coverage_ratio
    And it reads no world and returns pure data

  Scenario: build_run_report assembles the finished RunReport
    Given chains: int and links: int and vocabularies: int and permutations: int and failures: int and adversarial_rejected: int and coverage: CoverageReport and mutation_caught: int and mutation_total: int
    When build_run_report is called
    Then it assembles the finished RunReport from the measured pieces: how many chains, links and vocabularies the run found, how many generated cases ran and failed, how many near-miss inputs were correctly rejected, the CoverageReport, and the mutation-adequacy tally
    And it returns the RunReport render_report renders and write_coverage writes; it reads no world and returns pure data

  Scenario: render_report renders the RunReport into the human layout
    Given report: RunReport
    When render_report is called
    Then it returns the report text — the chains, links and vocabularies found, the permutations run and failures, the adversarial inputs rejected, the honesty and chain-contract results, the state-machine tallies, and the totals — laid out as section 11 shows
    And run_suite hands the string to print_report; it reads no world and returns pure data, the write being print_report's

  # hd: python/honest-test/honest-test.hd::run_source_mutation
  Scenario: run_source_mutation returns mutants for parseable source
    Given source: str is a parseable Python module containing a site for a declared mechanical change
    When run_source_mutation is called
    Then it returns the source mutants with spans and original and replacement text, without executing them

  # hd: python/honest-test/honest-test.hd::run_source_mutation
  Scenario: run_source_mutation returns a fault for malformed source
    Given source: str is a malformed Python module
    When run_source_mutation is called
    Then it returns the Fault from source_mutants

  # hd: python/honest-test/honest-test.hd::_number_mutants
  # spec: Honest Test §9.6 (as cited by the declaration)
  Scenario: _number_mutants shifts hexadecimal octal and binary tokens
    Given root: Node contains integer tokens "0x0FFF", "0O_17" and "0B_11" in that order
    When _number_mutants is called
    Then it returns three number_shift mutants in source order with replacement text "4096", "16" and "4", respectively
    And each mutant retains the original token text and span

  # hd: python/honest-test/honest-test.hd::_number_mutants
  # spec: Honest Test §9.6 (as cited by the declaration)
  Scenario: _number_mutants keeps decimal token spans separate from unary signs
    Given root: Node contains the decimal token "000" followed by the unary expression "-1_000"
    When _number_mutants is called
    Then it returns number_shift mutants for "000" and "1_000" with replacement text "1" and "1001", respectively
    And the span for "1_000" excludes the unary sign

  # hd: python/honest-test/honest-test.hd::_number_mutants
  # spec: Honest Test §9.6 (as cited by the declaration)
  Scenario: _number_mutants skips imaginary tokens and preserves integer order
    Given root: Node contains numeric tokens "7", "2j", "3J" and "9" in that order
    When _number_mutants is called
    Then it returns only the number_shift mutants for "7" and "9", in that order, with replacement text "8" and "10"

  # hd: python/honest-test/honest-test.hd::source_mutants
  Scenario: source_mutants enumerates the declared mechanical changes
    Given root: Node is the parsed root of a module containing sites for the declared change kinds
    When source_mutants is called
    Then it returns one Mutant per applicable change site and change, carrying the node span, original text and replacement text, without running the mutants

  # hd: python/honest-test/honest-test.hd::_boolean_mutants
  # spec: Honest Test §9.6 (as cited by the declaration)
  Scenario: _boolean_mutants flips only operator tokens in source order
    Given root: Node parses the source line "result: bool = (a and b) or c # and in a comment"
    When _boolean_mutants is called
    Then it returns two condition_flip records in source order
    And the first spans only "and" at zero-based bytes 18 through 20 and replaces it with "or"
    And the second spans only "or" at zero-based bytes 25 through 26 and replaces it with "and"
    And applying either record leaves the operands, grouping, annotation, whitespace and comment outside that span unchanged

  # hd: python/honest-test/honest-test.hd::_boolean_mutants
  # spec: Honest Test §9.6 (as cited by the declaration)
  Scenario: _boolean_mutants returns no flips for operator words in strings and comments
    Given root: Node parses one assignment of the string literal "and or" with a comment containing the words and and or, and no actual Boolean operator tokens
    When _boolean_mutants is called
    Then it returns an empty list

  # hd: python/honest-test/honest-test.hd::_membership_mutants
  # spec: Honest Test §9.6 (as cited by the declaration)
  Scenario: _membership_mutants flips each chained membership token independently
    Given root: Node parses the source line "a in b not in c in d"
    When _membership_mutants is called
    Then it returns three membership_change records in source order with zero-based byte spans [2, 4), [7, 13), and [16, 18)
    And their original texts are "in", "not in", and "in" with replacements "not in", "in", and "not in", respectively
    And applying one record leaves both other operators and all operands unchanged

  # hd: python/honest-test/honest-test.hd::_membership_mutants
  # spec: Honest Test §9.6 (as cited by the declaration)
  Scenario: _membership_mutants preserves the raw span of a spaced not in token
    Given root: Node parses the source line "a not  in b" with two spaces between not and in
    When _membership_mutants is called
    Then it returns one membership_change record with byte span [2, 9), original text "not  in", and replacement "in"
    And applying it yields "a in b"

  # hd: python/honest-test/honest-test.hd::_membership_mutants
  # spec: Honest Test §9.6 (as cited by the declaration)
  Scenario: _membership_mutants ignores iterator syntax strings and comments
    Given root: Node parses the comprehension [a for a in b], a for-loop over b, the string literal "a in b not in c", and a comment containing in and not in, with no membership comparison
    When _membership_mutants is called
    Then it returns an empty list

  # hd: python/honest-test/honest-test.hd::source_mutants
  # spec: Honest Test §9.6 (as cited by the declaration)
  Scenario: source_mutants emits separate condition and membership changes in traversal order
    Given root: Node parses four source lines "left = a and b", "right = c or d", "first = p in group", and "second = q in other", in that order
    When source_mutants is called
    Then the condition_flip mutations change only "and" to "or" on the first line and only "or" to "and" on the second line, in that order
    And the membership_change mutations make the third line "first = p not in group" and the fourth line "second = q not in other", in that order
    And the four changes are separate records, each with a location spanning its exact original source text and a replacement that changes only its own site

  # hd: python/honest-test/honest-test.hd::source_mutants
  # spec: Honest Test §9.6 (as cited by the declaration)
  Scenario: source_mutants emits separate constant replacements in traversal order
    Given root: Node parses five assignments whose values in source order are 0, 1, True, False, and the string literal "text"
    When source_mutants is called
    Then the constant_replace records carry original text 0, 1, True, False, and "text", in that order, with replacement text 1, 0, False, True, and an empty string literal, respectively
    And each record spans only its original literal and is separate from any other mutation of that literal

  # hd: python/honest-test/honest-test.hd::source_mutants
  Scenario: source_mutants returns a fault for an unparseable root
    Given root: Node is the recovered Python root of malformed source
    When source_mutants is called
    Then it returns a Fault

  # hd: python/honest-test/honest-test.hd::mutate_source
  Scenario: mutate_source generates every mechanical mutant of the source
    Given source: str
    When mutate_source is called
    Then it applies each of the seven change kinds to every place it fits and returns one Mutant per change — a swapped comparison, a shifted number, a flipped condition, a replaced constant, a swapped result, a removed line, a changed membership or key — each carrying its node span and the original and replacement text
    And it returns a Fault when the source does not parse, because a mutant can only be made from parseable source
    And the mutants are run out of process by the memory-capped harness, never here; it reads no world and returns pure data or a Fault

  Scenario: classify_mutant_result judges one mutant run against the baseline
    Given baseline_output: str and mutant_output: str and completed: bool
    When classify_mutant_result is called
    Then it returns a MutantResult: caught when the mutant output shows at least one case failed, set_aside with the demonstration as its reason when the mutant output is identical to the baseline, and undecided with the bound as its reason when completed is false, because a run that hit its bound produced no verdict and recording it as caught would assert a detection that did not happen
    And adequacy requires caught plus set_aside to equal the total with none left undecided
    And it reads no world and returns pure data

  Scenario: generate_scaffolding generates the Gherkin step scaffolding for a chain
    Given chain_name: str and links: list<Link>
    When generate_scaffolding is called
    Then it returns a step-module source string whose handlers are pure functions that take the immutable context plus bound captures and return a new context, wired through a register(registry) that returns the registry — never decorators or a mutable shared context — matching honest-gherkin's step-module contract
    And run_suite hands the string to write_scaffolding, which writes the do-not-edit file; the developer writes only the .feature files against it
    And it reads no world and returns the generated source as a string

  Scenario: build_proof_event builds one hf.proof.checked proof event
    Given function_name: str and scenario: str and cases_run: int and outcome: ProofOutcome and line_coverage: int and branch_coverage: int
    When build_proof_event is called
    Then it returns the ProofEvent record carrying the fully-qualified function name, the gherkin scenario name, how many cases ran, the proved-or-failed outcome, and the line and branch coverage percentages
    And a function earns proved only when honesty, full coverage and the gherkin's Then value oracle all hold; a run where any does not emits failed
    And run_suite hands it to emit_proof_event; it reads no world and returns pure data, the emit being the sink's boundary

  Scenario: evaluate_case opens the value-oracle door to run one portable suite case
    Given case: SuiteCase and function_map: dict<str, Callable>
    When evaluate_case is called
    Then it is the door a sibling module's conformance runner enters by import; it hands the case and the map to run_case and returns what run_case returned: honest-type's ok Result carrying the output when it equals the expected value, honest-type's err Result carrying an expected-vs-got fault when they differ, or a honest-test Fault when a named function or expression is unknown
    And the ok arm is what earns the value leg of proved, because auto-generation checks properties and shape but never which value is correct
    And evaluate_case itself only hands its input to the orchestrator; the running of the injected function is the engine's boundary realized by run_resolved_call

  Scenario: run_case drives the value-oracle sequence for one case
    Given case: SuiteCase and function_map: dict<str, Callable>
    When run_case is called
    Then it resolves the case with resolve_call, and when that returns a Fault — a named function or expression the map does not hold — it passes the Fault outward and runs nothing; otherwise it runs the ResolvedCall at the boundary with run_resolved_call, judges the output against the resolved expected value with compare_output, and returns the ok or err Result
    And it holds the one decision of the value-oracle path — a case that could not resolve never runs — and composes no other orchestrator

  Scenario: resolve_call resolves one suite case into a runnable ResolvedCall
    Given case: SuiteCase and function_map: dict<str, Callable>
    When resolve_call is called
    Then it resolves the function name and each portable argument against the map — a literal is itself, a $ref is looked up to its callable, and a $call becomes a resolved application node carrying its callable and its own resolved arguments — and resolves the expected value the same way, returning a ResolvedCall ready for run_resolved_call
    And it returns a honest-test Fault when any name or expression is not in the map, so a ResolvedCall is always runnable
    And it reads no world and runs no code: every execution waits for the boundary; it returns pure data or a Fault

  Scenario: run_resolved_call runs one resolved call at the engine's boundary
    Given resolved: ResolvedCall
    When run_resolved_call is called
    Then it applies each resolved $call application bottom-up, invokes the function under test by single, positional or keyword arguments, and drives an awaitable result to completion itself so an async function is checkable, returning the finished value for compare_output to judge
    And all names are already resolved, so it reaches no map and reads no file; its one side effect is the process-level effect of running the caller's injected code, which may do anything, and reading back what it returned

  Scenario: compare_output judges one value-oracle output against the known-good value
    Given output: any and expected: any
    When compare_output is called
    Then it returns honest-type's ok Result carrying the output when the output equals the expected value, and honest-type's err Result carrying an expected-vs-got fault when they differ, comparing the output whole so a function that returns a Result has its Result as its expected value
    And the ok arm is the value leg of proved and an err arm is a wrong value; it reads no world and returns pure data

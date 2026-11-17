Feature: honest-test — generated, one scenario per function (59 total)

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

  Scenario: classify_predicate sorts one predicate into its generation class
    Given predicate_node: Node
    When classify_predicate is called
    Then it reads the node for the markers that decide the class and returns exactly one PredicateClass: numeric for int()/float()/a numeric comparison, length_bounded for a len(s) comparison, character_class for s.isdigit()/s.isalpha()/s.isupper(), external_lookup for a call to a function not in the codebase, composite for a call to a codebase-defined function (recursing into the callee at any depth), and catch_all for a predicate accepting nearly all inputs
    And it reads no world and returns pure data

  Scenario: enumerate_lengths generates the strings for a length-bounded predicate
    Given predicate_node: Node
    When enumerate_lengths is called
    Then it reads the minimum and maximum length from the comparison operators (distinguishing == from <= from <) and returns a LengthCases: one valid string at every length in the range, and the invalid boundary lengths just outside — one over the maximum always, one under the minimum when the minimum exceeds one
    And a pure lower bound with no maximum is unbounded above and falls to supplied values rather than generating here
    And it reads no world and returns pure data

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

  Scenario: verify_purity runs a link twice and flags a different result
    Given link: Callable and test_manifest: Manifest
    When verify_purity is called
    Then it runs the link twice on the same manifest and returns a non_deterministic failure when the two results differ, because a pure function must return the same output for the same input; the empty list when the link is pure
    And a link declared a boundary is exempt and is not handed here
    And it performs no I/O of its own; any effect belongs to the injected link

  Scenario: detect_mutation flags a link that modified its input manifest
    Given link: Callable and test_manifest: Manifest
    When detect_mutation is called
    Then it deep-copies the manifest, runs the link, and returns a manifest_mutated failure carrying the diff when the manifest after the run differs from the copy, because a pure function must not modify its input; the empty list when the input was untouched
    And it performs no I/O of its own

  Scenario: test_idempotency flags a chain that is not idempotent
    Given chain: Callable and test_manifest: Manifest
    When test_idempotency is called
    Then it runs the chain twice, the second time on a deep copy of the manifest, and returns a not_idempotent failure when the two results differ; the empty list when the chain is idempotent
    And a chain containing a boundary link is exempt and is not handed here
    And it performs no I/O of its own

  Scenario: verify_under_monitor runs a link under the injected monitor
    Given link: Callable and test_manifest: Manifest and monitor: Callable and kind: str
    When verify_under_monitor is called
    Then it runs the link inside the injected monitor and returns a warning when the monitor recorded a watched call and the link is not declared a boundary — io_detected for kind io (boundary isolation, the io_monitor plug) and nondeterminism_detected for kind nondeterminism (the call_monitor plug trapping the non-deterministic watch-list symbols)
    And monitor is injected as a callable so honest-test takes back the record of detected calls, never reaching for a global; the warning reports and does not block
    And it returns the warning as a one-element list, or the empty list

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

  Scenario: test_persist_schema_contract checks a schema against a real in-memory database
    Given schema: Schema and connect: Callable
    When test_persist_schema_contract is called
    Then for every table it checks four contracts against a real in-memory database (never a mock) and returns a failure for each that breaks: round_trip_mismatch when a row read back does not equal the row written, undeclared_column_accepted when a query builder referencing an undeclared column is not rejected at build time, missing_required_field_accepted when an insert omitting a non-nullable column is not rejected, and empty_set_faulted when a select matching no rows returns a fault instead of ok of an empty list
    And connect is honest-persist's one I/O seam injected, returning a fresh ephemeral in-memory database recreated per table; the only side effect is through that injected real driver
    And it returns one failure per broken contract per table, empty when every table's contract holds

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

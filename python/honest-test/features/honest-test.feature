Feature: honest-test — generated from honest-test.hd, one scenario per function with the two orchestrators split by branch (49 functions, 53 scenarios)

  # Doors. Both are host-started call-form entries the entry-check reports UNCHECKED.

  Scenario: run_cli the CLI door hands src_dir to the orchestrator and returns its answer
    Given src_dir: str
    When run_cli is called
    Then it hands src_dir to run_suite, which drives the whole run, and opens no file itself
    And it returns the assembled RunReport run_suite returned on a completed run
    And it returns the Fault run_suite passed outward when the module source could not be parsed for mutation
    And the two sinks print_report and write_coverage have already run inside run_suite before it returns, so a completed run has already reported
    And it raises nothing: a run that could not complete comes back as a Fault for the host to discharge as a non-zero exit

  Scenario: check_test_body the pytest collection hook reads one test module and refuses a dishonest body
    Given collector: handle
    When check_test_body is called
    Then it reads the collected module's source through the injected collector, whose path read_text returns the source, and touches nothing else on the collector
    And it hands that source to run_body_check for the pure verdict and gets back the list of rejection Findings
    And it returns that list, empty when the module collected clean
    And it raises collection_failure when the list is non-empty, naming each rebinding site, so a test body that rebinds a call target at runtime does not run
    And its one side effect is reading the collected module's source file

  # Readers. The source reader, the live-module loader, and the config reader.

  Scenario: read_source pulls one source file's full text from disk
    Given path: str
    When read_source is called
    Then it returns that file's full contents as a string and does nothing else: it does not parse, generate or write
    And path is the filesystem path of one source file under src/, already resolved by discovery at the run boundary
    And its one side effect is reading the filesystem

  Scenario: load_under_test imports each module under test to obtain its live declarations
    Given src_dir: str
    When load_under_test is called
    Then it imports each module under src_dir, running each module's own top-level code into the running interpreter, so it is a boundary and not pure analysis
    And it returns a LiveModules record carrying the live vocabularies, bindings, links, chains, machines, schemas, components, providers and gates for the orchestrator to thread into the checks that must call real functions
    And it asks honest-type to tell a link from an ordinary function and read its declared vocabulary and binding off each imported module through the honest-type.link_meta seam
    And its side effects are reading the filesystem, reading the import system of the running process, and reading honest-type.link_meta

  Scenario: read_config reads honest-test.toml and decodes it to the parsed table
    Given path: str
    When read_config is called
    Then it reads honest-test.toml and returns the plain decoded table, the predicates section as a map, and nothing more
    And decoding the standard TOML format is part of the read; it builds no module record and resolves no values, because a door does not transform its input (honest-check HC-R006)
    And the table is empty when no honest-test.toml exists or it declares no predicates
    And its one side effect is reading the filesystem

  # Orchestrators. run_suite drives the CLI run across its decision paths; run_body_check drives the collection verdict.

  Scenario: run_suite the completed run resolves config once, loads once, drives the core, drives both sinks and returns the report
    Given src_dir: str
    When run_suite is called
    Then it pulls the programmer-supplied config once with read_config and loads the modules under test once with load_under_test to obtain their live vocabularies, links, chains, machines, schemas, components, providers and gates
    And it measures coverage with coverage_ratio and assembles it with build_coverage_report
    And it drives the two sinks, print_report to stdout and write_coverage to coverage.json, and returns the assembled RunReport
    And one run resolves one config, loads once, and governs the whole scan
    And it does not drive generate_scaffolding, build_proof_event or evaluate_case: those are the per-case import surface the generated scaffolding and conformance runner call

  Scenario: run_suite the source-text path reads, parses, finds predicates, classifies each and dispatches to the matching generator
    Given src_dir: str
    When run_suite is called
    Then for each file it pulls the text with read_source, parses it once with parse_source, finds each predicate node with extract_predicates and sorts it with classify_predicate
    And it runs the matching generator per predicate class: enumerate_lengths for a length_bounded predicate, fibonacci_sequence for a numeric one with the limit and direction the config carries, supplied_cases for an external_lookup predicate
    And it runs mutate_source to produce the mutants for the adequacy measure

  Scenario: run_suite the live-value path runs every check that must call real functions over the loaded declarations
    Given src_dir: str
    When run_suite is called
    Then enumerate_sets permutes each vocabulary and the honesty checks verify_purity, detect_mutation, test_idempotency and verify_under_monitor run each link
    And test_chain_contracts checks each chain's joins, test_auth_honesty probes each provider, and check_gate_honesty verifies each gate
    And the three state-machine tests test_valid_transitions, test_invalid_transitions and test_adversarial_state_machine exercise each machine
    And test_persist_schema_contract and enumerate_check_constraints drive each schema, and the three component checks test_css_isolation, test_route_isolation and test_startup_isolation compare the components

  Scenario: run_suite the fault-return path passes the mutate_source Fault outward to the door
    Given src_dir: str
    When run_suite is called
    Then when mutate_source answers a Fault because the module source does not parse, it returns that Fault, passing it outward to the door rather than swallowing it
    And it raises nothing: the unparseable-source outcome travels as a returned Fault

  Scenario: run_body_check an honest body runs the verdict and returns an empty list
    Given source: str
    When run_body_check is called
    Then it runs test_body_violations over the one test module's source the door read
    And it returns the empty list when the test body is honest
    And it reads no world, keeps no state, and composes no other orchestrator

  Scenario: run_body_check a dishonest body returns one rejection Finding per rebinding statement
    Given source: str
    When run_body_check is called
    Then it runs test_body_violations over the source and returns the list of rejection Findings for the door to act on
    And it holds the collection path's single decision — run the verdict over the source — and nothing else

  # The pure verdict the collection gate rests on.

  Scenario: test_body_violations returns one rejection per statement that rebinds a call target at runtime
    Given source: str
    When test_body_violations is called
    Then it returns one rejection Finding per statement that rebinds a call target at runtime: a monkeypatch fixture (setattr, setitem, delattr, setenv), a mock.patch or patch.object or an installed Mock, a setattr on an imported module, class or function, or an imported symbol rebound by attribute assignment
    And each rejection carries the rebinding site's location and the fix — pass the dependency as a parameter, or inject a boundary plug as an argument
    And the framework's own record-and-restore instrumentation (io_monitor, call_monitor) is not a violation and never appears, because it lives in framework code and restores the original rather than leaving a behaviour-changing stand-in
    And an empty list means the test body is honest
    And it reads nothing and raises nothing

  # Sinks. Two boundary_out writing stdout and coverage.json.

  Scenario: print_report writes the already-rendered report to stdout
    Given text: str
    When print_report is called
    Then it writes the given string to standard output and nothing else: it does no formatting, since the layout was already rendered, because a door does not transform its input (honest-check HC-R006)
    And it returns nothing and makes no decision
    And its one side effect is writing stdout

  Scenario: write_coverage writes the report's coverage as coverage.json
    Given report: RunReport
    When write_coverage is called
    Then it writes the report's CoverageReport field as coverage.json, the file honest-check reads for HC-P009 and other cross-tool checks
    And it returns nothing and makes no decision, since the coverage numbers are already measured
    And its one side effect is writing the file

  # Parse and classify, and the source-reachable generators.

  Scenario: parse_source parses one source file with tree-sitter and returns the root node
    Given source: str
    When parse_source is called
    Then it returns the tree's root node, which extract_predicates walks for predicate nodes and mutate_source walks for the spans each change sits at
    And the parse is deterministic and reads no world
    And tree-sitter produces a tree with error nodes for malformed input rather than failing, so it returns a node, never a fault

  Scenario: extract_predicates walks a parsed tree and returns each recognizer predicate node
    Given tree: Node
    When extract_predicates is called
    Then it returns one node per predicate found, each the body honest-test analyzes
    And an empty list means the file declares no predicates
    And it reads no world and returns pure data

  Scenario: classify_predicate sorts one predicate into its generation class by analyzing its AST
    Given predicate_node: Node
    When classify_predicate is called
    Then it returns exactly one PredicateClass: numeric for int() or float() or a numeric comparison; length_bounded for a len(s) comparison; character_class for s.isdigit(), s.isalpha() or s.isupper(); external_lookup for a call to a function not defined in the codebase; composite for a call to a codebase-defined function, recursing into that callee at any depth; catch_all for a predicate that accepts nearly all inputs, already rejected at vocabulary construction by HC011
    And the returned class picks the downstream generation strategy
    And it reads no world and returns pure data

  Scenario: enumerate_lengths generates the strings for a length-bounded predicate
    Given predicate_node: Node
    When enumerate_lengths is called
    Then it reads the minimum and maximum length from the comparison operators the node holds, distinguishing == (one exact length) from <= (a range up to a maximum) from < (a range up to one below)
    And it returns a LengthCases with one valid string at every length in the range, built by repeating the alphabet so lengths beyond the alphabet are still generated
    And the invalid list carries the boundary lengths just outside — one over the maximum always, and one under the minimum when the minimum exceeds one
    And a pure lower bound with no maximum is unbounded above and not finitely enumerable, so it falls to supplied values rather than generating here
    And it reads no world and returns pure data

  Scenario: fibonacci_sequence generates the numeric probe values from zero up to the limit
    Given limit: int and negative: bool
    When fibonacci_sequence is called
    Then it returns the Fibonacci sequence from zero up to limit, giving logarithmically distributed values dense among small numbers and spaced among large ones, probing a numeric range rather than enumerating it
    And limit is the ceiling whose documented default is 1,000,000, carried from the predicate's honest-test.toml entry
    And when negative is true it returns the negatives of the sequence prepended to the non-negatives, and the non-negatives alone otherwise
    And for a float predicate each value is divided by 100
    And it reads no world and returns pure data

  Scenario: supplied_cases resolves one predicate's programmer-supplied values from the config
    Given predicate_name: str and supplied_values: SuppliedConfig
    When supplied_cases is called
    Then it returns a SuppliedCases carrying that predicate's valid and invalid values when the config has an entry
    And it returns missing true with empty lists when the config has no entry, the case the runner turns into a missing_supplied_values warning rather than passing over
    And it reads no file: the supplied values entered through read_config at the boundary, and it reads only the record it was handed
    And it returns pure data

  # The pure import surface (edge role) and the pure checks the orchestrator and conformance runner drive.

  Scenario: enumerate_sets generates every test case for a Set-based vocabulary
    Given vocab: Vocabulary
    When enumerate_sets is called
    Then it enumerates every member of every Set recognizer and produces the Cartesian product of their members, with no sampling, so a vocabulary of three Sets of 5, 150 and 4 members yields all 3,000 cases
    And each case is a manifest in honest-type's manifest shape, a map from each Set slot's name to the member chosen for it
    And a Maybe slot adds its absent arm, one more case binding that slot to Nothing with a null value, so a Maybe Set of 4 members yields 5
    And a predicate recognizer contributes no slot to these manifests and is handled by the predicate strategies, so a vocabulary of only predicate recognizers yields one empty manifest
    And it returns the list of test manifests, one per combination, reading no world and returning pure data

  Scenario: verify_purity runs a link twice on the same manifest and reports a non_deterministic failure when results differ
    Given link: Callable and test_manifest: Manifest
    When verify_purity is called
    Then it runs the link twice on the same manifest and returns a non_deterministic failure Finding when the two results differ, because a pure function must return the same output for the same input
    And a link declared a boundary is exempt and is not handed here
    And it returns the failure as a one-element list, or the empty list when the link is pure
    And it performs no I/O of its own; any effect belongs to the injected link

  Scenario: detect_mutation runs a link on a copied manifest and reports manifest_mutated when the input changed
    Given link: Callable and test_manifest: Manifest
    When detect_mutation is called
    Then it deep-copies the manifest, runs the link, and returns a manifest_mutated failure Finding when the manifest after the run differs from the copy, because a pure function must not modify its input
    And the failure's message carries the diff of what changed
    And it returns the failure as a one-element list, or the empty list when the input was untouched
    And it performs no I/O of its own

  Scenario: test_idempotency runs a chain twice and reports not_idempotent when results differ
    Given chain: Callable and test_manifest: Manifest
    When test_idempotency is called
    Then it runs the chain twice, the second time on a deep copy of the manifest, and returns a not_idempotent failure Finding when the two results differ
    And a chain containing a boundary link is exempt and is not handed here
    And it returns the failure as a one-element list, or the empty list when the chain is idempotent
    And it performs no I/O of its own

  Scenario: verify_under_monitor with the io kind runs a link under the I/O monitor and warns io_detected for a non-boundary link
    Given link: Callable and test_manifest: Manifest and monitor: Callable
    When verify_under_monitor is called with the io kind
    Then it runs the link inside the injected io_monitor and returns an io_detected warning Finding when the monitor recorded an I/O call and the link is not declared a boundary
    And monitor is framework record-and-restore instrumentation that patches known I/O functions to record a call and then restores the original, changing no result, so it is not the runtime rebinding section 4.8 forbids
    And it returns the warning as a one-element list, or the empty list when no I/O was detected
    And the warning reports and does not block

  Scenario: verify_under_monitor with the nondeterminism kind runs a link under the call monitor and warns nondeterminism_detected for a non-boundary link
    Given link: Callable and test_manifest: Manifest and monitor: Callable
    When verify_under_monitor is called with the nondeterminism kind
    Then it runs the link inside the injected call_monitor, which traps the symbols on the non-deterministic watch list, and returns a nondeterminism_detected warning Finding when the monitor recorded such a call and the link is not declared a boundary
    And this runtime trap is stricter than honest-check's static HC008, catching non-determinism entering through an attribute chain or dynamic dispatch that static analysis misses
    And the monitor's watch list is the subset of honest-check's NONDETERMINISTIC_WATCH_LIST honest-test carries and verifies against the published list in its conformance suite, so the two cannot drift
    And it returns the warning as a one-element list, or the empty list, and the warning reports and does not block

  Scenario: test_chain_contracts checks each adjacent pair of links and reports chain_contract on a broken join
    Given links: list of Callable and vocab: Vocabulary and binding: Binding
    When test_chain_contracts is called
    Then for each adjacent pair it enumerates the input cases the upstream link accepts, runs the upstream link, and when that produces an ok manifest feeds it to the downstream link
    And it returns a chain_contract failure Finding when the downstream link rejects that valid output with a server fault, because every valid output of one link must be accepted as valid input by the next
    And a client fault from the downstream link is not a contract failure — only a server fault indicates a broken join
    And it returns one failure per broken join, empty when every join holds, performing no I/O of its own

  Scenario: enumerate_test_cases builds the input manifests a link accepts for chain-contract testing
    Given accepts: Vocabulary and binding: Binding
    When enumerate_test_cases is called
    Then it enumerates the vocabulary the way enumerate_sets does and resolves each combination into a manifest through the binding, so each case is a ready input for the link under test
    And it returns the list of manifests, reading no world and returning pure data

  Scenario: test_auth_honesty probes each token class and reports auth_honesty on wrong behaviour
    Given provider: AuthProvider
    When test_auth_honesty is called
    Then for each of the six token classes it generates a token with the provider's test_token_generator and asserts the provider's outcome: a malformed token must be rejected at the actor_recognizer before resolve_actor, a valid token must resolve to ok(actor), and every other class must fault with the expected HTTP status compute_expected_status derives
    And it returns an auth_honesty failure Finding when the provider accepts a malformed token, rejects a valid one, or does not fault correctly for a class
    And whether a resolved actor is authorized for a target is ordinary business logic verified by that link's own tests, not here
    And it returns one failure per class that behaved wrongly, empty when the provider's boundary validation is sound, performing no I/O of its own

  Scenario: compute_expected_status maps one token class to the HTTP status the auth check expects
    Given token_class: TokenClass and fault_mapping: dict of str to int
    When compute_expected_status is called
    Then it returns 401 for revoked, expired, missing and forged (an unauthenticated fault), 400 or the provider's preferred status for malformed (rejected at the recognizer), and the ok path for valid carries no error status
    And the provider may override the default through fault_mapping
    And it reads no world and returns pure data

  Scenario: check_gate_honesty requires every gate to name a bound proof-of-failure test
    Given gates: list of Gate
    When check_gate_honesty is called
    Then it returns a gate_unverified rejection Finding for a gate with no proof, because a gate whose failing arm has never executed carries no information when the run is green
    And it returns a gate_proof_unbound rejection Finding for a proof that asserts only that some exception was raised rather than binding the specific failure type and message
    And honest-test never guesses which checks are gates, since inferring that is undecidable the way inferring entry points is; a gate declares itself
    And a gate that skips rather than fails must surface its skip and reason in the run output, the coverage obligation, not handled here as a failure
    And it returns one rejection per dishonest gate, empty when every gate is proven, reading no world and returning pure data

  Scenario: test_valid_transitions exhaustively tests every declared transition
    Given machine: StateMachine and run_transition: Callable
    When test_valid_transitions is called
    Then for each (state, event) to next_state in the machine's transition table it applies the event and returns a transition_incorrect failure Finding when the result is not ok of the expected next state
    And it returns one failure per wrong transition, empty when every declared transition is correct, driving transition coverage to 100 by construction
    And run_transition is honest-type's transition applied to the machine, passed in as a callable, and it performs no I/O of its own

  Scenario: test_invalid_transitions tests every (state, event) pair the table does not declare
    Given machine: StateMachine and run_transition: Callable
    When test_invalid_transitions is called
    Then for each state and each event with no declared transition it applies the event and returns an invalid_transition_accepted failure Finding when the result is not a no_transition fault, because an undeclared pair must be refused
    And it returns one failure per undeclared pair that was accepted, empty when every undeclared pair faults correctly
    And run_transition is honest-type's transition, passed in, and it performs no I/O of its own

  Scenario: test_adversarial_state_machine tests adversarial neighbors of the machine's states and events
    Given machine: StateMachine and run_transition: Callable
    When test_adversarial_state_machine is called
    Then for each state it feeds each adversarial neighbor of that state with the first valid event and returns an invalid_state failure Finding when the neighbor is accepted
    And for each event it feeds the first valid state each adversarial neighbor of that event and returns an invalid_event failure Finding when the neighbor is accepted
    And the neighbors come from adversarial_neighbors, the same five classes used for Set members
    And it returns one failure per accepted neighbor, empty when every neighbor is rejected, performing no I/O of its own

  Scenario: adversarial_neighbors generates the five classes of adversarial neighbors of one value
    Given value: str
    When adversarial_neighbors is called
    Then it returns the deduplicated union of edit-distance-1 neighbors, Unicode confusables, control-character injections, length extensions and encoding variants, with the original value removed
    And every neighbor must produce a rejection; one that is accepted reveals a vocabulary overlap, a case-sensitivity bug, a normalization flaw or an encoding vulnerability
    And the five class functions it invokes — edit_distance_1, unicode_confusables, control_characters, length_extensions, encoding_variants — are the reference vocabulary a conformant implementation must exercise in full
    And it reads no world and returns pure data

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
    Then for each C0 and C1 control code, DEL, and the zero-width and bidirectional-override characters on the injection set it returns three neighbors — the character prepended, appended, and inserted at the midpoint of value
    And these reveal parsers that strip or mishandle control codes instead of rejecting them
    And it reads no world and returns pure data

  Scenario: length_extensions generates the length-extension neighbor class
    Given value: str
    When length_extensions is called
    Then it returns value repeated 10, 100 and 1000 times to shake out quadratic behaviour, and value padded to just below, at, and well beyond the uint16 boundary and toward one megabyte, to expose fixed-buffer assumptions, field-length confusion and downstream truncation
    And it reads no world and returns pure data

  Scenario: encoding_variants generates the encoding-variant neighbor class
    Given value: str
    When encoding_variants is called
    Then it returns value with a UTF-16 byte-order-mark prefix, an overlong UTF-8 encoding of its ASCII, a double percent-encoding, a mixed UTF-8 and latin-1 encoding, and whitespace-normalization attacks that replace a space with a non-breaking space or a line separator
    And these target recognizers that accept after normalization rather than rejecting malformed input
    And it reads no world and returns pure data

  Scenario: test_persist_schema_contract checks four contracts per table against a real in-memory database
    Given schema: Schema and connect: Callable
    When test_persist_schema_contract is called
    Then connect is honest-persist's one I/O seam, injected: it returns a fresh ephemeral in-memory database recreated per table so nothing leaks, and honest-test applies the declared schema and drives the genuine query builders and execute against it, never a mock
    And for every table it returns a round_trip_mismatch failure when a row read back does not equal the row written
    And it returns an undeclared_column_accepted failure when a query builder referencing an undeclared column is not rejected at build time
    And it returns a missing_required_field_accepted failure when an insert omitting a non-nullable column is not rejected by the real database
    And it returns an empty_set_faulted failure when a select matching no rows returns a fault instead of ok of an empty list
    And it returns one failure per broken contract per table, empty when every table's contract holds; its only side effect is through the injected connect, a real driver

  Scenario: enumerate_check_constraints enumerates the CHECK-constraint contract cases for a schema
    Given schema: Schema
    When enumerate_check_constraints is called
    Then for each CHECK declared on a table it produces one CheckCase carrying a conforming row the real database must accept and a violating row it must reject, both derived from the closed CHECK-expression vocabulary, never supplied by hand
    And it returns the list of cases for the contract runner to drive against the real database
    And it reads no world and returns pure data; the running against the database is test_persist_schema_contract's injected connect, not here

  Scenario: test_css_isolation reports css_namespace_collision when two components share a CSS class
    Given component_a: Component and component_b: Component
    When test_css_isolation is called
    Then it extracts each component's CSS classes from its template with extract_css_classes and returns a css_namespace_collision failure Finding naming the shared classes when the two sets intersect, because each component must namespace under its own BEM block
    And it returns the failure when they collide, empty when their class namespaces are disjoint
    And it reads no world and returns pure data

  Scenario: test_route_isolation reports route_collision when two components define the same path
    Given components: list of Component
    When test_route_isolation is called
    Then it accumulates every component's route paths and returns a route_collision failure Finding naming both components when a path is defined twice
    And it returns one failure per collided path, empty when every route path is unique
    And it reads no world and returns pure data

  Scenario: test_startup_isolation reports startup_cascade when one component's load failure breaks another
    Given components: list of Component and load_component: Callable
    When test_startup_isolation is called
    Then with load_component the injected loader driving the genuine load, when one component fails to load every other must still load
    And it returns a startup_cascade failure Finding when a failure in one component causes another to fail to load, empty when each component's load failure is isolated
    And the effect of loading belongs to the injected loader; honest-test only observes which loads then fail

  Scenario: extract_css_classes pulls the CSS class names out of a component's template
    Given template: str
    When extract_css_classes is called
    Then it returns the set of class names the template references, for test_css_isolation to intersect against another component's
    And it reads no world and returns pure data

  Scenario: coverage_ratio computes one coverage dimension's numbers
    Given exercised: int and total: int
    When coverage_ratio is called
    Then it returns a Coverage carrying exercised, total and their whole-number percentage — the share of the things that could be exercised that were, one computation for all four dimensions
    And for chain coverage the total is the fault exits an input can reach, not every fault exit; the exits no input can reach are named elsewhere, never folded into this ratio
    And it reads no world and returns pure data

  Scenario: build_coverage_report assembles the four coverage dimensions into the CoverageReport
    Given vocabularies: dict of str to Coverage and chains: dict of str to Coverage and honesty: dict of str to Coverage and state_machines: dict of str to Coverage
    When build_coverage_report is called
    Then it returns the CoverageReport, stamping the format version, which write_coverage writes as coverage.json and honest-check reads for HC-P009
    And each argument is a map from a declaration's name to its Coverage, already computed by coverage_ratio
    And it reads no world and returns pure data

  Scenario: mutate_source generates every mechanical mutant of a module's source, or a Fault when it does not parse
    Given source: str
    When mutate_source is called
    Then it parses the source with tree-sitter and applies each of the seven change kinds to every place it fits, returning one Mutant per change — a swapped comparison, a shifted number, a flipped condition, a replaced constant, a swapped result, a removed line, a changed membership or key — each carrying its node span and the original and replacement text
    And it returns a Fault when the source does not parse, because a mutant can only be made from parseable source
    And the mutants are run out of process by the memory-capped harness, never here, because an infinite-loop mutant must not run inline; it only produces the changes
    And it reads no world and returns pure data or a Fault

  Scenario: classify_mutant_result judges one mutant run against the baseline
    Given baseline_output: str and mutant_output: str and completed: bool
    When classify_mutant_result is called
    Then it returns a MutantResult of caught when the mutant output shows at least one case failed
    And it returns set_aside with the demonstration as its reason when the mutant output is identical to the baseline, so the change cannot alter the result
    And it returns undecided with the bound as its reason when completed is false, because a run that hit its bound produced no verdict and recording it as caught would assert a detection that did not happen
    And adequacy requires caught plus set_aside to equal the total with none left undecided
    And it reads no world and returns pure data

  Scenario: evaluate_case runs one portable value-oracle case and compares the output against the known-good value
    Given case: SuiteCase and function_map: dict of str to Callable
    When evaluate_case is called
    Then it walks the input expression bottom-up — a literal is itself, a list evaluates its elements, a reference resolves a callable, a call applies a named function to its evaluated arguments — invokes the function under test by single, positional or keyword arguments, runs an awaitable result to completion so async functions are checkable, and returns the function's Result
    And function_map maps each name a reference or call expression can hold to its callable, so a function that takes another function is reachable by naming its argument with no callable embedded in the data
    And it returns a Fault when an expression names a function the map does not hold, or is otherwise malformed
    And it performs no I/O of its own; the functions under test are injected through the map

  Scenario: generate_scaffolding generates the Gherkin step scaffolding for a chain from its link declarations
    Given chain_name: str and links: list of Link
    When generate_scaffolding is called
    Then it returns a step-module source string whose handlers are pure functions that take the immutable context plus bound captures and return a new context, wired through a register(registry) that returns the registry — never through decorators or a mutable shared context, matching honest-gherkin's step-module contract
    And the developer writes only the .feature files against this scaffolding, which is marked do-not-edit
    And it reads no world and returns the generated source as a string

  Scenario: build_proof_event builds one hf.proof.checked event for a function honest-test proved
    Given function_name: str and scenario: str and cases_run: int and outcome: ProofOutcome and line_coverage: int and branch_coverage: int
    When build_proof_event is called
    Then it returns a ProofEvent record for the host runner to emit through an injected honest-observe runtime, so honest-test's core takes no dependency on honest-observe
    And function_name is the fully-qualified name that is the function's gherkin requirement and its function-point unit
    And a function earns outcome proved only when honesty, full coverage and the gherkin's Then value oracle all hold; a run where any does not emits failed
    And it reads no world and returns pure data; the emit is the runner's boundary

  Scenario: law states one property as data for the generative law runner
    Given identifier: str and statement: str and check: Callable
    When law is called
    Then it returns a Law record of those three fields: the identifier, the plain-language statement, and the check
    And check is the pure predicate the property is proven by — a function from one subject to a list of violation messages, empty when the property holds and one message per violation, which never raises and never returns a bare boolean
    And it is reached only by import — honest-type, honest-persist and honest-test's own suite import it in their conformance runners — so it is an import surface, not a stage of the run
    And it reads no world and returns pure data

  Scenario: verify_laws runs every law against every subject and returns the run record
    Given laws: list of Law and subjects: list of Subject
    When verify_laws is called
    Then it applies each law's check to each subject's params and returns a LawRun of passed, total and violations
    And it counts the law-and-subject pairs that held as passed and the pairs checked as total
    And it collects one Violation per failed pair, each naming the law's identifier, its statement, the subject, and the messages the check returned
    And it is reached only by import, not by run_suite; each check is a pure predicate the caller supplied, so it reads no world and returns pure data

  Scenario: resolve_supplied_config builds the supplied-values record from the decoded table
    Given table: dict of str to any
    When resolve_supplied_config is called
    Then it returns a SuppliedConfig, a map from predicate name to that predicate's SuppliedEntry — its valid list, its invalid list and its strategy
    And it reads the decoded table as data, builds the record the generators take, and touches no world
    And a predicate absent from the table yields the missing-entry warning rather than a file lookup

  Scenario: render_report renders the finished RunReport into the section 11 layout
    Given report: RunReport
    When render_report is called
    Then it returns the section 11 output text — the chains, links and vocabularies found, the permutations run and failures, the adversarial inputs rejected, the honesty and chain-contract results, the state-machine tallies, and the totals
    And it reads the finished report as data and returns the rendered string, touching no world
    And the verdict is already in the report; render_report only lays it out

  Scenario: build_run_report assembles the RunReport from the measured parts
    Given chains: int and links: int and vocabularies: int and permutations: int and failures: int and adversarial_rejected: int and coverage: CoverageReport and mutation_caught: int and mutation_total: int
    When build_run_report is called
    Then it returns a RunReport record carrying the counts the run measured, so a pure function produces the report rather than an orchestrator assembling it inline
    And it reads its arguments as data and touches no world
    And render_report and the two sinks take the RunReport it produced

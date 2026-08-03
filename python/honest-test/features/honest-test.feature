Feature: honest-test — Python supplement
  Scenarios that can only be stated in host-language terms: walking the Python syntax tree to
  read length bounds and classify predicates, reading a live function's source, and parsing
  the configuration file. Counted toward the module's function points alongside the neutral
  scenarios in specs/features/honest-test.feature.

  Scenario: _is_len_call recognises a length call in the syntax tree
    Given a syntax-tree node and the source it came from
    When _is_len_call inspects it
    Then it reports true only when the node calls the length builtin

  Scenario: _int_value reads an integer literal from the syntax tree
    Given a syntax-tree node and the source it came from
    When _int_value reads it
    Then it returns the integer value when the node is an integer literal, otherwise nothing

  Scenario: _bound_from_pair derives a length bound from one comparison
    Given the left node, the operator, the right node, the source, and the bounds so far
    When _bound_from_pair inspects the comparison
    Then it records a bound when one side is a length call and the other an integer literal
    And it flips the operator when the length call is on the right
    But any other comparison contributes nothing

  Scenario: _scan_comparison derives bounds from a chained comparison
    Given a comparison node, the source, and the bounds so far
    When _scan_comparison flattens it into operand-operator-operand triples
    Then it derives a bound from each adjacent triple

  Scenario: extract_length_bounds reads the allowed length range from predicate source
    Given the source text of a predicate
    When extract_length_bounds walks its syntax tree for length comparisons
    Then it returns the minimum and maximum length the predicate allows
    And the minimum defaults to one and the maximum is absent when there is no upper bound

  Scenario: _callee_identifier records the fact a bare-name call signals
    Given a callee identifier node, the source, and the facts so far
    When _callee_identifier inspects the name
    Then it records the mapped fact for a recognised builtin
    And it records an unrecognised, non-ignored name as a named call

  Scenario: _callee_attribute records a character-class fact from a method call
    Given a callee attribute node, the source, and the facts so far
    When _callee_attribute inspects the attribute
    Then it records the character-class fact when the method is a character-class test

  Scenario: _fact_call routes a call node to the right callee handler
    Given a call node, the source, and the facts so far
    When _fact_call reads the callee
    Then it dispatches an identifier or attribute callee to its handler, ignoring others

  Scenario: _fact_comparison records that the source compares values
    Given a comparison node, the source, and the facts so far
    When _fact_comparison reads it
    Then it records that a comparison is present

  Scenario: _fact_numeric_literal records that the source contains a number
    Given a numeric-literal node, the source, and the facts so far
    When _fact_numeric_literal reads it
    Then it records that a numeric literal is present

  Scenario: _fact_true records that the source is an always-true predicate
    Given a true-literal node, the source, and the facts so far
    When _fact_true reads it
    Then it records the catch-all fact

  Scenario: _collect_facts gathers every classification fact from predicate source
    Given the source text of a predicate
    When _collect_facts walks its syntax tree
    Then it returns the facts found, with the numeric fact set when a numeric call appears or a comparison meets a numeric literal

  Scenario: classify_source classifies a predicate from its source text
    Given the source text of a predicate and the set of codebase names
    When classify_source weighs the facts by precedence
    Then it returns the most specific self-contained class, or composite for a known codebase call, external for an unknown call, and unknown otherwise

  Scenario: classify_predicate classifies a live predicate by reading its source
    Given a live predicate recognizer or callable and the set of codebase names
    When classify_predicate reads the function's source and classifies it
    Then it returns the class from the source
    But a function whose source cannot be read is treated as external

  Scenario: load_config reads and parses the configuration file
    Given the path to the configuration file
    When load_config reads it
    Then it returns the parsed contents using the standard-library parser
    But it returns an empty configuration when the file is absent

  Scenario: _bound_registry builds a per-case registry that binds the case data directly
    Given a value case and the function map
    When _bound_registry builds the registry
    Then it registers the supply-input, call-function, and assert-oracle steps with the concrete data bound directly, resolving the function inside the step so an unknown name surfaces as a caught fault

  Scenario: _settle runs an awaitable result to completion
    Given the result of calling a function under test
    When _settle settles it
    Then an awaitable is run to completion so async functions are value-checkable, and a plain value is returned unchanged

  Scenario: _invoke calls the function under test per the value case
    Given a value case and the function map
    When _invoke calls the function
    Then it calls with positional args, keyword args, or a single input, evaluating each argument and settling an awaitable result

  Scenario: test_body_violations flags runtime rebinding in a test body
    Given a test module's source
    When test_body_violations scans it
    Then it flags the monkeypatch fixture, mock.patch or patch.object, setattr on an imported symbol, and attribute assignment on an imported symbol, and leaves honest tests and local mutation alone

  Scenario: rebind_report formats the collection-failure message for a test body's rebinds
    Given a list of rebinding violations
    When rebind_report formats them
    Then it returns None for an empty list, and otherwise a message naming each site by line, joined with a semicolon

  Scenario: pytest_pycollect_makemodule fails collection of a test module that rebinds a call target
    Given a Python test module about to be collected
    When pytest_pycollect_makemodule reads its source
    Then it raises a CollectError when the body rebinds a call target, and returns nothing so an honest module builds normally

  Scenario: _is_boundary reports whether a link declared itself a boundary
    Given a link
    When _is_boundary reads its metadata
    Then it is true only when the link was declared boundary=True

  Scenario: _adversarial_rejections counts near-misses and how many recognizers reject
    Given a vocabulary
    When _adversarial_rejections perturbs every bounded member
    Then it returns the total near-miss count and how many the recognizers reject, skipping unbounded predicate types that have no members to perturb

  Scenario: _idempotency returns the chain's idempotency verdict
    Given a chain's links, its enumerated manifests, and its boundary links
    When _idempotency judges it
    Then it is exempt when a boundary link is present, and otherwise true only when every enumerated manifest repeats

  Scenario: _honesty builds the chain's honesty record
    Given a chain's links and its enumerated manifests
    When _honesty checks them
    Then it records purity and mutation over every non-boundary link on a fresh copy of every manifest, the idempotency verdict, and the names of the declared boundary links

  Scenario: _format_vocab_line renders the vocabulary term line
    Given the bounded vocabulary terms
    When _format_vocab_line renders them
    Then it joins each name and member count with a times sign

  Scenario: _format_honesty renders the honesty line
    Given a chain's honesty record
    When _format_honesty renders it
    Then it shows the purity, mutation, and idempotency marks, and appends the comma-joined boundary link names only when there are boundary links

  Scenario: _format_chain renders a chain's section-11 block
    Given a chain result record
    When _format_chain renders it
    Then it emits the name, link count, vocabulary line, permutations, pass or fail running line, adversarial line, honesty line, and chain-contract line

  Scenario: _format_state_machine renders a state machine's block
    Given a state-machine result record
    When _format_state_machine renders it
    Then it emits the name, the state, event, and transition counts, the valid-transition line, and the invalid-transition line

  Scenario: _header renders the report header with the discovery counts
    Given the list of result records
    When _header renders it
    Then it emits the tool banner and the count of chains, links, and vocabularies across the chain records

  Scenario: _footer renders the totals footer
    Given the list of result records
    When _footer renders it
    Then it emits the total permutations and failures, the total adversarial inputs and rejections, the honest and boundary link counts, and the total BDD scenarios

  Scenario: _link_checks runs one link's honesty probes on a fresh copy of every manifest
    Given a link and the enumerated manifests
    When _link_checks probes it
    Then it reports whether the link is pure and mutation-free on a fresh copy of every manifest, so one probe cannot hide another

  Scenario: _first_fault finds the first faulting link in a chain run
    Given a chain's links and a manifest
    When _first_fault runs them in sequence
    Then it returns the index of the first link that returns a non-ok result, feeding each link the previous link's output, or None when the chain runs clean

  Scenario: _adversarial_tokens counts the near-miss state and event tokens
    Given a state machine
    When _adversarial_tokens counts its perturbations
    Then it counts every state's neighbours (only when there is an event to pair with) plus every event's neighbours

  Scenario: _run_discovered_chain verifies a chain and attaches its BDD result
    Given a discovered chain and the feature runner
    When _run_discovered_chain runs it
    Then it verifies the chain and attaches the feature's scenario counts when the developer wrote a feature, and returns the bare result otherwise

  Scenario: _chain_ok decides whether one chain passed
    Given a chain result record
    When _chain_ok judges it
    Then it is true only when every permutation ran clean, every near-miss was rejected, the contracts held, and the non-boundary links are honest, treating boundary-exempt idempotency as not a failure

  Scenario: _coverage builds the section-9.5 coverage document
    Given the run's result records and a timestamp
    When _coverage assembles them
    Then it records complete vocabulary coverage, measured honesty coverage, the observed fault-exit coverage per chain, and the fired-transition coverage per state machine

  Scenario: _walk lists the source files under a directory
    Given a source directory
    When _walk scans it
    Then it returns every .py file under it, sorted for a deterministic order

  Scenario: _read reads a source file's bytes
    Given a file path
    When _read reads it
    Then it returns the file's bytes, which the declaration graph is parsed from

  Scenario: _import imports a source file as a live module
    Given a file path
    When _import imports it
    Then it returns the module with its declared chains and machines as live objects

  Scenario: _run_feature runs a chain's developer feature when one exists
    Given a discovered chain
    When _run_feature looks for its feature
    Then it scaffolds the chain's step registry and runs features/<name>.feature returning the scenario counts, or None when there is no feature for the chain

  Scenario: _write writes text to a file
    Given a path and text
    When _write writes it
    Then the text is written to the file, which is how the coverage document is persisted

  Scenario: _now returns the current time as an ISO-8601 string
    Given the system clock
    When _now reads it
    Then it returns the current UTC time as an ISO-8601 string for the coverage document's timestamp

  Scenario: main scans a source directory and returns the process exit code
    Given command-line arguments
    When main runs
    Then it scans the given source directory (default src), prints the report, writes coverage.json, and returns 0 only when every chain and machine passed

  Scenario: _finding builds a component-isolation finding
    Given a code and a detail
    When _finding assembles them
    Then it returns a finding with that code and detail, the data shape the isolation checks emit

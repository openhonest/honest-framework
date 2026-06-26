Feature: honest-test — exhaustive generation, honesty checks, and conformance laws
  One scenario per function. The declaration is the test specification: bounded vocabularies
  become exhaustive test spaces, honesty checks confirm links behave as Honest Code requires,
  and conformance laws assert universal properties. Each scenario names the single behaviour
  the proof stands on; the count of scenarios is the module's directly-counted
  function-point size. Host-language specifics live in the python supplement.

  Scenario: _options lists the values a type contributes to the product
    Given a type, its recognizer, and the optional binding
    When _options gathers its values
    Then it returns the type's Set members in sorted order
    And it adds the absent case when the type is maybe-bound

  Scenario: enumerate_sets builds every combination of bounded Set members
    Given a vocabulary and an optional binding
    When enumerate_sets runs
    Then it returns the full combination of every bounded Set's members, one case per combination
    But unbounded predicate types do not take part

  Scenario: _apply accumulates a length bound, keeping the tightest
    Given a side to set, a candidate value, and the bounds so far
    When _apply records it
    Then the minimum rises to the larger value and the maximum falls to the smaller
    And an exact length sets both at once

  Scenario: _string_of_length builds a string of an exact length
    Given a target length and an alphabet
    When _string_of_length builds it
    Then it returns a string of exactly that length, repeating the alphabet as needed
    But a length of zero or less yields the empty string

  Scenario: enumerate_lengths generates valid and boundary-invalid strings for a length-bounded predicate
    Given the source of a length-bounded predicate
    When enumerate_lengths runs
    Then it returns a valid string at every allowed length and boundary strings just outside the range
    But when the predicate has no upper bound it returns no strings, leaving the work to supplied values

  Scenario: law packages a conformance property
    Given an identifier, an English statement, and a check over a subject
    When law packages them
    Then it returns the law carrying all three

  Scenario: verify_laws runs every law over every subject
    Given a list of laws and a list of labelled subjects
    When verify_laws runs each law's check over each subject
    Then it returns a report of how many passed, how many failed, the total, and every violation
    And each violation names the law, its statement, the subject, and the failure messages

  Scenario: edit_distance_1 generates single-edit neighbours of a value
    Given a value
    When edit_distance_1 varies it
    Then it returns every deletion, insertion, and substitution by one character
    And it adds case variations and leading, trailing, and interior whitespace variations

  Scenario: unicode_confusables generates look-alike substitutions of a value
    Given a value
    When unicode_confusables substitutes look-alike characters
    Then it replaces each position with every confusable for that character
    And it adds one fully homoglyph-substituted form when that differs from the original

  Scenario: control_characters injects control and zero-width characters into a value
    Given a value
    When control_characters injects each control, bidi-override, and zero-width character
    Then it returns the value with that character prepended, appended, and inserted at the midpoint

  Scenario: length_extensions pads a value to sizes that expose buffer assumptions
    Given a value
    When length_extensions pads it
    Then it returns the value repeated many times over and padded to fixed-buffer boundary sizes

  Scenario: encoding_variants applies encoding attacks to a value
    Given a value
    When encoding_variants transforms it
    Then it returns a byte-order-mark prefix, a double percent-encoding, and whitespace-substitution forms

  Scenario: adversarial_neighbours gathers every adversarial neighbour of a value
    Given a value
    When adversarial_neighbours runs every generation class over it
    Then it returns the de-duplicated, sorted neighbours, excluding the value itself
    And a correct recognizer must reject every one of them

  Scenario: fibonacci_sequence lists Fibonacci values in both directions from zero
    Given a magnitude limit
    When fibonacci_sequence builds the sequence
    Then it returns the negatives largest-magnitude-first followed by the non-negative values up to the limit

  Scenario: numeric_values selects test values for a numeric predicate
    Given a limit and the choices of including negatives and using fractional values
    When numeric_values builds the values
    Then it returns the Fibonacci values, dropping those below zero when negatives are excluded
    And it divides each by one hundred when fractional values are requested

  Scenario: _finding records an honesty violation as data
    Given a violation code, the subject it concerns, and a message
    When _finding records it
    Then it returns the violation as data carrying the code, subject, and message

  Scenario: _is_boundary reports whether a link is declared at a boundary
    Given a link
    When _is_boundary reads its declaration
    Then it reports true when the link is marked as a boundary, otherwise false

  Scenario: _name reports the readable name of a link
    Given a link
    When _name reads it
    Then it returns the link's declared name, falling back to its own name when none is declared

  Scenario: _to_slots re-keys an enumerated case to the slots a link receives
    Given an enumerated case of type-to-value and the link's binding
    When _to_slots re-keys it
    Then it returns the values keyed by the slot each type binds to, leaving unbound types under their own name

  Scenario: verify_purity confirms a link returns the same result for the same input
    Given a link and a manifest
    When verify_purity runs the link twice on that manifest
    Then it returns a non-deterministic finding when the two results differ, otherwise nothing
    But a link declared at a boundary is exempt and yields nothing

  Scenario: detect_mutation confirms a link does not modify its input
    Given a link and a manifest
    When detect_mutation runs the link and compares the manifest before and after
    Then it returns a mutation finding when the manifest changed, otherwise nothing

  Scenario: verify_idempotency confirms a chain run twice gives the same result
    Given a chain of links and a manifest
    When verify_idempotency runs the chain twice on the same manifest
    Then it returns a not-idempotent finding when the two results differ, otherwise nothing
    But a chain containing any boundary link is exempt and yields nothing

  Scenario: enumerate_test_cases builds test manifests for a link from its accepts vocabulary
    Given a vocabulary and a binding
    When enumerate_test_cases builds the cases
    Then it returns the Set combinations, each keyed by the slot the link receives

  Scenario: test_chain_contracts confirms each link accepts the previous link's valid output
    Given a chain of links
    When test_chain_contracts feeds each link's valid outputs to the next
    Then it returns a finding only when a link rejects valid upstream output with a server fault
    But a link rightly rejecting bad data with a client fault is not a violation
    And a producing link that declares no accepts vocabulary is skipped

  Scenario: _finding records a transition violation as data
    Given a violation code and the detail it concerns
    When _finding records it
    Then it returns the transition violation as data carrying the code and the detail

  Scenario: _is_err reports whether a result is a fault of a given code
    Given a result and a fault code
    When _is_err inspects the result
    Then it reports true only when the result is a fault carrying that code

  Scenario: _first selects the lowest-ordered name from a collection
    Given a collection of names
    When _first picks one
    Then it returns the lowest in order, or nothing when the collection is empty

  Scenario: test_valid_transitions confirms every declared transition produces its target
    Given a state machine
    When test_valid_transitions exercises every declared state-and-event pair
    Then it returns a finding for each declared pair that does not produce its declared next state

  Scenario: test_invalid_transitions confirms undeclared pairs are refused
    Given a state machine
    When test_invalid_transitions exercises every state-and-event pair absent from the table
    Then it returns a finding for each absent pair that is not refused with a no-transition fault

  Scenario: test_adversarial_transitions confirms near-miss tokens are rejected
    Given a state machine
    When test_adversarial_transitions feeds adversarial neighbours of each state and event
    Then it returns a finding for each neighbour state accepted in place of a real state
    And a finding for each neighbour event accepted in place of a real event
    But an empty machine with no states or events is skipped

  Scenario: supplied_for returns the developer-supplied values for a predicate
    Given a parsed configuration and a predicate name
    When supplied_for looks it up
    Then it returns the valid examples, the invalid examples, and the strategy for that predicate
    But it returns nothing when there is no entry for that predicate

  # proof
  Scenario: proof_payload builds one function's proof record
    Given a function's name, its gherkin, the cases run, the result, and its coverage
    When proof_payload assembles them
    Then it returns the proof record carrying every field

  Scenario: emit_proofs records a run's proofs through the injected emit
    Given an emit and a list of per-function proofs
    When emit_proofs runs
    Then it emits one proof event per function, keyed by the function's name
    And an empty run emits nothing

  Scenario: decide_proof grants proved only when all three legs hold
    Given whether honesty and coverage hold, the function's value-oracle results, and whether it is value-oracle exempt
    When decide_proof decides
    Then it returns proved only when honesty holds, coverage is full, and the value oracle ran with every case passing
    But any missing leg returns failed, naming it — an unrun oracle is a failure, not a vacuous proof — unless the function is declared exempt, which waives the value-oracle leg only, never honesty or coverage

  # value-assertion oracle (section 8.6)
  Scenario: _oracle_expected checks the result equals the known-good value
    Given a case carrying an expected value and a function result
    When _oracle_expected checks it
    Then it holds when the result equals the expected value, and fails as data otherwise

  Scenario: _oracle_fault checks the result is a fault with the declared code
    Given a case carrying a fault code and a function result
    When _oracle_fault checks it
    Then it holds when the result is an error carrying that code, and fails as data otherwise

  Scenario: _oracle_ok checks the result is ok
    Given a case asking for an ok result and a function result
    When _oracle_ok checks it
    Then it holds when the result is an ok result, and fails as data otherwise

  Scenario: _oracle_field checks one named field of the result
    Given a case naming a field and its value and a function result
    When _oracle_field checks it
    Then it holds when that field of the result equals the value, and fails as data otherwise

  Scenario: _oracle_kind names the oracle a case declares
    Given a value case
    When _oracle_kind reads it
    Then it returns the first recognised oracle key the case carries, or nothing when it declares none

  Scenario: check_oracle runs the oracle a case declares against a result
    Given a value case and a function result
    When check_oracle runs it
    Then it dispatches to the declared oracle and asserts it, rejecting a case that declares none

  Scenario: run_value_case runs one value case through the engine
    Given a value case and the function map
    When run_value_case runs it
    Then it proves when every step is ok, and otherwise reports the first fault as data
    But an unknown or raising function is reported as an errored step, never a crash

  Scenario: run_value_cases runs every value case against the function map
    Given a list of value cases and the function map
    When run_value_cases runs them
    Then it returns one result per case, the executable face of the suite.json value contract

  Scenario: _eval evaluates a value-case argument against the function map
    Given an argument expression and the function map
    When _eval evaluates it
    Then a literal is itself, a list evaluates each element, a reference resolves the named callable, and a call applies the named function to its evaluated arguments recursively, so a function-taking function needs no callable in the data, even inside a list

  Scenario: nondeterministic_watch_list lists the sources a pure link must not call
    Given the framework's non-determinism rules
    When nondeterministic_watch_list is asked
    Then it returns the call-form non-deterministic sources the runtime monitor traps, mirroring honest-check's HC008 list

  Scenario: nondeterminism_finding decides whether a link's calls are honest
    Given a link name, its boundary flag, and the sources it called
    When nondeterminism_finding decides
    Then a non-boundary link that called any source is a warning naming them, while a boundary link or one that called none is honest

  Scenario: _recorder wraps a watched symbol to record its call
    Given a watched symbol path, its original, and a detected list
    When _recorder wraps it
    Then the wrapper records the path and delegates to the original so the link still runs

  Scenario: call_monitor traps every watch-list symbol for the duration of a run
    Given a watch list
    When call_monitor patches the symbols and the run calls them
    Then it records every call and restores each original on exit

  Scenario: verify_determinism flags a non-boundary link that touches a non-deterministic source
    Given a link and a manifest
    When verify_determinism runs the link under the monitor
    Then it warns for a non-boundary link that touched a source, and is silent for a boundary link or a link that touched none

  Scenario: auth_token_classes lists the seven token classes
    Given an authorization contract
    When auth_token_classes is asked
    Then it returns the seven token classes that probe the contract, beginning with the valid authorized one

  Scenario: map_fault_to_http maps a fault to its HTTP status
    Given a fault with a category
    When map_fault_to_http maps it
    Then a forbidden guard fault is 403, an unauthenticated one 401, a client fault 400, and anything else 500

  Scenario: auth_expected_status gives the expected outcome for a token class
    Given a token class and an optional provider fault mapping
    When auth_expected_status is asked
    Then it returns ok for a valid authorized token and the expected HTTP status otherwise, with the provider mapping overriding the default

  Scenario: auth_honesty_finding decides whether a class outcome is honest
    Given a token class, the chain result, and the expected outcome
    When auth_honesty_finding decides
    Then a valid authorized token must be accepted and every other class must fault with the expected status, returning a finding otherwise

  Scenario: test_auth_honesty runs the auth honesty test over an authorizing link
    Given an authorizing link, an injected provider, and a chain run
    When test_auth_honesty runs the seven classes
    Then it returns a finding for each class that behaved dishonestly, and nothing for a non-authorizing link or when no provider is registered

  Scenario: _pct gives a coverage percentage as a whole number
    Given a part and a whole
    When _pct computes the percentage
    Then it returns the rounded part-of-whole percentage, or 100 when there is nothing to cover

  Scenario: vocabulary_coverage reports a vocabulary's exercised members
    Given a total and exercised member count
    When vocabulary_coverage reports it
    Then it returns the total, exercised, and percentage

  Scenario: chain_coverage reports a chain's exercised fault paths
    Given a fault-path total and exercised count
    When chain_coverage reports it
    Then it returns the fault paths, exercised, and percentage

  Scenario: honesty_coverage reports a chain's honest links
    Given the link total, honest count, and boundary count
    When honesty_coverage reports it
    Then it returns the total, honest, boundary, and percentage

  Scenario: state_machine_coverage reports a machine's exercised transitions
    Given a transition total and exercised count
    When state_machine_coverage reports it
    Then it returns the transitions, exercised, and percentage

  Scenario: build_coverage assembles the coverage document
    Given the four coverage maps and a timestamp
    When build_coverage assembles them
    Then it returns the document with the version, timestamp, and the vocabulary, chain, honesty, and state-machine maps

  Scenario: write_coverage writes coverage.json through the injected writer
    Given a coverage document, a path, and an injected write
    When write_coverage writes it
    Then it serializes the document and writes it to the path so honest-check can read it back

  Scenario: _edit replaces a byte range of the source
    Given a source, a start and end byte, and a replacement
    When _edit applies it
    Then it returns the source with that byte range replaced

  Scenario: _mutant records one mutation
    Given an operator, a label, the source, a byte range, and a replacement
    When _mutant records it
    Then it returns the operator, label, and the mutated source

  Scenario: _comparison_swaps mutates every comparison operator
    Given source with comparison operators
    When _comparison_swaps mutates it
    Then it returns one mutant per site with each operator swapped to its pair

  Scenario: _number_shifts shifts every integer literal
    Given source with integer literals
    When _number_shifts mutates it
    Then it returns a mutant for n+1 and a mutant for n-1 at each literal

  Scenario: _condition_flips flips boolean operators and drops a not
    Given source with and/or operators and not operators
    When _condition_flips mutates it
    Then it swaps and with or and drops a not at each site

  Scenario: _constant_replaces swaps booleans and empties strings
    Given source with True/False literals and non-empty strings
    When _constant_replaces mutates it
    Then it swaps True with False and empties each non-empty string literal

  Scenario: _result_swaps swaps ok and err calls
    Given source with ok and err calls
    When _result_swaps mutates it
    Then it swaps the callee ok with err and vice versa at each call

  Scenario: _membership_changes swaps in and not in
    Given source with in and not in operators
    When _membership_changes mutates it
    Then it swaps in with not in at each membership site

  Scenario: _line_removals deletes one statement at a time
    Given source with a block of two or more statements
    When _line_removals mutates it
    Then it returns a mutant with each statement deleted, leaving a sole statement alone

  Scenario: enumerate_mutants produces every mutant of the source
    Given module source
    When enumerate_mutants runs every operator over it
    Then it returns the full list of mutants, each an operator, a label, and the mutated source

  Scenario: run_mutants returns the mutants a suite does not catch
    Given a list of mutants and an injected suite-runner
    When run_mutants checks each mutant against the suite
    Then it returns the survivors — the mutants that leave the suite still passing

  Scenario: mutation_adequacy accounts caught plus set-aside against the total
    Given the mutants, the survivors, and a set-aside map of equivalent mutants by label
    When mutation_adequacy reports
    Then it returns the totals with each survivor either declared equivalent or undeclared, and adequate only when none are undeclared

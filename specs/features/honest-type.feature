Feature: honest-type — vocabulary, classification, chains, and the boundary
  One scenario per function. honest-test's auto-generation proves every case;
  each scenario names the single behaviour that proof stands on, and the count of
  scenarios is the module's directly-counted function-point size.

  # types.py

  Scenario: ticket records the type a token was classified as
    Given a type name and a token value
    When ticket records them
    Then it yields a ticket carrying that type and value

  Scenario: rejection records a token that could not be placed
    Given a token, a reason, and optional detail
    When rejection records them
    Then it yields a rejection carrying that token, reason, and detail
    But when no detail is given the detail is nothing

  Scenario: fault records a processing error as data
    Given a code, a message, a category, and optional detail
    When fault records them
    Then it yields a fault carrying that code, message, category, and detail
    But when no detail is given the detail is nothing

  Scenario: ok wraps a manifest as a successful result
    Given a manifest
    When ok wraps it
    Then it yields a result marked as success carrying that manifest

  Scenario: err wraps a fault as a failed result
    Given a fault
    When err wraps it
    Then it yields a result marked as failure carrying that fault

  # recognizers.py

  Scenario: predicate builds an open-ended recognizer from a test
    Given a test that answers yes or no for a token
    When predicate builds a recognizer from it
    Then it yields a recognizer tagged as a predicate holding that test

  Scenario: insensitive builds a case-folding membership recognizer
    Given a collection of member words
    When insensitive builds a recognizer from them
    Then it yields a recognizer tagged as case-insensitive whose members are all lowercased

  Scenario: normalize coerces a declaration into a recognizer
    Given a vocabulary declaration
    When normalize coerces it
    Then a bare collection becomes a membership recognizer over those values
    But an already-tagged recognizer passes through unchanged

  Scenario: _match_set decides membership against a recognizer's values
    Given a token and a membership recognizer
    When _match_set checks the token
    Then it answers yes only when the token is one of the recognizer's values

  Scenario: _match_insensitive decides membership ignoring case
    Given a token and a case-insensitive recognizer
    When _match_insensitive checks the token
    Then it answers yes only when the token, lowercased, is one of the recognizer's values

  Scenario: _match_predicate decides a match by running the recognizer's test
    Given a token and a predicate recognizer
    When _match_predicate checks the token
    Then it answers with the result of running the recognizer's test on the token

  Scenario: recognize decides whether a token matches a recognizer
    Given a token and a recognizer
    When recognize checks the token
    Then it answers yes or no by dispatching on the recognizer's kind

  Scenario: is_bounded reports whether a recognizer enumerates a finite set
    Given a recognizer
    When is_bounded inspects it
    Then it answers yes for a membership recognizer
    But it answers no for a predicate recognizer

  Scenario: members returns the enumerated values of a bounded recognizer
    Given a recognizer
    When members reads it
    Then it returns the recognizer's members for a bounded recognizer
    But it returns an empty collection for a predicate recognizer

  # reserved.py

  Scenario: is_reserved reports whether a token is a reserved word
    Given a token
    When is_reserved checks it
    Then it answers yes when the token is among the reserved words, otherwise no

  Scenario: reservation_layer names the layer that reserves a token
    Given a token
    When reservation_layer inspects it
    Then it returns the name of the layer that reserves the token
    But if no layer reserves it, it returns nothing

  # vocabulary.py

  Scenario: maybe marks a binding slot as optional
    Given a slot name
    When maybe marks it
    Then it yields an optional slot wrapper carrying that name

  Scenario: is_maybe reports whether a slot is optional
    Given a slot or an optional slot wrapper
    When is_maybe inspects it
    Then it answers yes only for an optional slot wrapper

  Scenario: unwrap_maybe yields the bare slot name
    Given a slot or an optional slot wrapper
    When unwrap_maybe reads it
    Then it returns the plain slot name whether or not it was wrapped as optional

  Scenario: composed declares a multi-token type
    Given a name, the required base types and values, and the captured base type
    When composed declares them
    Then it yields a composed type that matches when the required values are present and binds the captured value

  Scenario: _check_reserved rejects a bounded type that uses a reserved word
    Given a type name and its recognizer
    When _check_reserved inspects a bounded recognizer
    Then it raises a vocabulary error naming the reserved member and its layer
    But it does nothing for a predicate recognizer

  Scenario: _check_overlap rejects two bounded types that share a value
    Given the base types of a vocabulary
    When _check_overlap compares every pair of bounded types
    Then it raises a vocabulary error naming the two types and the shared values
    And it leaves non-overlapping types alone

  Scenario: _accepts samples whether a recognizer accepts a token, tolerating a raise
    Given a recognizer and a sample token
    When _accepts applies the recognizer
    Then it returns whether the token is accepted, counting a predicate that raises as not accepting it

  Scenario: _check_catch_all rejects a predicate that accepts nearly all inputs
    Given the base types of a vocabulary
    When _check_catch_all samples each predicate against the fixed corpus
    Then it raises a vocabulary error when a predicate accepts more than 95 percent of the sample, leaving discriminating recognizers and bounded sets alone

  Scenario: _check_composed rejects a composed type referencing an unknown base
    Given the base types and the composed types
    When _check_composed validates each composed type
    Then it raises a vocabulary error when a required or captured type is not a declared base

  Scenario: vocabulary builds a validated vocabulary from declarations
    Given base declarations and optional composed types
    When vocabulary builds them
    Then it normalizes each declaration and checks reserved words, overlaps, and composed bases
    But an empty set of declarations raises a vocabulary error

  Scenario: _type_names lists every type name a vocabulary defines
    Given a vocabulary
    When _type_names reads it
    Then it returns the names of all base and composed types together

  Scenario: merge combines two vocabularies into one
    Given two vocabularies
    When merge combines them
    Then it yields one vocabulary holding both sets of types
    But a name collision or a shared bounded value raises a vocabulary error

  Scenario: binding builds a binding table from type names to slots
    Given a table mapping type names to slot names
    When binding builds it
    Then it yields that mapping as plain data

  Scenario: auto_binding makes every type its own slot
    Given a vocabulary
    When auto_binding builds the identity binding
    Then every base and composed type name maps to a slot of the same name

  # chains.py

  Scenario: link declares a function as a chain link with metadata
    Given vocabulary and role metadata for a step
    When link declares a function with it
    Then it attaches that metadata to the function and leaves its behaviour unchanged

  Scenario: is_link reports whether a function was declared a link
    Given a function
    When is_link inspects it
    Then it answers yes only when the function carries link metadata

  Scenario: link_meta returns a declared link's metadata
    Given a function
    When link_meta reads it
    Then it returns the link's name, accepted and bound vocabulary, boundary and authorization marks, and emitted events
    But for an undeclared function it returns nothing

  Scenario: execute_chain runs links in sequence and short-circuits on failure
    Given a sequence of links and a starting manifest
    When execute_chain runs them
    Then it feeds each link's manifest to the next and returns the first failure if one occurs
    And if a link returns neither success nor failure it returns a server fault

  Scenario: chain composes links into a single link
    Given several links
    When chain composes them
    Then it yields one link that runs them in sequence and short-circuits

  Scenario: _run_validate_all runs every link against the same manifest
    Given a sequence of links and a manifest
    When _run_validate_all runs them all against that manifest
    Then it succeeds only when every link succeeds
    But if any fails it yields one failure carrying every result, success and failure alike

  Scenario: validate_all composes accumulating checks into a single link
    Given several validation links
    When validate_all composes them
    Then it yields one link that runs them all against the same manifest and preserves the full picture on failure

  # classify.py

  Scenario: _safe_recognize runs a recognizer without leaking a thrown error
    Given a token and a recognizer
    When _safe_recognize runs the recognizer
    Then it returns whether the token matched and no error
    But if the recognizer's test throws it returns no match and the error message

  Scenario: _classify_token turns one token into a ticket, a rejection, or a fault
    Given one token and a vocabulary
    When _classify_token classifies it
    Then a token matching exactly one type becomes a ticket
    And a token matching no type becomes an unrecognized rejection
    And a reserved word matched only by a predicate becomes a reserved-word rejection
    But a test that throws becomes a predicate-error fault

  Scenario: _requirements_met reports whether a composed type's requirements are present
    Given a composed type and the classified tickets
    When _requirements_met checks the requirements
    Then it answers yes only when every required type is present with the required value

  Scenario: _resolve_bindings binds tickets to slots across the composition passes
    Given the tickets, rejections, vocabulary, and binding
    When _resolve_bindings runs
    Then a satisfied composed type captures its token and binds it to the composed slot, overriding the base binding
    And remaining tickets bind to their slots, with an unbound type or a duplicate slot recorded as a rejection
    And an unmatched optional slot is filled with nothing
    And a required type with no token provided is recorded as a missing-required rejection

  Scenario: classify turns tokens into a manifest against a vocabulary
    Given a list of tokens, a vocabulary, and an optional binding
    When classify runs
    Then it classifies each token and resolves the bindings into a manifest
    And a token that is nothing or empty becomes a rejection rather than failing
    But a token that is not text yields a server fault

  # boundary.py

  Scenario: catch_at_boundary wraps a handler so faults become rendered output
    Given a handler, a table from fault codes to output, success output, and server and client defaults
    When catch_at_boundary wraps the handler and the wrapper runs
    Then a success is rendered by the success output
    And a fault is rendered by its code's output, or the category default if its code is not listed
    But an unhandled error from the handler is rendered as a server fault

  Scenario: check_rejections turns manifest rejections into a result before the chain
    Given a manifest carrying rejections and a rejection policy
    When check_rejections applies the policy
    Then any rejection the policy marks blocking yields a client fault
    But otherwise the manifest is returned clean with its rejections stripped

  # state_machine.py

  Scenario: _names extracts the declared names from a states or events declaration
    Given a states or events declaration
    When _names reads it
    Then it returns the member names whether the declaration is a vocabulary or a plain set of names

  Scenario: state_machine builds a validated transition table
    Given states, events, transitions, an initial state, and optional terminal states
    When state_machine builds the machine
    Then it yields a machine carrying the states, events, transitions, and initial and terminal states
    But it raises a state-machine error when a transition references an unknown state or event, lands on an unknown state, or the initial state is undeclared

  Scenario: transition applies one event to compute the next state
    Given a machine, a current state, and an event
    When transition applies the event
    Then it returns the next state on success
    And an unknown state yields a server fault, an unknown event a client fault, and a missing transition a client fault

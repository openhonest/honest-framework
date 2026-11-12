Feature: honest-type — generated, one scenario per function (39 total)

# ---- the pure core ----

  Scenario: predicate
    Given fn: Callable
    When predicate is called
    Then wraps a String to Boolean callable as an open-ended recognizer

  Scenario: insensitive
    Given members: list<str>
    When insensitive is called
    Then a case-insensitive Set recognizer: members and token are compared lowercased

  Scenario: recognize
    Given token: str and recognizer: Recognizer
    When recognize is called
    Then true when a token matches a recognizer, dispatched on the recognizer's kind; an unknown kind hits the terminal entry and returns a server fault naming the accepted kinds (spec 13.7)

  Scenario: _match_set
    Given token: str and recognizer: Recognizer
    When _match_set is called
    Then membership test for a Set recognizer: the token is one of the recognizer's members

  Scenario: _match_insensitive
    Given token: str and recognizer: Recognizer
    When _match_insensitive is called
    Then membership test for a case-insensitive Set recognizer: the lowercased token is one of the members

  Scenario: _match_predicate
    Given token: str and recognizer: Recognizer
    When _match_predicate is called
    Then runs the recognizer's String to Boolean callable; a throw becomes a predicate_error fault at classify, not here

  Scenario: vocabulary
    Given base_declarations: dict<str, any> and composed_types: list<ComposedType>
    When vocabulary is called
    Then builds a validated vocabulary, returning a fault on a reserved word, an overlap, a catch-all predicate, or an unknown composed base

  Scenario: merge
    Given vocab_a: Vocabulary and vocab_b: Vocabulary
    When merge is called
    Then combines two vocabularies into one, returning a fault on a name or value collision

  Scenario: composed
    Given name: str and requires: dict<str, str> and captures: str
    When composed is called
    Then a multi-token recognizer: it matches when its required base types are present and claims one base type's value

  Scenario: binding
    Given table: dict<str, str>
    When binding is called
    Then a binding table mapping type names to slot names

  Scenario: auto_binding
    Given vocab: Vocabulary
    When auto_binding is called
    Then the identity binding: every type name, base and composed, is its own slot

  Scenario: maybe
    Given slot: str
    When maybe is called
    Then marks a binding slot optional: an absent token becomes Nothing, not a rejection

  Scenario: _check_reserved
    Given base_types: dict<str, Recognizer>
    When _check_reserved is called
    Then the construction check that no Set member is a reserved word

  Scenario: _check_overlap
    Given base_types: dict<str, Recognizer>
    When _check_overlap is called
    Then the construction check that no token matches two types in one vocabulary

  Scenario: _check_catch_all
    Given base_types: dict<str, Recognizer>
    When _check_catch_all is called
    Then the construction check that rejects a predicate matching nearly every input, which is a test and not a type

  Scenario: _check_composed
    Given base_types: dict<str, Recognizer> and composed_list: list<ComposedType>
    When _check_composed is called
    Then the construction check that every composed type's required base types exist

  Scenario: _check_capture_ambiguity
    Given composed_list: list<ComposedType>
    When _check_capture_ambiguity is called
    Then the construction check that no two composed types would capture the same token

  Scenario: classify
    Given tokens: list<str> and vocab: Vocabulary and bind: Binding
    When classify is called
    Then classifies tokens against a vocabulary into a manifest, in two passes so token order never changes the result

  Scenario: _classify_token
    Given token: str and vocab: Vocabulary
    When _classify_token is called
    Then pass one: one token becomes a ticket, a rejection, or a fault when a predicate throws

  Scenario: _resolve_bindings
    Given tickets: list<Ticket> and rejections: list<Rejection> and vocab: Vocabulary and bind: Binding
    When _resolve_bindings is called
    Then pass two: resolve composed types, bind the remaining slots, fill Maybe slots with Nothing, and record missing required slots

  Scenario: link
    Given accepts: Vocabulary and binds: Binding and boundary: bool and authorizes: bool and emits: list<str>
    When link is called
    Then declares a link by attaching its vocabulary and role to a function for the checker; it never changes the function's behaviour

  Scenario: is_link
    Given fn: Callable
    When is_link is called
    Then true when a function was declared with link

  Scenario: link_meta
    Given fn: Callable
    When link_meta is called
    Then the metadata a declared link carries: its name, accepts, binds, boundary, authorizes and emits

  Scenario: chain
    Given links: list<Callable>
    When chain is called
    Then composes links into one short-circuiting link the host later runs, manifest to Result

  Scenario: validate_all
    Given links: list<Callable>
    When validate_all is called
    Then composes links into one accumulating link the host later runs: every link runs against the same manifest and any error makes the whole a validation_failed carrying every result

  Scenario: execute_chain
    Given links: list<Callable> and initial_manifest: Manifest
    When execute_chain is called
    Then runs links in sequence, short-circuiting on the first error

  Scenario: execute_chain_async
    Given links: list<Callable> and initial_manifest: Manifest
    When execute_chain_async is called
    Then runs links in sequence, awaiting each, short-circuiting on the first error

  Scenario: _run_validate_all
    Given links: list<Callable> and manifest: Manifest
    When _run_validate_all is called
    Then runs every link against the same manifest, accumulating every result

  Scenario: _run_validate_all_async
    Given links: list<Callable> and manifest: Manifest
    When _run_validate_all_async is called
    Then runs every link against the same manifest, awaiting each, accumulating every result

  Scenario: catch_at_boundary
    Given handler: Callable and fault_to_output: dict<str, any> and success_output: Callable and server_default: Callable and client_default: Callable
    When catch_at_boundary is called
    Then wraps a handler the host later runs so a fault renders through the output table and an uncaught exception becomes a server default

  Scenario: check_rejections
    Given manifest: Manifest and policy: dict<str, str>
    When check_rejections is called
    Then turns a manifest's rejections into a Result before the chain runs, deciding by a policy table

  Scenario: state_machine
    Given states: Vocabulary and events: Vocabulary and transitions: dict<str, str> and initial: str and terminal: list<str>
    When state_machine is called
    Then builds an immutable state machine, returning a fault on an unknown state, event, or transition target

  Scenario: transition
    Given machine: StateMachine and current_state: str and event: str
    When transition is called
    Then applies one event to a state and returns the next state or a fault; the machine stays stateless and the caller stores the result

  Scenario: is_reserved
    Given token: str
    When is_reserved is called
    Then true when a token is a framework, cross-language, or language reserved word

  Scenario: ticket
    Given type_name: str and value: str
    When ticket is called
    Then the result of classifying one token: its matched type name and original value

  Scenario: rejection
    Given token: str and reason: Reason and detail: str
    When rejection is called
    Then a token that could not be classified or bound, carried as data

  Scenario: fault
    Given code: str and message: str and category: Category and results: list<Result> and detail: dict<str, any>
    When fault is called
    Then a processing error carried as data; every field is passed explicitly, results empty unless a validate_all fault and detail empty unless there is structured context, so nothing is defaulted (spec 13.2)

  Scenario: ok
    Given manifest: Manifest
    When ok is called
    Then a successful Result wrapping a manifest

  Scenario: err
    Given fault_data: Fault
    When err is called
    Then a failed Result wrapping a fault

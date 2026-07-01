Feature: honest-check — Python supplement
  Scenarios that can only be stated in host-language terms: the tree-sitter node mechanics
  that read declarations out of source, the Python-specific watch lists and AST helpers, and
  the boundary plumbing (command line, language server, configuration and startup file reads).
  Counted toward the module's function points alongside the neutral scenarios in
  specs/features/honest-check.feature.

  # declgraph.py — reading honest-type declarations out of the syntax tree

  Scenario: resolve_aliases records how honest_type was imported
    Given a syntax tree and its source
    When resolve_aliases scans the imports
    Then it returns the local names bound to each honest-type constructor
    And the module names under which honest_type itself was imported

  Scenario: constructor_calls finds every call to a named honest-type constructor
    Given a syntax tree, the resolved aliases, and a canonical constructor name
    When constructor_calls scans the tree
    Then it returns each call node invoking that constructor, by bare name or by module attribute

  Scenario: assigned_name returns the variable a constructor call is assigned to
    Given a call node
    When assigned_name reads its parent assignment
    Then it returns the assigned variable name, or nothing when the call is not assigned

  Scenario: string_value returns the text inside a string literal node
    Given a node
    When string_value reads it
    Then it returns the text inside a string literal, or nothing when the node is not a string

  Scenario: _recognizer tags a vocabulary value node by kind
    Given a vocabulary value node
    When _recognizer inspects it
    Then it tags a set-literal as a bounded set of members
    And a bare name as a reference, and anything else as an open-ended predicate

  Scenario: _dictionary_arg finds the base-types dictionary of a vocabulary call
    Given a vocabulary call node
    When _dictionary_arg scans its arguments
    Then it returns the dictionary literal argument, or nothing when there is none

  Scenario: vocabulary_base_types reads a vocabulary call into type-to-recognizer pairs
    Given a vocabulary call node and its source
    When vocabulary_base_types reads it
    Then it returns each declared type name mapped to its tagged recognizer

  Scenario: _parse_composed reads a composed-type call into its record
    Given a composed-type call node
    When _parse_composed reads it
    Then it returns the composed type's name, its required base types, its captured type, and its location

  Scenario: extract_composed_types reads the composed types listed in a vocabulary call
    Given a vocabulary call node and the resolved aliases
    When extract_composed_types scans its composed-types list
    Then it returns one record per composed-type call found there

  Scenario: extract_bindings reads each binding call into its slot table
    Given a syntax tree and the resolved aliases
    When extract_bindings scans it
    Then it returns each binding variable mapped to its type-to-slot table and location

  Scenario: extract_vocabularies reads each vocabulary assignment into its parts
    Given a syntax tree and the resolved aliases
    When extract_vocabularies scans it
    Then it returns each vocabulary variable mapped to its base types, composed records, and location

  Scenario: vocab_binding_pairings pairs each vocabulary with the binding it is used with
    Given a syntax tree and the resolved aliases
    When vocab_binding_pairings scans link decorators and classify calls
    Then it returns each vocabulary variable paired with its binding variable

  Scenario: _calls_by_name finds every call to a bare-name callee
    Given a syntax tree and a callee name
    When _calls_by_name scans the tree
    Then it returns every call node whose callee is that bare name

  Scenario: authorizing_links finds functions that declare they authorize
    Given a syntax tree and the resolved aliases
    When authorizing_links scans the link decorators
    Then it returns each function declared to authorize, with its node

  Scenario: is_provider_registered reports whether an AuthProvider is registered
    Given a syntax tree
    When is_provider_registered scans for a register_auth_provider call
    Then it returns true when a provider is registered and false otherwise

  Scenario: positional_arg_count counts a call's positional arguments
    Given a call node
    When positional_arg_count counts its arguments
    Then it returns the number of positional arguments, ignoring keywords and comments

  Scenario: call_location reports a constructor call's position
    Given a call node
    When call_location reads it
    Then it returns the call's line and column, counted from one

  Scenario: module_assignments finds the top-level assignment statements
    Given the root of a syntax tree
    When module_assignments scans its top level
    Then it returns each assignment that is a top-level statement of the module

  Scenario: vocab_expr_type_names resolves a vocabulary expression to its type names
    Given a vocabulary expression node and the known vocabulary definitions
    When vocab_expr_type_names resolves it
    Then it returns the set of type names, following a name reference, an inline call, or a merge

  Scenario: build_vocabulary_definitions maps each vocabulary variable to its type names
    Given a syntax tree and the resolved aliases
    When build_vocabulary_definitions scans the module assignments
    Then it returns each module-level vocabulary variable mapped to its set of type names

  Scenario: link_decorator_call finds the link decorator on a function
    Given a function node and the resolved aliases
    When link_decorator_call inspects its decorators
    Then it returns the link decorator call node, or nothing when the function has none

  Scenario: function_name returns the name of a function node
    Given a function node
    When function_name reads it
    Then it returns the declared name, or an anonymous placeholder when there is none

  Scenario: function_role returns the declared role of a function
    Given a function node
    When function_role reads its decorators
    Then it returns the recognized role decorator, or nothing when none is declared

  Scenario: function_calls collects the bare-name calls inside a function body
    Given a function node
    When function_calls walks its body
    Then it returns the names of the functions it calls by bare name

  Scenario: functions_by_name maps each function name to its node
    Given a syntax tree
    When functions_by_name scans it
    Then it returns each function name mapped to its definition node

  Scenario: defined_function_names collects every function name in the module
    Given a syntax tree
    When defined_function_names scans it
    Then it returns the name of every function defined in the module

  Scenario: extract_links reads each link decorator into its declared contract
    Given a syntax tree, the resolved aliases, and the vocabulary definitions
    When extract_links scans the link decorators
    Then it returns each link mapped to the types it accepts, the types it emits, whether it is a boundary, and its location

  Scenario: extract_chains reads each chain call into its ordered links
    Given a syntax tree and the resolved aliases
    When extract_chains scans the chain calls
    Then it returns each chain's name, its ordered link names, and its location

  Scenario: keyword_args reads a call's keyword arguments
    Given a call node
    When keyword_args reads its arguments
    Then it returns each keyword name mapped to its value node

  Scenario: vocabulary_members collects the set members across a vocabulary's base types
    Given a vocabulary call node
    When vocabulary_members reads its base types
    Then it returns the union of all set-recognizer members declared in it

  Scenario: string_list reads the string values of a list or tuple literal
    Given a node
    When string_list reads it
    Then it returns the string values of a list or tuple literal, or empty for anything else

  Scenario: transition_table reads a transitions literal into ordered triples
    Given a dictionary node of transitions
    When transition_table reads it
    Then it returns each state, event, and resulting state as a triple

  Scenario: extract_state_machines reads each state-machine call into its declared parts
    Given a syntax tree and the resolved aliases
    When extract_state_machines scans the state-machine calls
    Then it returns each machine's states, events, initial state, terminal states, transitions, and location

  # rules.py — Python and tree-sitter helpers behind the rules

  Scenario: _simple_base_name reduces a base expression to its bare name
    Given the text of a base expression
    When _simple_base_name reduces it
    Then it returns the bare trailing name, stripped of module qualifier and subscript

  Scenario: _class_base_names collects a class's explicit bases
    Given a class node
    When _class_base_names reads its superclasses
    Then it returns the names of the explicit bases, ignoring keyword arguments

  Scenario: _equality_target returns the identifier an equality condition tests
    Given a condition node
    When _equality_target inspects it
    Then it returns the tested identifier when the condition compares a name for equality, otherwise nothing

  Scenario: _if_chain_conditions collects the conditions of an if-chain
    Given an if-statement node
    When _if_chain_conditions reads it
    Then it returns the condition guarding the if branch and each following branch

  Scenario: _call_name returns the callee name of a call
    Given a call node
    When _call_name reads its callee
    Then it returns the bare name for a plain call and the attribute name for a method call

  Scenario: _class_methods collects the methods directly in a class body
    Given a class node
    When _class_methods reads its body
    Then it returns the function definitions declared directly in the class body

  Scenario: _self_attr_writes collects attributes assigned on self in a method
    Given a method node
    When _self_attr_writes walks its body
    Then it returns the attribute names assigned on the instance

  Scenario: _direct_nonlocal_names collects the names declared nonlocal in a body
    Given a function node
    When _direct_nonlocal_names reads its body
    Then it returns the names declared nonlocal at the top of the body

  Scenario: _rebinds_name reports whether a function rebinds a name
    Given a function node and a name
    When _rebinds_name walks the function
    Then it reports true when the name is the direct target of an assignment

  Scenario: _dotted_name returns the dotted path of a name expression
    Given a node
    When _dotted_name reads it
    Then it returns the dotted path for a name or attribute expression, otherwise empty

  Scenario: _qualified_call_name returns the dotted callee of a call
    Given a call node
    When _qualified_call_name reads its callee
    Then it returns the dotted callee path, or empty when the callee is not a name path

  Scenario: _decorators collects the decorators attached to a function
    Given a function node
    When _decorators reads its parent
    Then it returns the decorator nodes attached to the function

  Scenario: _is_boundary_function reports whether a function is a boundary
    Given a function node
    When _is_boundary_function reads its decorators
    Then it reports true when it is decorated as a boundary or as a boundary link

  Scenario: _enclosing_function returns the nearest enclosing function
    Given a node
    When _enclosing_function climbs its parents
    Then it returns the nearest enclosing function, or nothing at module level

  Scenario: _subscript_base returns the base name of a subscript target
    Given a node
    When _subscript_base reads it
    Then it returns the base name when the target is a subscript on a plain name, otherwise nothing

  Scenario: _mutable_module_containers finds module-level containers that are mutated
    Given a syntax tree
    When _mutable_module_containers scans the module
    Then it returns the names of module-level containers that are written to or reassigned
    But a container that is only ever read is treated as a constant lookup table and excluded

  Scenario: _local_names collects the names bound locally in a function
    Given a function node
    When _local_names reads its parameters and body
    Then it returns the parameter names and the assignment and loop targets

  Scenario: _is_value_load reports whether an identifier is read as a value
    Given an identifier node
    When _is_value_load reads its parent
    Then it reports true when the identifier is read as a value, false when it is only a name label

  Scenario: _check_global_reads flags reads of mutable module state in non-boundary functions
    Given a syntax tree and the set of mutable module-level containers
    When _check_global_reads scans the non-boundary functions
    Then it flags each first read of a mutable module-level container as HC-P004

  Scenario: _decorator_name returns the bare name of a decorator
    Given a decorator node
    When _decorator_name reads it
    Then it returns the bare trailing name of the decorator

  Scenario: _is_profiled_comment reports whether a comment is a profiling annotation
    Given a node
    When _is_profiled_comment reads it
    Then it reports true when the node is a comment carrying the profiling directive

  Scenario: _has_profiling_evidence reports whether a function carries profiling evidence
    Given a function node
    When _has_profiling_evidence inspects it
    Then it reports true when the function has a profiled decorator or an adjacent profiling comment

  Scenario: _reachable_states collects the states reachable from an initial state
    Given an initial state and a list of transitions
    When _reachable_states searches outward
    Then it returns every state reachable by following transitions

  Scenario: _has_except_clause reports whether a try statement catches
    Given a try-statement node
    When _has_except_clause reads it
    Then it reports true when the statement has an except clause, false for cleanup-only

  Scenario: _produced_slot_keys collects the slot keys a link body writes
    Given a link function node
    When _produced_slot_keys walks its body
    Then it returns the slot keys written by subscript assignment or as dictionary keys

  Scenario: _recognizer_identity returns a comparable identity for a recognizer
    Given a recognizer
    When _recognizer_identity inspects it
    Then it returns a comparable identity for a set or reference recognizer
    But nothing for an open-ended predicate, which is treated as unique

  Scenario: _orchestrator_call_sequence reads an orchestrator body to its ordered calls
    Given an orchestrator function node
    When _orchestrator_call_sequence walks its body
    Then it returns the ordered sequence of qualified call names it makes

  Scenario: _longest_common_run measures the longest shared run of two sequences
    Given two sequences of call names
    When _longest_common_run compares them
    Then it returns the length of their longest contiguous shared sublist

  Scenario: _risky_predicate_ops collects operations in a recognizer body that can throw
    Given a recognizer value node
    When _risky_predicate_ops walks it
    Then it returns the operations that can throw on non-matching input, such as numeric conversion, indexing, or division

  # formats.py — host-language escaping

  Scenario: _xml_escape escapes the characters reserved in XML
    Given a piece of text
    When _xml_escape escapes it
    Then it replaces the ampersand, angle brackets, and double quote with their XML entities

  # watchlists.py — the Python impurity watch lists

  Scenario: matches_watchlist matches a qualified call name against a watch list
    Given a qualified call name and a watch list
    When matches_watchlist checks it
    Then it matches an exact entry, a dotted-wildcard prefix, or a bare-wildcard prefix

  # suppression.py — reading honest directives from comments

  Scenario: _parse_directive parses an honest directive comment
    Given the text of a comment
    When _parse_directive reads it
    Then it returns the verb and the named rules for a well-formed honest directive, otherwise nothing

  Scenario: _collect_directives collects every honest directive in source order
    Given a syntax tree and its source
    When _collect_directives walks the comments
    Then it returns each directive's line, verb, and rules, in source order

  Scenario: build_suppressions computes the inline and block suppressions
    Given a syntax tree, its source, and the last line number
    When build_suppressions reads the directives
    Then it returns the per-line inline ignores and the per-rule disable ranges
    And a disable that is never re-enabled runs to the end of the file

  # cli.py — the command-line boundary

  Scenario: _discover_files expands paths into the source files to check
    Given paths to check and exclusion patterns
    When _discover_files expands them
    Then it returns the sorted source files, dropping any that match an exclusion

  Scenario: _find_config locates the configuration file to use
    Given an optional explicit configuration path
    When _find_config looks for one
    Then it returns the explicit path when given, otherwise the nearest ancestor's configuration, otherwise nothing

  Scenario: _load_config reads and normalizes the configuration file
    Given a configuration path
    When _load_config reads it
    Then it returns the normalized configuration, or the defaults when the file is absent

  Scenario: _parse_args parses the command-line arguments
    Given the command-line argument list
    When _parse_args parses it
    Then it returns the parsed paths, format, severity, rule selections, and mode flags

  Scenario: main runs the check over the paths and returns the exit code
    Given the command-line arguments
    When main runs the check
    Then it discovers, checks, filters, and renders the violations
    And returns zero when nothing blocks, one when an error is found, and two on a usage or read failure
    But with --fix it reports that nothing is auto-fixable, and with --watch it re-runs on each trigger

  Scenario: _run_once checks the paths once and returns the exit code
    Given the resolved paths, severity, suppressed and selected rules, and format
    When _run_once runs the check once
    Then it discovers, checks, filters, and renders, returning one on errors, two on a read failure, else zero

  Scenario: watch re-runs the check on each trigger from the stream
    Given a run thunk and a trigger stream
    When watch reads the stream
    Then it runs the check once and again for each trigger line, returning the last exit code at end of stream

  Scenario: is_fixable reports whether a rule has a conservative automatic fix
    Given a rule identifier
    When is_fixable checks it
    Then it is true only for a rule with a provably-safe fix, of which honest-check's structural rules have none

  # startup.py — the startup integration boundary

  Scenario: _format_report formats startup findings into a report
    Given a list of startup findings
    When _format_report formats them
    Then it returns one line per finding with its location, severity, rule, and message

  Scenario: _on_warn prints a report to standard error
    Given a formatted report
    When _on_warn handles it
    Then it prints the report to standard error and lets the boot continue

  Scenario: _on_raise raises an error carrying the report
    Given a formatted report
    When _on_raise handles it
    Then it raises a startup error carrying the report

  Scenario: _on_halt prints the report and halts the boot
    Given a formatted report
    When _on_halt handles it
    Then it prints the report to standard error and exits the process with a failing code

  Scenario: _collect runs the startup-eligible rules over the paths
    Given paths to check and a severity to keep
    When _collect reads each source file and checks it
    Then it returns the findings from the startup-eligible rules at that severity

  # lsp.py — the language-server boundary

  Scenario: to_lsp_diagnostic converts a violation into a language-server diagnostic
    Given a one-based violation
    When to_lsp_diagnostic converts it
    Then it returns a zero-based language-server diagnostic with the mapped severity, rule code, and message

  Scenario: _publish builds a diagnostics notification for a document
    Given a document's URI and its current text
    When _publish checks the text
    Then it returns a publish-diagnostics notification carrying the document's violations

  Scenario: _response builds a result response for a request
    Given a message id and a result
    When _response wraps them
    Then it returns a protocol response carrying that id and result

  Scenario: _on_initialize answers the initialize request with the server's capabilities
    Given an initialize request
    When _on_initialize handles it
    Then it returns a response advertising full-document sync and the server's identity

  Scenario: _on_did_open publishes diagnostics for a newly opened document
    Given a document-opened notification and the document store
    When _on_did_open handles it
    Then it records the opened document's text in the store and returns a publish-diagnostics notification for it

  Scenario: _hover_contents builds the hover documentation at a position
    Given a document's text, its uri, and a position
    When _hover_contents reads it
    Then it returns the rule and message of a diagnostic on that line as markdown, or nothing when the line is unflagged

  Scenario: _on_hover answers a hover request from the document store
    Given a hover request and the document store
    When _on_hover handles it
    Then it returns the hover documentation for the position from the stored text, or a null result when nothing is flagged there

  Scenario: _node_at finds the identifier at a position
    Given a parse tree and a zero-based line and column
    When _node_at searches it
    Then it returns the identifier node whose span covers the position, or nothing when the position is not on an identifier

  Scenario: _definition_of finds where a name is defined
    Given a parse tree, the source, and a name
    When _definition_of searches it
    Then it returns the assignment target or function definition that binds the name, or nothing when the name is undefined

  Scenario: _definition_location resolves the definition at a position
    Given a document's text, its uri, and a position
    When _definition_location resolves it
    Then it returns the location where the identifier at that position is defined, or nothing when the position is not an identifier or has no definition

  Scenario: _on_definition answers a go-to-definition request from the store
    Given a definition request and the document store
    When _on_definition handles it
    Then it returns the definition location for the position from the stored text, or a null result

  Scenario: _document_symbols lists a document's declarations as symbols
    Given a document's text and its uri
    When _document_symbols scans it
    Then it returns a symbol for each top-level assignment whose value constructs a vocabulary, binding, or chain, with its kind and location

  Scenario: _on_workspace_symbol answers a workspace symbol query
    Given a workspace symbol request and the document store
    When _on_workspace_symbol handles it
    Then it returns the declarations across every open document whose name contains the query substring

  Scenario: _code_actions offers a suppression directive for diagnostics in a range
    Given a document's text, its uri, and an LSP range
    When _code_actions builds the actions
    Then it returns a quick-fix for each diagnostic on a line in the range, whose edit appends an ignore directive to that line

  Scenario: _on_code_action answers a code-action request from the store
    Given a code-action request and the document store
    When _on_code_action handles it
    Then it returns the suppression quick-fixes for the requested range from the stored text

  Scenario: _on_did_change publishes diagnostics for the changed document
    Given a document-changed notification carrying the full new text
    When _on_did_change handles it
    Then it returns a publish-diagnostics notification for the latest text

  Scenario: _on_did_close clears the diagnostics for a closed document
    Given a document-closed notification
    When _on_did_close handles it
    Then it returns a publish-diagnostics notification with an empty list for that document

  Scenario: _on_shutdown answers the shutdown request
    Given a shutdown request
    When _on_shutdown handles it
    Then it returns an empty result response

  Scenario: _noop answers a request that needs no reply
    Given a request that needs no reply
    When _noop handles it
    Then it returns no outgoing messages

  Scenario: dispatch routes a request to its handler
    Given the document store, a method name, a message id, and parameters
    When dispatch routes them
    Then it calls the matching handler (or the no-op handler for an unknown method) and returns the updated store and its outgoing messages

  Scenario: _read_message reads one framed message from a stream
    Given a binary input stream
    When _read_message reads it
    Then it returns the decoded message, or nothing at end of input

  Scenario: _write_message writes one framed message to a stream
    Given a binary output stream and a message
    When _write_message writes it
    Then it writes the message framed with its content-length header and flushes the stream

  Scenario: serve runs the stdio request loop until exit
    Given an input stream and an output stream
    When serve runs the loop
    Then it reads each request, dispatches it, and writes the replies until exit or end of input

  Scenario: feature_vocabulary reads the module's FEATURES flag vocabulary
    Given a source with a module-scope FEATURES dict literal
    When feature_vocabulary reads it
    Then it returns each flag mapped to its declared set of states

  Scenario: _states_of reads the states of one FEATURES entry
    Given a flag specification dict
    When _states_of reads its states pair
    Then it returns the string members of the states set or list, or an empty set

  Scenario: _feature_state_flag reads the flag argument of a feature_state call
    Given a syntax node
    When _feature_state_flag inspects it
    Then it returns the second positional string argument of a feature_state call, else nothing

  Scenario: feature_state_calls finds every feature_state call site
    Given a parsed source
    When feature_state_calls walks it
    Then it returns each feature_state call's flag and node where the flag is a string literal

  Scenario: handler_table_dispatches finds every handler-table dispatch on a flag
    Given a parsed source
    When handler_table_dispatches walks it
    Then it returns each handler-table dispatch's table name, flag, and node

  Scenario: module_dict_keys reads the keys of a module-scope dict literal
    Given a name and a parsed source
    When module_dict_keys looks the name up
    Then it returns the string keys of that module-scope dict literal, or nothing

  Scenario: check_hc_hf001 flags a feature_state call on an undeclared flag
    Given a source that calls feature_state with a flag not in FEATURES
    When check_hc_hf001 runs
    Then it reports HC-HF001 at the call site

  Scenario: check_hc_hf002 flags a handler table missing a declared state
    Given a handler table keyed on a flag that omits one of its states
    When check_hc_hf002 runs
    Then it reports HC-HF002 naming the missing states

  Scenario: language_for_path picks the grammar a file is checked under
    Given a file path
    When language_for_path reads its extension
    Then it returns JavaScript for .js, .mjs, and .cjs, and Python otherwise

  Scenario: check_hc_p003_js flags a JavaScript class that is not an Error subclass
    Given JavaScript source with a class declaration
    When check_hc_p003_js runs
    Then it reports HC-P003 unless the class extends Error

  Scenario: _is_class_node recognizes a JavaScript class definition
    Given a JavaScript syntax node
    When _is_class_node inspects it
    Then it is true for a class declaration or a class expression, not the class keyword token

  Scenario: _class_name reads the name of a JavaScript class
    Given a JavaScript class node
    When _class_name reads it
    Then it returns the declared name, or anonymous for a class expression

  Scenario: _class_base reads the superclass of a JavaScript class
    Given a JavaScript class node
    When _class_base reads its heritage
    Then it returns the extended superclass name, or nothing when there is no heritage

  Scenario: _js_call_name reads the callee name of a JavaScript call
    Given a JavaScript call node
    When _js_call_name reads its callee
    Then it returns the identifier for a plain call or the property for a member call

  Scenario: check_hc_p011_js flags a JavaScript lifecycle hook
    Given JavaScript source that calls a lifecycle hook
    When check_hc_p011_js runs
    Then it reports HC-P011 naming the hook

  Scenario: _js_cache_construct recognizes a cache construct
    Given a JavaScript syntax node
    When _js_cache_construct inspects it
    Then it returns the name of a WeakMap constructor or a memoize call, else nothing

  Scenario: check_hc_p006_js flags a JavaScript cache without profiling evidence
    Given JavaScript source that constructs a WeakMap or calls memoize
    When check_hc_p006_js runs
    Then it reports HC-P006

  Scenario: _js_type_check recognizes a typeof or instanceof check
    Given a JavaScript syntax node
    When _js_type_check inspects it
    Then it returns typeof for a typeof unary, instanceof for an instanceof binary, else nothing

  Scenario: check_hc_p005_js flags a JavaScript type check in business logic
    Given JavaScript source with a typeof or instanceof check
    When check_hc_p005_js runs
    Then it reports HC-P005

  Scenario: _js_equality_target reads the discriminant of an equality condition
    Given a JavaScript if condition
    When _js_equality_target reads it
    Then it returns the identifier compared to a value, or nothing when it is not that shape

  Scenario: _js_else_if follows an else-if chain
    Given a JavaScript if node
    When _js_else_if reads its alternative
    Then it returns the nested if of an else-if, or nothing for a plain else or no else

  Scenario: _js_if_chain_conditions collects every condition in an if chain
    Given the head of a JavaScript if chain
    When _js_if_chain_conditions walks it
    Then it returns the condition of the if and of each else-if

  Scenario: check_hc_p001_js flags a JavaScript dispatch chain
    Given JavaScript source with an if/else-if chain on one value
    When check_hc_p001_js runs
    Then it reports HC-P001 when three or more branches compare the same identifier to constants

  Scenario: _js_scope_nodes visits a function's own scope
    Given a JavaScript node
    When _js_scope_nodes walks it
    Then it yields the node and its descendants without descending into nested functions

  Scenario: _js_mutable_decl_names reads the names a let or var declaration binds
    Given a JavaScript declaration node
    When _js_mutable_decl_names reads it
    Then it returns the bound identifier names, or nothing for a const declaration

  Scenario: _js_param_names reads a function's parameter names
    Given a JavaScript function node
    When _js_param_names reads it
    Then it returns the identifier parameter names, single or listed

  Scenario: _js_scope_lets reads the let and var names of a function's own scope
    Given a JavaScript function node
    When _js_scope_lets reads it
    Then it returns the let and var names declared directly in that function

  Scenario: _js_reassigned_names reads the names reassigned in a function's own scope
    Given a JavaScript function node
    When _js_reassigned_names reads it
    Then it returns the identifier names reassigned by assignment or update, not nested functions

  Scenario: check_hc_p016_js flags a closure that mutates an enclosing binding
    Given a nested JavaScript function reassigning an outer let or var
    When check_hc_p016_js runs
    Then it reports HC-P016 unless the name is shadowed by a parameter or local declaration

  Scenario: _js_qualified_name reads the dotted name of a callee
    Given a JavaScript callee node
    When _js_qualified_name reads it
    Then it returns the identifier or dotted member path, or nothing for a computed callee

  Scenario: _js_impure_name reads the watched name of an impure node
    Given a JavaScript call or new expression
    When _js_impure_name inspects it
    Then it returns the watched name of a matching I/O or non-deterministic construct, else nothing

  Scenario: _js_enclosing_function finds the nearest enclosing function
    Given a JavaScript node
    When _js_enclosing_function walks its parents
    Then it returns the nearest enclosing function, or nothing at module level

  Scenario: _js_boundary_lines finds the honest boundary comment lines
    Given a parsed JavaScript source
    When _js_boundary_lines scans its comments
    Then it returns the line numbers carrying a honest boundary directive

  Scenario: _js_is_boundary decides whether a function is a boundary
    Given a JavaScript function and the boundary comment lines
    When _js_is_boundary checks it
    Then it is true when a boundary comment sits on the function's line or the line above it

  Scenario: check_hc_p004_js flags I/O in a non-boundary function
    Given JavaScript source with an I/O or non-deterministic call in a non-boundary function
    When check_hc_p004_js runs
    Then it reports HC-P004 unless the function is marked a boundary

  Scenario: check_hc_p002_js flags a caught exception in a non-boundary function
    Given JavaScript source with a try/catch in a non-boundary function
    When check_hc_p002_js runs
    Then it reports HC-P002 unless the function is marked a boundary

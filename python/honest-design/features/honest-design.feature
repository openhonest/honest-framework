Feature: honest-design — the .hd architecture-declaration read path
  The reader folds .hd source into the language-agnostic IR, emitting faults as data in the shared
  Result shape. It depends only on honest-parse and sits below honest-type in the build order.

  Scenario: fault constructs a fault record as data
    Given code, message, category, and detail
    When fault assembles them
    Then it returns a fault record carrying those four fields, never raised

  Scenario: ok wraps a value in a successful Result
    Given a value the reader produced
    When ok wraps it
    Then it returns a Result carrying that value under "ok"

  Scenario: err wraps a fault in a failed Result
    Given a fault produced during reading
    When err wraps it
    Then it returns a Result carrying that fault under "err"

  Scenario: _field returns a node's child by field name
    Given a parse node and a field name
    When _field looks it up
    Then it returns that named child node, or nothing

  Scenario: _text returns a node's source text
    Given a parse node and the source
    When _text reads it
    Then it returns the source slice the node spans

  Scenario: _field_text returns the text of a node's named field
    Given a parse node, a field name, and the source
    When _field_text reads the field
    Then it returns the source text of that field

  Scenario: _children returns a node's children of a given type
    Given a parse node and a node type
    When _children filters
    Then it returns the children of exactly that type, in order

  Scenario: _unquote strips a string token's surrounding quotes
    Given a quoted string token
    When _unquote strips it
    Then it returns the text without the surrounding quotes

  Scenario: _read_atom folds a type atom with its generic arguments
    Given a type_atom node
    When _read_atom folds it
    Then it returns the atom name and its generic argument types

  Scenario: _read_type folds a type as a union of atoms
    Given a type node
    When _read_type folds it
    Then it returns the list of atoms making up the union

  Scenario: _read_field folds a record field
    Given a record field node
    When _read_field folds it
    Then it returns the field name and its type

  Scenario: _read_type_decl folds a type declaration as a record or an alias
    Given a type_decl node
    When _read_type_decl folds it
    Then it returns the name with either a record of fields or an alias type

  Scenario: _read_member folds a set member with its optional description
    Given a set_member node
    When _read_member folds it
    Then it returns the member value and its description, or an empty description

  Scenario: _read_set folds a set declaration
    Given a set_decl node
    When _read_set folds it
    Then it returns the set name and its members

  Scenario: _read_vocab folds a vocabulary declaration
    Given a vocabulary_decl node
    When _read_vocab folds it
    Then it returns the vocabulary name and the sets it composes

  Scenario: _read_dispatch_entry folds a dispatch entry
    Given a dispatch_entry node
    When _read_dispatch_entry folds it
    Then it returns the entry key and its handler

  Scenario: _read_dispatch folds a dispatch table
    Given a dispatch_decl node
    When _read_dispatch folds it
    Then it returns the dispatch name and its entries

  Scenario: _read_example folds an example declaration
    Given an example_decl node
    When _read_example folds it
    Then it returns the example name, its chain, and its text

  Scenario: _read_param folds a function parameter
    Given a param node
    When _read_param folds it
    Then it returns the parameter name and its type

  Scenario: _read_side_effect folds a side_effect annotation
    Given a side_effect node
    When _read_side_effect folds it
    Then it returns the direction and the target

  Scenario: _read_function folds a function declaration and derives its column
    Given a function_decl node
    When _read_function folds it
    Then it returns the name, role, derived column, params, return type, side_effects, invokes, and raises

  Scenario: _read_chain folds a chain declaration
    Given a chain_decl node
    When _read_chain folds it
    Then it returns the chain name and its ordered links

  Scenario: _read_route folds a route declaration
    Given a route_decl node
    When _read_route folds it
    Then it returns the method, path, and target

  Scenario: _read_entry folds an entry-point declaration
    Given an entry_decl node
    When _read_entry folds it
    Then it returns the call-site string and the target

  Scenario: _read_html_attr folds an html_attr declaration
    Given an html_attr_decl node
    When _read_html_attr folds it
    Then it returns the attribute and its description

  Scenario: _read_layer folds a layer declaration
    Given a layer_decl node
    When _read_layer folds it
    Then it returns the layer name

  Scenario: _read_module folds a module and its body declarations
    Given a module_decl node
    When _read_module folds it
    Then it returns the module name, layer, and every grouped declaration collection

  Scenario: _read_rule folds a workspace rule
    Given a rule_decl node
    When _read_rule folds it
    Then it returns the rule id, its module (or empty for a global rule), and its statement

  Scenario: _read_actor folds a workspace actor
    Given an actor_decl node
    When _read_actor folds it
    Then it returns the actor name

  Scenario: _read_flow folds a workspace flow
    Given a flow_decl node
    When _read_flow folds it
    Then it returns the flow name, its group, and its steps

  Scenario: _document assembles the Document from grouped declarations
    Given the grouped top-level declarations
    When _document assembles them
    Then it returns the Document with modules, rules, actors, and flows

  Scenario: read_hd reads .hd source into the Document IR
    Given .hd architecture-declaration source text
    When read_hd reads it
    Then it returns a Result carrying the Document IR, or a client fault if the source is malformed

  Scenario: _declared_functions collects a module's declared function names
    Given a module IR
    When _declared_functions gathers them
    Then it returns the set of names of every function the module declares

  Scenario: _unknown_links flags chain links naming no declared function
    Given a module IR whose chains reference functions
    When _unknown_links checks them
    Then it returns an unknown_link fault for each link that names no declared function

  Scenario: _unknown_targets flags routes and entries targeting no declared function
    Given a module IR with routes and entries
    When _unknown_targets checks them
    Then it returns an unknown_target fault for each route or entry whose target is not declared

  Scenario: _duplicate_names flags a name declared twice within a kind
    Given a module IR with declarations
    When _duplicate_names checks each kind
    Then it returns a duplicate_name fault for any name that appears more than once in a kind

  Scenario: _impure_pure_functions flags a pure function that declares a side effect
    Given a module IR with functions
    When _impure_pure_functions checks them
    Then it returns an impure_pure_function fault for each pure fn that declares a side effect

  Scenario: validate returns a module's faults
    Given a module IR
    When validate runs every check over it
    Then it returns the combined list of faults, empty when the module is valid

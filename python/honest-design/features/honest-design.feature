Feature: honest-design — reading, checking, drawing and tracing .hd itself
  One scenario per function. Four doors face the world: read_hd folds source into the IR, validate
  checks a module, render draws it, reach traces what each door touches. One reader asks honest-parse
  for the tree. Four orchestrators carry the four paths. The rest is the pure core: the fold, the
  checks and their shared helpers, the renderer, the reach walk, and the Result constructors.

  # --- the four doors and the one reader ------------------------------------

  Scenario: read_hd reads .hd source text into a Document
    Given .hd source text from another module
    When read_hd receives it
    Then it returns a Document holding the modules, rules, actors and flows the source declares
    But a source that is not text is refused by name, and a malformed source comes back as a fault naming the line and column

  Scenario: validate checks one module's IR and returns the faults
    Given one module's IR
    When validate runs every check over it
    Then it returns the list of faults, empty when the module is sound
    But a document handed where a single module belongs is refused by name

  Scenario: render draws one module's IR as the four-column diagram
    Given one module's IR
    When render lays it out
    Then it returns a Diagram of four columns and the chain edges between them

  Scenario: reach reports what each door's path touches
    Given one module's IR and the declarations of the modules it reaches
    When reach walks each door's path
    Then it returns, per door, the world it reads directly, the world it reaches past a seam, and the seams it could not follow

  Scenario: parse asks honest-parse for the hd syntax tree
    Given .hd source as bytes
    When parse hands it to honest-parse
    Then it returns the syntax tree, located fault and all
    But this is the one place honest-parse is touched

  # --- the four orchestrators -----------------------------------------------

  Scenario: read_declaration folds the parsed tree's top level into a Document
    Given .hd source text
    When read_declaration asks for the tree and folds its top level
    Then it returns a Document, assembling each top-level declaration through its own reader
    But a non-text source and a malformed source each come back as a fault

  Scenario: check_module runs every check over one module and gathers the faults
    Given one module's IR
    When check_module runs each check in turn
    Then it returns every fault the checks found, in one list

  Scenario: draw_module builds the four columns and the chain edges
    Given one module's IR
    When draw_module places each function in its column and reads the chains
    Then it returns the four columns and the edges between chain links

  Scenario: trace_reach walks each door's path and reports what it touches
    Given one module's IR and the declarations it reaches
    When trace_reach walks from each door
    Then it returns the reach report for every door

  # --- the read fold --------------------------------------------------------

  Scenario: _document assembles the four top-level lists into a Document
    Given the folded modules, rules, actors and flows
    When _document gathers them
    Then it returns a Document carrying all four lists

  Scenario: _read_module folds one module node into a Module
    Given a module node and the source
    When _read_module reads each body declaration through its own reader
    Then it returns a Module carrying its layer, envs, stores, surface, types, functions, chains and the rest

  Scenario: _read_rule folds one rule node into a Rule
    Given a rule node and the source
    When _read_rule reads it
    Then it returns a Rule carrying the id, the module it names, and the statement

  Scenario: _read_actor folds one actor node into an Actor
    Given an actor node and the source
    When _read_actor reads it
    Then it returns an Actor carrying the name

  Scenario: _read_flow folds one flow node into a Flow
    Given a flow node and the source
    When _read_flow reads it
    Then it returns a Flow carrying the name, the group, and the steps in order

  Scenario: _read_layer reads a module's layer name
    Given a layer node and the source
    When _read_layer reads it
    Then it returns the layer name as declared

  Scenario: _read_env folds one env node into an Env
    Given an env node and the source
    When _read_env reads the name and its type
    Then it returns an Env carrying the variable name, its type, and any note

  Scenario: _read_store folds one store node into a Store
    Given a store node and the source
    When _read_store reads it
    Then it returns a Store carrying the pure function whose answers it holds and why it exists

  Scenario: _read_surface folds an inputs or outputs block into its members
    Given an inputs or outputs node and the source
    When _read_surface reads each member
    Then it returns the list of set members, each a side of the world with its description

  Scenario: _read_surfaces folds a surfaces node into a Surfaces
    Given a surfaces node and the source
    When _read_surfaces reads each member
    Then it returns a Surfaces carrying its members in the declared order

  Scenario: _read_surface_member folds one surface member into its id and element
    Given a surface member node and the source
    When _read_surface_member reads it
    Then it returns the id a rendered element must carry and the element it lives in

  Scenario: _read_type_decl folds one type node into a TypeDecl
    Given a type node and the source
    When _read_type_decl reads a record, an alias, or a foreign type
    Then it returns a TypeDecl carrying the fields, the aliased type, or the foreign source, and any note

  Scenario: _read_field folds one record field into a Field
    Given a field node and the source
    When _read_field reads the name and type
    Then it returns a Field carrying the name and its type expression

  Scenario: _read_type reads a type expression into a list of atoms
    Given a type node and the source
    When _read_type reads the union
    Then it returns the list of atoms the type mentions

  Scenario: _read_atom reads one atom, its name and generic arguments
    Given an atom node and the source
    When _read_atom reads the name and each argument
    Then it returns an Atom carrying the name and its argument types

  Scenario: _read_set folds one set node into a SetDecl
    Given a set node and the source
    When _read_set reads each member
    Then it returns a SetDecl carrying the members and any note

  Scenario: _read_member folds one set member into its value and description
    Given a set member node and the source
    When _read_member reads it
    Then it returns the value and its description, the description empty when none is written

  Scenario: _read_vocab folds one vocabulary node into a Vocabulary
    Given a vocabulary node and the source
    When _read_vocab reads the sets it names
    Then it returns a Vocabulary carrying those set names and any note

  Scenario: _read_dispatch folds one dispatch node into a Dispatch
    Given a dispatch node and the source
    When _read_dispatch reads each entry
    Then it returns a Dispatch carrying its entries and any note

  Scenario: _read_dispatch_entry folds one dispatch entry into key, handler and projection
    Given a dispatch entry node and the source
    When _read_dispatch_entry reads it
    Then it returns the key, the handler, and the slice of the input the handler is fed when one is declared

  Scenario: _read_example folds one example node into an Example
    Given an example node and the source
    When _read_example reads it
    Then it returns an Example carrying the name, the chain it names, and the text

  Scenario: _read_function folds one function node into a Function
    Given a function node and the source
    When _read_function reads the role, parameters, return, side effects, invokes, raises and awaited word
    Then it returns a Function carrying all of them and the column its role derives

  Scenario: _read_param folds one parameter into a Param
    Given a parameter node and the source
    When _read_param reads the name and type
    Then it returns a Param carrying the name and its type expression

  Scenario: _read_side_effect folds one side effect, splitting a dotted target
    Given a side effect node and the source
    When _read_side_effect reads the direction and target
    Then it returns a SideEffect, a colon naming a kind and a dot splitting the target into the module and the door it enters

  Scenario: _read_chain folds one chain node into a Chain
    Given a chain node and the source
    When _read_chain reads its links
    Then it returns a Chain carrying the links in order and any note

  Scenario: _read_route folds one route node into a Route
    Given a route node and the source
    When _read_route reads it
    Then it returns a Route carrying the method, path, target and label

  Scenario: _read_entry folds one entry node into an Entry
    Given an entry node and the source
    When _read_entry reads it
    Then it returns an Entry carrying the callsite and the target it starts

  Scenario: _read_html_attr folds one html_attr node into an HtmlAttr
    Given an html_attr node and the source
    When _read_html_attr reads it
    Then it returns an HtmlAttr carrying the attribute and its description

  Scenario: _note reads the one kept comment on a node
    Given a node and the source
    When _note looks for a note
    Then it returns the note text, or an empty string when the node has none

  # --- the checks -----------------------------------------------------------

  Scenario: _bad_surfaces faults an empty surfaces block or a repeated id
    Given a module's surfaces blocks
    When _bad_surfaces reads them
    Then it faults a block that declares no member and a block whose ids are not unique

  Scenario: _unknown_links faults a chain link naming an undeclared function
    Given a module's chains
    When _unknown_links checks each link against the declared functions
    Then it faults a link that names a function the module does not declare

  Scenario: _unknown_targets faults a route or entry naming an undeclared function
    Given a module's routes and entries
    When _unknown_targets checks each target against the declared functions
    Then it faults a target the module does not declare

  Scenario: _unknown_envs faults an environment read naming an undeclared variable
    Given a module's functions and env declarations
    When _unknown_envs checks each environment read
    Then it faults a read that names no declared env

  Scenario: _unknown_layer faults a layer that is not one of the known set
    Given a module's layer
    When _unknown_layer checks it
    Then it faults a layer that is a word somebody coined rather than one of the known layers

  Scenario: _duplicate_names faults two declarations of one kind sharing a name
    Given a module's declarations
    When _duplicate_names checks each kind for repeats
    Then it faults two functions, types, sets, chains, vocabularies, envs or stores that share one name

  Scenario: _impure_pure_functions faults a pure fn that declares a side effect
    Given a module's functions
    When _impure_pure_functions checks each plain fn
    Then it faults a pure fn that declares any side effect, because only a boundary may

  Scenario: _held_not_read faults a pure fn that names a handle in its signature
    Given a module's functions and the names that mean a handle
    When _held_not_read checks each pure fn's signature
    Then it faults a pure fn that names a handle, because a handle is held and passed to a boundary, never read

  Scenario: _fault_swallowed faults a caller that cannot return the fault its callee can
    Given a module's call graph and the functions whose return says they can fault
    When _fault_swallowed follows the faults up through the returns
    Then it faults a caller that invokes a faulting callee yet cannot return a fault, unless it is a boundary that raises

  Scenario: _fault_shape faults a Fault declared without fields to explain it
    Given a module that can fault
    When _fault_shape reads the Fault type
    Then it faults a Fault declared as a bare name or with fewer than two fields to say what went wrong and what to do instead

  Scenario: _unawaited_caller faults a caller of an awaited function that is not awaited
    Given a module's awaited functions and its call graph
    When _unawaited_caller follows the awaited word up through the returns
    Then it faults a caller whose callee is awaited but which is not itself awaited

  Scenario: _door_called faults a function that invokes an input boundary
    Given a module's functions
    When _door_called checks each one's invokes and chain
    Then it faults a function that calls a boundary_in, because the world calls a door and nothing inside the module does

  Scenario: _reader_calls faults a reader that invokes anything
    Given a module's readers
    When _reader_calls checks each one
    Then it faults a reader that invokes a function or heads a chain, because a reader answers the program and asks nothing of it

  Scenario: _store_of_impure faults a store of anything but a plain pure function
    Given a module's stores
    When _store_of_impure checks what each store holds
    Then it faults a store whose named function is not a plain pure fn

  Scenario: _unknown_stores faults a side effect naming an undeclared store
    Given a module's functions and store declarations
    When _unknown_stores checks each store read
    Then it faults a side effect that names no declared store

  Scenario: _store_not_orchestrator faults a boundary that reaches a store
    Given a module's functions
    When _store_not_orchestrator checks who reaches each store
    Then it faults any reader or boundary that reaches a store, because only an orchestrator keeps what each step returned

  Scenario: _surface_undeclared faults a module with boundaries and no surface list
    Given a module that declares boundaries
    When _surface_undeclared checks for an inputs or outputs block
    Then it faults an open surface, one fault for a module that lists neither

  Scenario: _surface_unknown faults a side a boundary touches that the surface omits
    Given a module's boundaries and its surface lists
    When _surface_unknown checks each side read against inputs and each side written against outputs
    Then it faults a side a boundary touches that its surface list does not name

  Scenario: _surface_unused faults a listed side no boundary touches
    Given a module's surface lists and its boundaries
    When _surface_unused checks each listed side
    Then it faults a listed side that no boundary reads or writes, a stale declaration

  Scenario: _boundary_without_surface faults a boundary that touches no side of the world
    Given a module's boundaries
    When _boundary_without_surface checks each one's side effects and entries
    Then it faults a boundary that reads or writes nothing and that no entry or route names

  Scenario: _door_takes_readable faults a door that takes what the module can read for itself
    Given a module's input boundaries
    When _door_takes_readable checks each door's parameters
    Then it faults a door whose parameter type is something a reader of the module already pulls

  Scenario: _bad_projections faults a dispatch projection that names no real field
    Given a module's dispatch tables and the functions that invoke them
    When _bad_projections checks each entry's from against the caller's input and handler
    Then it faults a projection that names no real field of the caller's input, or a handler that does not take it

  # --- the shared check helpers ---------------------------------------------

  Scenario: _declared_functions gathers the names of every declared function
    Given a module
    When _declared_functions reads its functions
    Then it returns the set of their names

  Scenario: _env_reads gathers every function and the env variable it reads
    Given a module
    When _env_reads reads the side effects
    Then it returns every pair of a function and the environment variable it names

  Scenario: _type_names gathers every type name an expression mentions at any depth
    Given a type expression
    When _type_names walks it
    Then it returns every name it mentions, counting both halves of a nested type

  Scenario: _reaches_handle answers whether a name resolves to the handle within budget
    Given a name, the module's type aliases, and a budget of steps
    When _reaches_handle follows the aliases
    Then it answers whether the name is the handle or an alias that leads to it, and a cycle ends when the budget does

  Scenario: _handles gathers the names that mean a handle
    Given a module's type aliases
    When _handles resolves each
    Then it returns the handle scalar and every alias that leads to it

  Scenario: _can_fault gathers the functions whose return says they can fail
    Given a module's functions
    When _can_fault reads each return type
    Then it returns the names of the functions whose return names Fault

  Scenario: _callees gathers every caller and callee whose answer returns to the caller
    Given a module's invokes, dispatch tables and chains
    When _callees reads them
    Then it returns each pair once, a dispatch caller inheriting every handler

  Scenario: _store_reads gathers every function and the store it names
    Given a module
    When _store_reads reads the side effects
    Then it returns every pair of a function and the store it names

  Scenario: _world_targets gathers the world sides a function touches in given directions
    Given a function and a set of directions
    When _world_targets reads its side effects
    Then it returns the world sides it touches in those directions, leaving its own env and store aside

  Scenario: _boundaries gathers a module's boundary functions
    Given a module
    When _boundaries reads its functions
    Then it returns the input and output boundaries

  Scenario: _callers_of gathers the functions that invoke a dispatch table
    Given a module and a dispatch table's name
    When _callers_of reads the invokes
    Then it returns the functions that invoke that table, whose input the table projects from

  Scenario: _record_fields gathers every declared record's fields by type name
    Given a module
    When _record_fields reads its types
    Then it returns each record type's fields, keyed by the type name

  # --- the renderer ---------------------------------------------------------

  Scenario: _node builds a diagram node from a function
    Given a function
    When _node reads its name, role and side-effect targets
    Then it returns a diagram node carrying them

  Scenario: _column builds one column of the diagram
    Given a module and a column index
    When _column gathers the functions whose role sits in that column
    Then it returns the column with its title and nodes

  Scenario: _edges builds the chain edges of the diagram
    Given a module's chains
    When _edges reads each adjacent link pair
    Then it returns one edge per pair, naming the chain, the source and the destination

  # --- reach ----------------------------------------------------------------

  Scenario: _world gathers the sides of the world a function touches directly
    Given a function and the declarations it may reach
    When _world reads its side effects
    Then it returns the world sides it touches directly, leaving out a seam, its own env or store, and the direction a call arrived from

  Scenario: _seams gathers the sides of a function that enter another module
    Given a function and the declarations it may reach
    When _seams reads its side effects
    Then it returns each seam as a module and a door, the door empty when the side names a module alone

  Scenario: _onward gathers who each function hands on to
    Given a module
    When _onward reads the invokes and the chains
    Then it returns, per function, the functions it invokes and the next link of any chain it is on

  Scenario: _walk follows one path from a start and answers what it touches
    Given a module, a starting function, the declarations it may reach, and the paths already seen
    When _walk follows the path, through its seams into other modules
    Then it answers the world touched directly, the world reached past a seam, and the seams it could not follow, once per path already seen

  # --- the Result constructors ----------------------------------------------

  Scenario: ok wraps a value in a successful Result
    Given a value the reader produced
    When ok wraps it
    Then it returns a Result carrying that value under "ok"

  Scenario: err wraps a fault in a failed Result
    Given a fault produced during reading
    When err wraps it
    Then it returns a Result carrying that fault under "err"

  Scenario: fault constructs a fault record as data
    Given a code, a message, a category, and detail
    When fault assembles them
    Then it returns a fault record carrying those four fields, never raised


  # --- reader helpers (restored as they stood at HEAD) ----------------------

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

  # --- checks the .hd declares ----------------------------------------------

  Scenario: _missing_note faults every function that has no note
    Given one module's IR
    When _missing_note reads each function's note
    Then it returns a missing_note fault for each function with no note, the domain description written once at authoring time

  Scenario: _door_orchestrator faults a door that does not hand to exactly one orchestrator
    Given one module's IR
    When _door_orchestrator follows each door's calls
    Then it returns a door_orchestrator fault for a door that reaches no orchestrator or more than one

  Scenario: couples_on says whether a world-side target couples two modules
    Given a world-side target
    When couples_on reads it
    Then a named kind couples and returns True
    But a bare kind, or the reserved name given, returns False

Feature: honest-persist — schema diffing, query building, and the write boundary
  One scenario per function. honest-test's auto-generation proves every case;
  each scenario names the single behaviour that proof stands on, and the count of
  scenarios is the module's directly-counted function-point size. Dialect-specific
  rendering lives in the language supplement; everything here is platform-neutral.

  Scenario: operation packages one schema change as data
    Given a change name, the object it acts on, and that change's details
    When operation assembles them
    Then it returns a record carrying the change name as its discriminator and its details
    And when no details are given the details are empty

  Scenario: diff_result packages the outcome of a schema diff as data
    Given the operations, their dependencies, an execution order, and any ambiguities
    When diff_result assembles them
    Then it returns a record carrying all four together

  Scenario: diff produces the operations that transform one schema into another
    Given a current schema and a target schema, with optional rename decisions
    When diff compares them
    Then it returns the dependency-ordered operations that turn current into target, together with the ambiguities it found
    But if the target schema is internally inconsistent it returns a "schema_invalid" fault
    And if the dependency graph contains a cycle it returns a "schema_cycle" fault

  Scenario: validate_schema checks a schema for internal consistency
    Given a schema, given either bare or as a full definition
    When validate_schema inspects it
    Then it returns the schema unchanged when every reference resolves
    But if any reference is broken it returns a "schema_invalid" fault listing every error

  Scenario: _resolve_renames separates true renames from fresh additions
    Given the added names, the dropped names, and the target definitions
    When _resolve_renames inspects each added name's rename hint
    Then an added name whose hint points at a dropped name is paired as a rename
    And every other added name is reported as a genuine addition

  Scenario: _compute_alterations finds the differences between two column definitions
    Given a current column definition and a target column definition
    When _compute_alterations compares them
    Then it reports each of type, nullability, and default that changed, with its old and new value
    But if nothing changed it reports no alterations

  Scenario: _diff_columns produces the column changes for a shared table
    Given the current columns and target columns of one table
    When _diff_columns compares them
    Then it emits drops, renames, additions, and alterations so the columns match the target
    But a column consumed by a rename is not also dropped

  Scenario: _diff_foreign_keys produces the foreign-key changes for shared columns
    Given the current and target definitions of columns present in both schemas
    When _diff_foreign_keys compares each column's reference
    Then a changed reference becomes a drop of the old foreign key and an add of the new
    But an unchanged reference produces nothing

  Scenario: _diff_named produces the changes for named sub-objects
    Given a table's current and target named objects with their add and drop change names
    When _diff_named compares them
    Then added names become adds, dropped names become drops, and changed names become a drop followed by an add

  Scenario: _diff_table produces every change for a table present in both schemas
    Given a table's current and target definitions
    When _diff_table compares them
    Then it gathers the column, foreign-key, index, and constraint changes for that table

  Scenario: _diff_views produces the view changes between two schemas
    Given the current views and target views
    When _diff_views compares them
    Then added views become creates, dropped views become drops, and a changed view becomes a drop followed by a create
    And each change carries the view's declared dependencies for ordering

  Scenario: _diff_triggers produces the trigger changes between two schemas
    Given the current triggers and target triggers
    When _diff_triggers compares them
    Then added triggers become creates, dropped triggers become drops, and a changed trigger becomes a drop followed by a create
    And each change records the table the trigger fires on so it orders after that table

  Scenario: _diff_procedures produces the procedure changes between two schemas
    Given the current procedures and target procedures
    When _diff_procedures compares them
    Then added become creates and dropped become drops
    And a changed function is replaced in place while a changed non-function procedure becomes a drop followed by a create

  Scenario: _normalize coerces any schema shape into a full definition
    Given either a bare table mapping or a full schema definition
    When _normalize inspects it
    Then a definition carrying the reserved sections is kept with each section filled in
    But a bare table mapping becomes a definition whose tables are those tables and whose other sections are empty

  Scenario: _reference_error reports whether a reference resolves in a schema
    Given a "table.column" reference and the schema
    When _reference_error resolves it
    Then it reports nothing when the table and column both exist
    But it returns a message when the reference is malformed, names an unknown table, or names an unknown column

  Scenario: _table_errors collects the internal-consistency errors of one table
    Given a table definition and the schema it belongs to
    When _table_errors inspects it
    Then it reports each dangling foreign key and every primary-key, index, or constraint reference to a column that does not exist
    But a consistent table yields no errors

  Scenario: _subject names the object an operation acts on
    Given an operation
    When _subject reads it
    Then it returns the view, trigger, or function name when present, otherwise the table

  Scenario: _related decides whether two operations touch the same thing
    Given two operations
    When _related compares them
    Then they are related when they share a table, when one's foreign key references the other's subject, or when one declares the other's subject as a dependency

  Scenario: _runs_before decides whether one operation must precede another
    Given two operations
    When _runs_before consults the ordering rules
    Then it is true when the first is a prerequisite the second depends on, or when the first must precede the second, and the two are related
    But unrelated operations impose no order

  Scenario: build_dependencies maps each operation to the operations that must run first
    Given a list of operations
    When build_dependencies pairs every operation against every other
    Then it returns, for each operation, the indices of the operations that must run before it

  Scenario: topological_sort produces a valid execution order of operations
    Given the operations and their dependencies
    When topological_sort orders them
    Then it returns an order in which every prerequisite comes before the operation that needs it, ties broken by index for determinism
    But if the dependency graph has a cycle it returns nothing

  Scenario: detect_ambiguities reports drops and adds that might be renames
    Given a current schema, a target schema, and the rename decisions already made
    When detect_ambiguities compares the columns of tables in both
    Then it reports each dropped-and-added pair that could be a rename, with a confidence from type match and name similarity
    But pairs already resolved by a hint or a decision, and pairs below the confidence threshold, are not reported

  Scenario: _levenshtein measures the edit distance between two names
    Given two strings
    When _levenshtein compares them
    Then it returns the fewest single-character edits that turn one into the other

  Scenario: _confidence scores how likely a drop-and-add is a rename
    Given a current column, a target column, and the two names
    When _confidence weighs them
    Then matching types with similar names score highest, matching types alone score lower, and differing types score zero

  Scenario: parse_check compiles a CHECK expression into an evaluable tree
    Given a CHECK expression as text
    When parse_check compiles it
    Then it returns the expression tree when the expression is within the supported vocabulary
    But an expression using an unsupported token or that cannot be compiled returns an "uncompilable_check" fault, never a silently dropped guarantee

  Scenario: check_holds evaluates a compiled CHECK tree against a row
    Given a compiled CHECK tree and a row
    When check_holds evaluates it
    Then it reports whether the row satisfies the constraint

  Scenario: _tokenize breaks a CHECK expression into tokens
    Given a CHECK expression as text
    When _tokenize scans it
    Then it yields a token for each name, number, string, keyword, comparison, and grouping symbol, ending with an end marker
    And any character outside the vocabulary becomes an unknown token

  Scenario: _number reads a numeric token's value
    Given the text of a numeric token
    When _number reads it
    Then a text containing a point becomes a fractional number, otherwise a whole number

  Scenario: _peek looks at the current token without consuming it
    Given the tokens and a cursor
    When _peek reads the cursor's position
    Then it returns the current token and leaves the cursor where it was

  Scenario: _advance consumes the current token
    Given the tokens and a cursor
    When _advance reads the cursor's position
    Then it returns the current token and moves the cursor past it

  Scenario: _parse_term parses one operand of a comparison
    Given the tokens and a cursor
    When _parse_term reads the current token
    Then a name becomes a column reference and a number or string becomes a literal value
    But any other token yields nothing

  Scenario: _parse_value_list parses a parenthesized list of literals
    Given the tokens and a cursor positioned at an opening parenthesis
    When _parse_value_list reads the list
    Then it returns the comma-separated literals up to the closing parenthesis
    But a missing parenthesis or a non-literal entry yields nothing

  Scenario: _parse_comparison parses a comparison or membership test
    Given the tokens and a cursor
    When _parse_comparison reads a term and what follows
    Then a comparison operator yields a comparison of the two terms and a membership keyword yields a test against a value list
    But a term with neither following it yields nothing

  Scenario: _parse_primary parses a grouped expression or a comparison
    Given the tokens and a cursor
    When _parse_primary reads the current token
    Then an opening parenthesis parses a full sub-expression up to its closing parenthesis, otherwise it parses a comparison
    But an unbalanced parenthesis yields nothing

  Scenario: _parse_not parses an optional negation
    Given the tokens and a cursor
    When _parse_not reads the current token
    Then a negation keyword wraps the clause that follows it as a negation, otherwise it parses the primary unchanged

  Scenario: _parse_junction parses a chain of operands joined by one keyword
    Given the tokens, a cursor, the joining keyword, the junction kind, and how to parse an operand
    When _parse_junction reads operands separated by the keyword
    Then a single operand is returned alone and several become a junction of that kind over all of them
    But a missing operand after the keyword yields nothing

  Scenario: _parse_and parses operands joined by the conjunction keyword
    Given the tokens and a cursor
    When _parse_and reads them
    Then it returns the conjunction of the negation-level operands it finds

  Scenario: _parse_or parses operands joined by the disjunction keyword
    Given the tokens and a cursor
    When _parse_or reads them
    Then it returns the disjunction of the conjunction-level operands it finds

  Scenario: _eval_term resolves one operand against a row
    Given a term and a row
    When _eval_term resolves it
    Then a column reference returns that column's value from the row and a literal returns its own value

  Scenario: _eval_compare evaluates a comparison against a row
    Given a comparison node and a row
    When _eval_compare evaluates it
    Then it compares the two resolved operands with the node's operator

  Scenario: _eval_and evaluates a conjunction against a row
    Given a conjunction node and a row
    When _eval_and evaluates it
    Then it holds only when every clause holds

  Scenario: _eval_or evaluates a disjunction against a row
    Given a disjunction node and a row
    When _eval_or evaluates it
    Then it holds when any clause holds

  Scenario: _eval_not evaluates a negation against a row
    Given a negation node and a row
    When _eval_not evaluates it
    Then it holds exactly when its inner clause does not

  Scenario: _eval_in evaluates a membership test against a row
    Given a membership node and a row
    When _eval_in evaluates it
    Then it holds when the resolved term is one of the listed values

  Scenario: _apply_result records the outcome of applying a diff
    Given whether the apply succeeded, the statements that ran, any error, and the operation it failed on
    When _apply_result assembles them
    Then it returns a record carrying the outcome, the statements applied, and how many there were

  Scenario: _pause_push asks a connection to pause replication push
    Given a connection
    When _pause_push is invoked
    Then it pauses replication push when the connection supports it, otherwise it does nothing

  Scenario: _resume_push asks a connection to resume replication push
    Given a connection
    When _resume_push is invoked
    Then it resumes replication push when the connection supports it, otherwise it does nothing

  Scenario: execute runs a built query and returns every row
    Given a built query and a connection
    When execute runs the query
    Then it returns every row the query produced as plain data

  Scenario: execute_one runs a built query and returns the first row
    Given a built query and a connection
    When execute_one runs the query
    Then it returns the first row, or nothing when the query produced none

  Scenario: execute_scalar runs a built query and returns one value
    Given a built query and a connection
    When execute_scalar runs the query
    Then it returns the first value of the first row, or nothing when the query produced none

  Scenario: execute_many runs a built query and returns the count it changed
    Given a built query and a connection
    When execute_many runs the query
    Then it returns the number of rows the query affected

  Scenario: requires_reconstruction reports whether an operation needs a table rebuild
    Given an operation and a target engine
    When requires_reconstruction consults the engine's rules
    Then it is true only when that engine cannot apply that operation in place

  Scenario: _columns_added names the columns this diff introduces to a table
    Given the operations and a table
    When _columns_added collects them
    Then it returns the columns the diff adds to that table, which the rebuild must not copy from the old table

  Scenario: apply executes a diff against a database in execution order
    Given a diff result, the target schema, a connection, a target engine, and an optional injected emit
    When apply runs the operations in order
    Then it applies each operation, rebuilding any table that cannot be altered in place, returns a record of what was applied, and emits one migration event per operation through the emit
    But if the diff still has unresolved ambiguities it refuses and returns a failure
    And it halts on the first operation that fails, emitting that operation with its fault code, returning the failure and what had already run

  Scenario: _emit_migration emits one migration event through the injected emit
    Given the injected emit, the operation facts, and whether it succeeded
    When _emit_migration emits the event
    Then it sends one hf.persist.migration through the emit, keyed by the schema aggregate, but a failure in the emit is logged and swallowed, and no emit means no event

  Scenario: _reconstruct rebuilds one table to its target shape
    Given a table, the target tables, the operations, a connection, the engine, and the running record of applied statements
    When _reconstruct rebuilds the table while sync push is paused
    Then it records the rebuild statements and reports success
    But if any statement fails it resumes sync push and returns the failure

  Scenario: transaction runs several writes as one all-or-nothing step
    Given a sequence of writes and a connection
    When transaction applies them
    Then it appends each write and commits them together, reporting the rows each affected
    But if any write fails it rolls the whole transaction back and returns a "write_failed" fault carrying the failing write's position

  Scenario: dialect_enforces_check reports whether a dialect enforces CHECK natively
    Given a dialect
    When dialect_enforces_check is asked
    Then it is true for a dialect that enforces CHECK natively and false for one that does not

  Scenario: table_checks collects a table's declared CHECK expressions
    Given a table with column-level and table-level CHECK constraints
    When table_checks collects them
    Then it returns the column-level checks then the table-level check constraints in declaration order

  Scenario: enforce_checks validates a row against a table's CHECK constraints
    Given a schema, table, row, and dialect
    When enforce_checks validates the row
    Then on a native dialect it trusts the database, and otherwise it compiles each CHECK and returns a check_violation for a failing row or an uncompilable_check for one that cannot be compiled

  Scenario: build_transaction_event builds the hf.persist.transaction payload
    Given a db id, write count, outcome, failed-at index, duration, and request id
    When build_transaction_event builds the payload
    Then it returns the transaction event with the write count, outcome, failing index, duration, and request id

  Scenario: _emit_transaction emits the transaction event through the injected emit
    Given an injected emit, db id, and the transaction outcome
    When _emit_transaction emits the event
    Then it emits one hf.persist.transaction keyed by the db, swallows a failing emit, and is a no-op when no emit is wired in

  Scenario: validate_checks rejects an unenforceable CHECK at construction
    Given a schema and a target dialect
    When validate_checks validates the declared CHECKs
    Then on a native dialect it trusts the database, and otherwise a CHECK that cannot be compiled is a construction-time uncompilable_check fault rather than a silently dropped guarantee

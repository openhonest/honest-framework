Feature: honest-persist (Python supplement) — SQL rendering and query construction
  The host-language and SQL-dialect behaviour that the platform-neutral feature cannot
  state. One scenario per function: the DDL renderers, the type map, and the query
  builders all emit concrete SQL, whose exact form belongs to the dialect, not the
  language-agnostic standard. The count joins the neutral count to equal the module's
  function-point size.

  Scenario: _sql_type maps an abstract type to its dialect spelling
    Given an abstract type name and a target dialect
    When _sql_type looks it up
    Then it returns the dialect's concrete type for that abstract type, or the name unchanged when the dialect has no mapping for it

  Scenario: _column_ddl renders one column's definition as DDL
    Given a column name, its definition, and a dialect
    When _column_ddl renders it
    Then it produces the name and dialect type followed by the primary-key, not-null, unique, and default clauses the definition declares

  Scenario: _render_create_table renders a CREATE TABLE statement
    Given a create-table operation and a dialect
    When _render_create_table renders it
    Then it produces a CREATE TABLE statement with each column rendered as DDL

  Scenario: _render_drop_table renders a DROP TABLE statement
    Given a drop-table operation and a dialect
    When _render_drop_table renders it
    Then it produces a DROP TABLE statement for that table

  Scenario: _render_rename_table renders an ALTER TABLE RENAME statement
    Given a rename-table operation and a dialect
    When _render_rename_table renders it
    Then it produces an ALTER TABLE RENAME TO statement to the new name

  Scenario: _render_add_column renders an ADD COLUMN statement
    Given an add-column operation and a dialect
    When _render_add_column renders it
    Then it produces an ALTER TABLE ADD COLUMN statement with the column rendered as DDL

  Scenario: _render_drop_column renders a DROP COLUMN statement
    Given a drop-column operation and a dialect
    When _render_drop_column renders it
    Then it produces an ALTER TABLE DROP COLUMN statement for that column

  Scenario: _render_rename_column renders a RENAME COLUMN statement
    Given a rename-column operation and a dialect
    When _render_rename_column renders it
    Then it produces an ALTER TABLE RENAME COLUMN statement from the old name to the new

  Scenario: _render_alter_column renders the column alterations as DDL
    Given an alter-column operation and a dialect
    When _render_alter_column renders it
    Then it produces, in PostgreSQL form, an ALTER COLUMN clause for each of the changed type, nullability, and default

  Scenario: _render_add_index renders a CREATE INDEX statement
    Given an add-index operation and a dialect
    When _render_add_index renders it
    Then it produces a CREATE INDEX statement over the named columns, marked unique when the definition is unique

  Scenario: _render_drop_index renders a DROP INDEX statement
    Given a drop-index operation and a dialect
    When _render_drop_index renders it
    Then it produces a DROP INDEX statement for that index

  Scenario: _render_add_foreign_key renders an ADD CONSTRAINT foreign-key statement
    Given an add-foreign-key operation and a dialect
    When _render_add_foreign_key renders it
    Then it produces an ALTER TABLE ADD CONSTRAINT FOREIGN KEY statement referencing the named table and column, with a derived constraint name

  Scenario: _render_drop_foreign_key renders a DROP CONSTRAINT foreign-key statement
    Given a drop-foreign-key operation and a dialect
    When _render_drop_foreign_key renders it
    Then it produces an ALTER TABLE DROP CONSTRAINT statement using the derived foreign-key constraint name

  Scenario: _render_add_constraint renders an ADD CONSTRAINT CHECK statement
    Given an add-constraint operation and a dialect
    When _render_add_constraint renders it
    Then it produces an ALTER TABLE ADD CONSTRAINT CHECK statement with the constraint's expression

  Scenario: _render_drop_constraint renders a DROP CONSTRAINT statement
    Given a drop-constraint operation and a dialect
    When _render_drop_constraint renders it
    Then it produces an ALTER TABLE DROP CONSTRAINT statement for that constraint

  Scenario: to_sql renders one operation to a DDL string for a dialect
    Given an operation and a dialect
    When to_sql dispatches on the operation's change name
    Then it returns the rendered DDL for that operation
    But an operation type with no renderer returns nothing

  Scenario: reconstruction_sql renders the statements that rebuild a table
    Given a table, its target shape, the columns to carry over, a dialect, and an optional temporary name
    When reconstruction_sql renders the rebuild
    Then it produces the statements to create a temporary table, copy the shared columns, drop the old, rename the temporary into place, and recreate the target indexes
    And without a supplied temporary name it uses a deterministic default so the plan is reproducible

  Scenario: _query packages built SQL with its named parameters
    Given a SQL string and its parameter map
    When _query assembles them
    Then it returns a query record carrying the SQL and its parameters

  Scenario: _where_clause builds a WHERE clause from equality conditions
    Given a mapping of columns to required values
    When _where_clause builds it
    Then it produces a WHERE clause of named-parameter equalities joined by AND, with the matching parameters
    But an empty mapping produces no clause and no parameters

  Scenario: _order_clause builds an ORDER BY clause from a column list
    Given a list of order columns
    When _order_clause builds it
    Then it produces an ORDER BY clause where a leading minus marks descending and any other column is ascending
    But an empty list produces no clause

  Scenario: _join_clause builds JOIN clauses from join specifications
    Given a list of join specifications
    When _join_clause builds them
    Then it produces a JOIN clause for each specification's table and condition
    But an empty list produces no clause

  Scenario: select builds a parameterized SELECT query
    Given a table and optional columns, conditions, ordering, limit, offset, and joins
    When select builds the query
    Then it returns a SELECT query naming the columns, joins, conditions, and ordering, with limit and offset as named parameters when supplied

  Scenario: insert builds a parameterized INSERT query
    Given a table and the values to insert
    When insert builds the query
    Then it returns an INSERT query whose columns and named-parameter placeholders match the values

  Scenario: update builds a parameterized UPDATE query
    Given a table, the new values, and the conditions to match
    When update builds the query
    Then it returns an UPDATE query whose set parameters are prefixed so they never collide with a condition parameter on the same column

  Scenario: delete builds a parameterized DELETE query
    Given a table and the conditions to match
    When delete builds the query
    Then it returns a DELETE query with the matching WHERE clause and parameters

  Scenario: raw builds a query from supplied SQL and parameters
    Given a SQL string and optional named parameters
    When raw builds the query
    Then it returns a query carrying that SQL and those parameters as the escape hatch, still data

  Scenario: _declared_columns names the columns declared for a table
    Given a schema and a table
    When _declared_columns reads the schema
    Then it returns the declared column names for that table, or nothing when the table is undeclared

  Scenario: _unknown_columns finds referenced names that are not declared
    Given the declared columns and the referenced names
    When _unknown_columns compares them
    Then it returns, sorted, the referenced names that are not declared, ignoring the wildcard and an ordering minus prefix

  Scenario: _check_columns verifies a table and its referenced columns are declared
    Given a schema, a table, and the names a query references
    When _check_columns verifies them
    Then it returns the table when the table and every referenced column is declared
    But an undeclared table returns an "unknown_table" fault and undeclared columns return an "unknown_column" fault

  Scenario: checked_select builds a SELECT only against a declared schema
    Given a schema, a table, and the optional clauses of a select
    When checked_select verifies the references
    Then it returns the built SELECT query when the table, columns, conditions, ordering, and join tables are all declared
    But an undeclared reference returns a fault

  Scenario: checked_insert builds an INSERT only against a declared schema
    Given a schema, a table, and the values to insert
    When checked_insert verifies the references
    Then it returns the built INSERT query when the table and value columns are declared
    But an undeclared reference returns a fault

  Scenario: checked_update builds an UPDATE only against a declared schema
    Given a schema, a table, the new values, and the conditions
    When checked_update verifies the references
    Then it returns the built UPDATE query when the table, value columns, and condition columns are declared
    But an undeclared reference returns a fault

  Scenario: checked_delete builds a DELETE only against a declared schema
    Given a schema, a table, and the conditions
    When checked_delete verifies the references
    Then it returns the built DELETE query when the table and condition columns are declared
    But an undeclared reference returns a fault

  # pool-layer instrumentation (section 8)
  Scenario: pool_fault builds a typed pool fault with its category
    Given a pool fault code and a message
    When pool_fault builds it
    Then it returns the fault with its category — a caller error for an unknown database or tenant, a server error otherwise

  Scenario: extract_table reads the table a SQL statement targets
    Given a SQL string
    When extract_table reads it
    Then it returns the identifier after FROM, INTO, UPDATE, or TABLE, or an empty string when none is present

  Scenario: sql_hash digests a SQL string
    Given a SQL string
    When sql_hash digests it
    Then it returns a stable SHA-256 hex digest, the same for the same SQL and different for different SQL, so queries group without exposing parameter values

  Scenario: build_query_event builds the query event payload
    Given the facts of a completed query and whether the run is in development
    When build_query_event builds the payload
    Then it carries the db, table, operation, row count, duration, and SQL hash, including the full SQL only in development mode

  Scenario: build_migration_event builds the migration event payload
    Given a DDL operation that apply executed
    When build_migration_event builds the payload
    Then it carries the db, operation, table, detail, duration, SQL, success, and any fault — one event per operation, a schema-change history

  Scenario: build_pool_event builds the pool lifecycle event payload
    Given a pool lifecycle transition
    When build_pool_event builds the payload
    Then it carries the db, the event, the pool size, the active and waiting counts, and any duration or fault, so pool health is in the same log

  Scenario: instrumented_execute runs a query and emits the query event
    Given a query, a connection, an injected emit, and the query's context
    When instrumented_execute runs the query
    Then it returns the rows and emits one hf.persist.query event keyed by db and table, with the fault code on failure, then re-raises
    But a failing emit never breaks the query, and no emit means no event

  Scenario: _safe_emit emits the query event and swallows an emit failure
    Given the injected emit, an aggregate id, and a query event payload
    When _safe_emit emits it
    Then it sends the hf.persist.query event through the emit, but a failure in the emit is logged and swallowed so it never breaks the query

  Scenario: resolve_pool_key routes a manifest to its pool selector
    Given a manifest with its database-routing keys
    When resolve_pool_key resolves it
    Then a db_id selects a registered database and a tenant_id a per-tenant one, carrying the credential and the lifecycle, defaulting the lifecycle to persistent
    But a manifest that names no database returns an unknown-database fault

  Scenario: empty_pool_registry is an empty pool cache
    Given nothing
    When empty_pool_registry is called
    Then it returns an empty cache of pools, held as a value rather than hidden state

  Scenario: _pool_key keys a pool by its database and credential variant
    Given a pool selector
    When _pool_key keys it
    Then it returns one key per database and credential variant, so each variant caches its own pool

  Scenario: get_pool routes a manifest to a cached connection, creating one on first contact
    Given a pool registry, a manifest, an injected connect, the current time, and an optional injected emit
    When get_pool routes the manifest
    Then on first contact it creates a connection through connect, caches it with its lifecycle and last-used time, and emits a created pool event, while a seen database reuses the cached one and refreshes its last-used time without re-emitting
    But a manifest naming no database returns an unknown-database fault and leaves the cache unchanged

  Scenario: emit_pool_event emits a pool lifecycle event through the injected emit
    Given the injected emit and the facts of a pool lifecycle transition
    When emit_pool_event emits it
    Then it sends one hf.persist.pool event keyed by the pool aggregate, but a failing emit is logged and swallowed and no emit means no event

  Scenario: empty_write_queue is an empty write queue
    Given nothing
    When empty_write_queue is called
    Then it returns an empty queue of pending writes, held as a value

  Scenario: enqueue_write appends a pending write to the queue
    Given a write queue, an operation, a table, and a row
    When enqueue_write appends the write
    Then it returns a new queue with the pending write added, never mutating the original

  Scenario: merge_pending folds the pending writes for a table into a read
    Given the rows from a read, a write queue, the table, and its primary key
    When merge_pending folds the pending writes in
    Then a pending insert or update sets the row by primary key and a pending delete removes it, so a write is visible in reads before it reaches the backend, while writes for other tables are ignored

  Scenario: _insert_query builds the query for a pending insert
    Given a table, a row, and the primary key
    When _insert_query builds it
    Then it returns the insert query for the row

  Scenario: _update_query builds the query for a pending update
    Given a table, a row, and the primary key
    When _update_query builds it
    Then it returns the update query setting the non-key columns where the primary key matches

  Scenario: _delete_query builds the query for a pending delete
    Given a table, a row, and the primary key
    When _delete_query builds it
    Then it returns the delete query for the row's primary key

  Scenario: _write_query builds the query for one pending write by its operation
    Given a pending write and the primary key
    When _write_query builds the query
    Then it dispatches by operation to the insert, update, or delete query

  Scenario: drain_queue persists each pending write to the backend
    Given a write queue, a connection, an injected execute, and the primary key
    When drain_queue drains the queue
    Then it persists each pending write to the backend through execute, in order, and returns the empty queue

  Scenario: queue_to_jsonl renders the write queue to its durable JSONL form
    Given a write queue
    When queue_to_jsonl renders it
    Then it returns one JSON object per pending write, the form that survives a restart

  Scenario: queue_from_jsonl parses a write queue from its JSONL form
    Given the JSONL form of a write queue
    When queue_from_jsonl parses it
    Then it returns the pending writes, ignoring blank lines

  Scenario: backoff_delay computes the exponential backoff before the next retry
    Given an attempt number and a base delay
    When backoff_delay computes the delay
    Then it returns the base delay doubled per attempt

  Scenario: is_stalled reports whether the queue has been failing past the limit
    Given the time of the first failure and the current time
    When is_stalled checks it
    Then it is true once the queue has been failing past the six-hour limit

  Scenario: save_queue persists the write queue to its JSONL file
    Given a write queue and a file path
    When save_queue saves it
    Then it writes the queue's JSONL form to the file so pending writes survive a restart

  Scenario: load_queue loads the write queue from its JSONL file
    Given a file path
    When load_queue loads it
    Then it returns the queue parsed from the file, or an empty queue when the file does not exist

  Scenario: _emit_queue_stalled emits the queue-stalled event through the injected emit
    Given the injected emit, the queue depth, and how long it has stalled
    When _emit_queue_stalled emits it
    Then it sends one hf.persist.queue_stalled event, but a failing emit is logged and swallowed and no emit means no event

  Scenario: supervise_drain drains the queue with retry, stalling past the limit
    Given a write queue, a connection, an injected execute, the primary key, the times, and an injected emit
    When supervise_drain attempts the drain
    Then a successful drain clears the queue and resets the failure clock, and a failure keeps the queue and starts the clock
    But once it has been failing past the limit it emits queue_stalled and raises the fault, never discarding the writes

  Scenario: enqueue_durable appends a write and persists the queue
    Given a write queue, an operation, a table, a row, and the queue's file path
    When enqueue_durable appends the write
    Then it returns the new queue and persists it to the file, so the write survives a restart before it reaches the backend

  Scenario: run_drain_loop drains the queue in the background, retrying with backoff
    Given a write queue, a connection, an injected execute, the primary key, a base delay, an injected clock and sleep, and an injected emit
    When run_drain_loop drains the queue
    Then it retries a failing backend, sleeping the exponential backoff between attempts, until the queue drains
    But a queue that keeps failing past the limit stalls and raises the fault

  Scenario: is_idle reports whether a pool has been idle past the threshold
    Given a pool's last-used time, the current time, and an idle threshold
    When is_idle checks it
    Then it is true only once the idle time exceeds the threshold

  Scenario: reap_idle closes and evicts the on_demand pools idle past the threshold
    Given a pool registry, the current time, a threshold, an injected close, and an optional injected emit
    When reap_idle reaps the registry
    Then it closes and evicts each on_demand pool idle past the threshold through close, emitting a closed pool event for each
    But persistent and ephemeral pools, and recently-used on_demand pools, are left in the cache

  Scenario: recreate_ephemeral rebuilds each ephemeral database's schema at startup
    Given the persist configuration, an injected connect, an engine, and the current time
    When recreate_ephemeral runs at startup
    Then it connects, applies the target schema, and caches a pool for each ephemeral database in configuration order, leaving the persistent and on_demand ones alone, so ephemeral data never survives a restart

  Scenario: new_pool holds N connections as a value
    Given a list of connections
    When new_pool builds the pool
    Then it returns a pool recording the size, the idle connections, and zero active

  Scenario: acquire_connection takes an idle connection or faults when full
    Given a connection pool
    When acquire_connection takes a connection
    Then it returns ok(connection) with the connection moved to active, but err(pool_exhausted) and the unchanged pool when every connection is in use

  Scenario: release_connection returns a connection to the idle set
    Given a pool and a connection taken from it
    When release_connection returns it
    Then the connection is idle again and the active count drops by one

  Scenario: lease_connection acquires a connection, emitting exhausted when full
    Given a pool, a db_id, and an injected emit
    When lease_connection leases a connection
    Then it returns the acquire result, emitting one exhausted pool event only when every connection is in use

  Scenario: open_pool opens N connections resiliently and emits created
    Given a db_id, an injected connect, a pure classify, an injected close, a size, a retry budget, a base delay, an injected sleep, and an injected emit
    When open_pool opens the pool
    Then it establishes each connection through connect_with_retry and emits one created pool event once the whole pool is open
    But if a connection cannot be established it closes the ones already opened, so none leak, and returns the establishment fault

  Scenario: close_pool closes the idle connections and emits closed
    Given a pool, a db_id, an injected close, and an injected emit
    When close_pool closes the pool
    Then it closes every idle connection through close and emits one closed pool event

  Scenario: should_retry decides whether a failed connection attempt is retried
    Given the attempt number, the retry budget, and the fault code
    When should_retry decides
    Then it retries while attempts remain and the fault is transient, but never retries a credential_rejected fault

  Scenario: connect_with_retry retries a transient failure and fails fast on a rejected credential
    Given a selector, an injected connect, a pure classify, a retry budget, a base delay, an injected sleep, and an injected emit
    When connect_with_retry establishes a connection
    Then it retries a transient failure with exponential backoff, emitting retry then ok(connection), and exhausting its attempts emits error and returns err(unresolvable_dsn)
    But a credential_rejected fault fails fast, emitting error and returning the fault without retrying

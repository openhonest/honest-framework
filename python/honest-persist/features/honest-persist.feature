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
    Then it produces the name and dialect type followed by the primary-key, not-null, unique, default, and foreign-key reference clauses the definition declares

  Scenario: _render_create_table renders a CREATE TABLE statement
    Given a create-table operation and a dialect
    When _render_create_table renders it
    Then it produces a CREATE TABLE statement with each column rendered as DDL, and an inline CONSTRAINT CHECK clause for each declared check constraint

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

  Scenario: _render_create_view renders a CREATE VIEW statement
    Given a create-view operation and a dialect
    When _render_create_view renders it
    Then it produces a CREATE VIEW statement whose body is the view's query

  Scenario: _render_drop_view renders a DROP VIEW statement
    Given a drop-view operation and a dialect
    When _render_drop_view renders it
    Then it produces a DROP VIEW statement for that view

  Scenario: matview_create_statements renders a materialized view for the dialect
    Given a create-matview operation and a dialect
    When matview_create_statements builds them
    Then it produces the native materialized view or the backfilled backing table, followed by any refresh triggers

  Scenario: matview_drop_statements renders a materialized view's drop for the dialect
    Given a drop-matview operation and a dialect
    When matview_drop_statements builds them
    Then it produces the refresh-trigger drops first, then the native materialized view or backing-table drop

  Scenario: refresh_materialized_view builds the refresh statements for the dialect
    Given a schema, a materialized view name, and a dialect
    When refresh_materialized_view builds the refresh
    Then it returns the native REFRESH on PostgreSQL and the in-place delete-and-reinsert on SQLite and Turso

  Scenario: _mv_refresh_events lists the trigger events of an auto-refresh materialized view
    Given a view name and its materialized definition
    When _mv_refresh_events reads it
    Then it returns an insert, update, and delete pair per source for a trigger or on_commit strategy, and none for manual

  Scenario: _mv_trigger_name names one refresh trigger
    Given a view name, a source table, and an event
    When _mv_trigger_name builds it
    Then it returns the deterministic refresh-trigger name

  Scenario: _mv_create_native renders a native CREATE MATERIALIZED VIEW
    Given a materialized view name and its query
    When _mv_create_native renders it
    Then it produces a CREATE MATERIALIZED VIEW statement

  Scenario: _mv_create_backing renders a backing-table CREATE TABLE AS
    Given a materialized view name and its query
    When _mv_create_backing renders it
    Then it produces a CREATE TABLE AS statement populating the backing table from the query

  Scenario: _mv_drop_native renders a DROP MATERIALIZED VIEW
    Given a materialized view name
    When _mv_drop_native renders it
    Then it produces a DROP MATERIALIZED VIEW statement

  Scenario: _mv_drop_backing renders a DROP TABLE for the backing table
    Given a materialized view name
    When _mv_drop_backing renders it
    Then it produces a DROP TABLE statement

  Scenario: _mv_refresh_native builds the native REFRESH statement
    Given a materialized view name and its query
    When _mv_refresh_native builds it
    Then it returns a single REFRESH MATERIALIZED VIEW statement

  Scenario: _mv_refresh_backing builds the in-place refresh statements
    Given a materialized view name and its query
    When _mv_refresh_backing builds it
    Then it returns a delete of the backing table followed by a reinsert of the query

  Scenario: _mv_triggers_native renders PostgreSQL refresh triggers
    Given a materialized view name and its definition
    When _mv_triggers_native builds them
    Then it returns a trigger function that calls REFRESH and a statement-level trigger on each source, or none for manual

  Scenario: _mv_triggers_backing renders SQLite refresh triggers
    Given a materialized view name and its definition
    When _mv_triggers_backing builds them
    Then it returns an inline-body trigger on each source that re-runs the in-place refresh

  Scenario: _mv_trigger_drops_native drops the PostgreSQL refresh triggers and function
    Given a materialized view name and its definition
    When _mv_trigger_drops_native builds them
    Then it returns a drop of each source trigger and of the refresh function, or none for manual

  Scenario: _mv_trigger_drops_backing drops the SQLite refresh triggers
    Given a materialized view name and its definition
    When _mv_trigger_drops_backing builds them
    Then it returns a drop of each source trigger

  Scenario: _render_create_trigger renders a CREATE TRIGGER statement
    Given a create-trigger operation and a dialect
    When _render_create_trigger renders it
    Then it produces a CREATE TRIGGER statement with the timing, events, table, optional condition, and body

  Scenario: _render_drop_trigger renders a DROP TRIGGER statement
    Given a drop-trigger operation and a dialect
    When _render_drop_trigger renders it
    Then it produces a DROP TRIGGER statement for that trigger

  Scenario: _render_function renders a function or procedure definition
    Given a function operation and whether to replace it
    When _render_function renders it
    Then it produces a CREATE or CREATE OR REPLACE statement with the kind, parameters, optional return type and language, and body

  Scenario: _render_create_function renders a CREATE FUNCTION statement
    Given a create-function operation and a dialect
    When _render_create_function renders it
    Then it produces a plain CREATE definition of the function or procedure

  Scenario: _render_replace_function renders a CREATE OR REPLACE statement
    Given a replace-function operation and a dialect
    When _render_replace_function renders it
    Then it produces a CREATE OR REPLACE definition of the function

  Scenario: _render_drop_function renders a DROP FUNCTION statement
    Given a drop-function operation and a dialect
    When _render_drop_function renders it
    Then it produces a DROP FUNCTION statement for that function

  Scenario: to_sql renders one operation to a DDL string for a dialect
    Given an operation and a dialect
    When to_sql dispatches on the operation's change name
    Then it returns the rendered DDL for that operation
    But an operation type with no renderer returns nothing

  Scenario: _dependent_views names the plain views that read a table
    Given a table and the schema's views
    When _dependent_views collects them
    Then it returns each plain view that reads the table, as name and query in order, and not a materialized view or a view on another table

  Scenario: reconstruction_sql renders the statements that rebuild a table
    Given a table, its target shape, the columns to carry over, a dialect, the dependent views, and an optional temporary name
    When reconstruction_sql renders the rebuild
    Then it drops the dependent views, creates a temporary table, copies the shared columns, drops the old, renames the temporary into place, recreates the target indexes, and recreates the dependent views
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

  Scenario: _column_from_pragma_row resolves one PRAGMA row to a column definition
    Given a PRAGMA table_info row
    When _column_from_pragma_row resolves it
    Then it returns the column's lowered type and nullability, with primary_key and default only when present

  Scenario: _columns_from_pragma resolves a table's PRAGMA rows to its columns
    Given the PRAGMA table_info rows of one table
    When _columns_from_pragma resolves them
    Then it returns a map of column name to column definition

  Scenario: _attach_foreign_keys attaches a table's foreign keys to its columns
    Given a table's columns and its PRAGMA foreign_key_list rows
    When _attach_foreign_keys attaches them
    Then each referencing column gains a table.column reference and any non-default cascade action, and a row whose column is absent is ignored

  Scenario: _index_from_pragma resolves one index from its PRAGMA rows
    Given an index's PRAGMA index_list unique flag and its PRAGMA index_info rows
    When _index_from_pragma resolves them
    Then it returns the index's columns in order, with unique only when the index is unique

  Scenario: _read_sqlite_indexes reads a table's explicit indexes
    Given a SQLite connection and a table name
    When _read_sqlite_indexes reads it
    Then it returns each explicitly-created index (PRAGMA index_list origin 'c') with its columns, and not the auto-index backing a unique or primary-key constraint

  Scenario: _pg_indexes groups the pg_catalog index rows into per-table indexes
    Given the pg_catalog index rows
    When _pg_indexes groups them
    Then it returns, per table, each index's columns in order with unique only when the index is unique

  Scenario: _read_object_registry reconstructs extended objects from the _hp_object registry
    Given a connection and a registry-existence query
    When _read_object_registry reads it
    Then it returns the views, triggers, procedures, and check constraints rebuilt exactly from the registry rows, or empty maps when the database has no registry table yet

  Scenario: _put_view reconstructs a view registry row
    Given the reconstructed objects, a view definition, and its name
    When _put_view places it
    Then the view is recorded under its name in the views map

  Scenario: _put_trigger reconstructs a trigger registry row
    Given the reconstructed objects, a trigger definition, and its name
    When _put_trigger places it
    Then the trigger is recorded under its name in the triggers map

  Scenario: _put_procedure reconstructs a procedure registry row
    Given the reconstructed objects, a procedure definition, and its name
    When _put_procedure places it
    Then the procedure is recorded under its name in the procedures map

  Scenario: _put_constraint reconstructs a check-constraint registry row onto its table
    Given the reconstructed objects and a constraint registry definition carrying its table
    When _put_constraint places it
    Then the constraint definition is recorded under the constraint's name within its table's constraints

  Scenario: _attach_constraints attaches reconstructed check constraints to their tables
    Given the inspected tables and the reconstructed constraints by table
    When _attach_constraints attaches them
    Then each table that has constraints gains them, and tables without any are unchanged

  Scenario: _schema_definition assembles the full SchemaDefinition from tables and registry objects
    Given the inspected tables and the reconstructed registry objects
    When _schema_definition assembles them
    Then it returns a definition whose tables carry their check constraints and whose views, triggers, and procedures are the top-level maps

  Scenario: _owned_tables names the stored tables that are honest-persist's own bookkeeping
    Given the reconstructed extended objects
    When _owned_tables reads them
    Then it returns the registry table and every materialized view's backing table, which round-trip as views rather than tables

  Scenario: _inspect_sqlite reads the live schema of a SQLite database
    Given a SQLite connection
    When _inspect_sqlite reads it
    Then it returns a full SchemaDefinition, reading user tables and columns from the catalog and the extended objects from the registry, and does not report the registry table itself

  Scenario: _pg_type resolves a PostgreSQL data type back to the abstract type
    Given a PostgreSQL information_schema data_type
    When _pg_type resolves it
    Then it returns the abstract type honest-persist emitted, resolving the canonical forms and passing every other type through

  Scenario: _pg_column resolves one schema-query row to a column definition
    Given a PostgreSQL schema-query row
    When _pg_column resolves it
    Then it returns the column's abstract type and nullability, with primary_key and default only when present

  Scenario: _pg_tables assembles the tables map from the flat schema query result
    Given the ordered rows of the PostgreSQL schema query and the owned table names
    When _pg_tables assembles them
    Then it groups the rows by table, skips honest-persist's own bookkeeping tables, and resolves each column

  Scenario: _inspect_postgresql reads the live schema of a PostgreSQL database
    Given a PostgreSQL connection
    When _inspect_postgresql reads it
    Then it returns a full SchemaDefinition, reading the registry and one schema query and handing the rows to the pure assembler, and does not report owned tables

  Scenario: inspect reads the live database schema for the dialect
    Given a connection and a dialect
    When inspect reads the schema
    Then it dispatches to the dialect's inspector and returns ok(schema), or err(unsupported_dialect) when none is registered

  Scenario: migrate runs the inspect-diff-apply workflow against a live database
    Given a target schema, a connection, and a dialect
    When migrate runs the workflow
    Then it inspects the current schema, diffs against the target, and applies, but refuses with a fault when inspection fails, the target is invalid, or the diff is ambiguous

  Scenario: _expand_range rewrites a range column to bound columns and a CHECK
    Given a table, a column name, and a range column declaration
    When _expand_range expands it
    Then it returns the lower and upper bound columns, each of the bound type and nullability, and a CHECK that the lower bound does not exceed the upper

  Scenario: _abstraction_kind names the abstraction a column declares
    Given a column declaration
    When _abstraction_kind reads it
    Then it returns enum when the column carries literal values, otherwise the declared type when it has an expander, otherwise nothing

  Scenario: _expand_table expands every abstraction column in one table
    Given a table name and a table definition
    When _expand_table expands it
    Then it passes plain columns through, rewrites abstraction columns to their relational form, and collects any tables an abstraction generates

  Scenario: _expand_tables expands every abstraction column in a bare tables map
    Given a bare tables map
    When _expand_tables expands it
    Then it rewrites each table's abstraction columns and adds the tables those abstractions generate

  Scenario: expand_schema expands every abstraction in a schema
    Given a bare schema or a full SchemaDefinition
    When expand_schema expands it
    Then it rewrites each abstraction and adds any generated tables, expanding a full definition in shape so its views, triggers, and procedures pass through, and leaving a schema with no abstractions unchanged in shape

  Scenario: range_overlaps builds an overlap condition over the bound columns
    Given a column and a query range
    When range_overlaps builds the condition
    Then it returns a WHERE condition true when the stored range and the query range each start at or before the other ends, with the bounds as named parameters

  Scenario: range_contains builds a containment condition over the bound columns
    Given a column and a point
    When range_contains builds the condition
    Then it returns a WHERE condition true when the point lies between the stored range's bounds, with the point as a named parameter

  Scenario: range_adjacent builds an adjacency condition over the bound columns
    Given a column and a query range
    When range_adjacent builds the condition
    Then it returns a WHERE condition true when the stored range touches the query range at a bound without overlapping, with the bounds as named parameters

  Scenario: _array_table names the junction table for an array column
    Given a table and an array column name
    When _array_table builds the name
    Then it returns the array junction table name for that column

  Scenario: _map_table names the junction table for a map column
    Given a table and a map column name
    When _map_table builds the name
    Then it returns the map junction table name for that column

  Scenario: _owner_type reads the base table's primary-key type
    Given a table definition
    When _owner_type reads it
    Then it returns the primary-key column's type, whether declared on a column or at the table level, falling back to integer when none is declared

  Scenario: _expand_array rewrites an array column to a junction table
    Given a table, a column name, and an array column declaration
    When _expand_array expands it
    Then it removes the base column and generates a junction table of owner_id, ordinal, and value

  Scenario: _expand_map rewrites a map column to a junction table
    Given a table, a column name, and a map column declaration
    When _expand_map expands it
    Then it removes the base column and generates a junction table of owner_id, key, and value

  Scenario: array_append builds an insert into an array junction table
    Given a table, an array column, an owner, an ordinal, and a value
    When array_append builds the query
    Then it returns an INSERT of the owner, ordinal, and value into the array junction table

  Scenario: array_set builds an update of an array junction row
    Given a table, an array column, an owner, an ordinal, and a value
    When array_set builds the query
    Then it returns an UPDATE of the value where the owner and ordinal match

  Scenario: array_remove builds a delete of an array junction row
    Given a table, an array column, an owner, and an ordinal
    When array_remove builds the query
    Then it returns a DELETE of the junction row where the owner and ordinal match

  Scenario: array_reindex closes the gap left by an array removal
    Given a table, an array column, an owner, and the removed ordinal
    When array_reindex builds the query
    Then it returns an UPDATE decrementing the ordinals above the removed position for that owner

  Scenario: map_put builds an insert into a map junction table
    Given a table, a map column, an owner, a key, and a value
    When map_put builds the query
    Then it returns an INSERT of the owner, key, and value into the map junction table

  Scenario: map_remove builds a delete of a map junction row
    Given a table, a map column, an owner, and a key
    When map_remove builds the query
    Then it returns a DELETE of the junction row where the owner and key match

  Scenario: _closure_table names the closure table for a hierarchy
    Given a table with a hierarchy column
    When _closure_table builds the name
    Then it returns the closure table name for that table

  Scenario: _expand_hierarchy rewrites a hierarchy column to a parent and closure table
    Given a table, a column name, and a hierarchy column declaration
    When _expand_hierarchy expands it
    Then it makes the column a nullable parent reference and generates a closure table of ancestor, descendant, and depth

  Scenario: closure_insert adds a node and its ancestor pairs to the closure
    Given a table, a node, and its parent
    When closure_insert builds the query
    Then it inserts the node's self-pair at depth zero and a pair from every ancestor of the parent, a root getting only its self-pair

  Scenario: closure_descendants reads a node's subtree in one query
    Given a table and a node
    When closure_descendants builds the query
    Then it returns a SELECT of every descendant of the node, the node included

  Scenario: closure_ancestors reads a node's ancestor chain in one query
    Given a table and a node
    When closure_ancestors builds the query
    Then it returns a SELECT of every ancestor of the node, the node included

  Scenario: closure_delete removes a node and its whole subtree
    Given a table and a node
    When closure_delete builds the query
    Then it returns a DELETE of every closure row whose descendant is in the node's subtree

  Scenario: closure_move relocates a subtree under a new parent
    Given a table, a node, and a new parent
    When closure_move builds the queries
    Then it returns two steps, detaching the subtree's cross-links to its old ancestors and reconnecting it under every ancestor of the new parent

  Scenario: _enum_table names the lookup table for an enum column
    Given a table and an enum column name
    When _enum_table builds the name
    Then it returns the enum lookup table name for that column

  Scenario: _expand_enum rewrites an enum column to a lookup table and foreign key
    Given a table, a column name, and a column carrying literal values
    When _expand_enum expands it
    Then it makes the column a text foreign key referencing the lookup's value, keeping its nullability and default, and generates a lookup table seeded with the allowed values

  Scenario: enum_seed_queries builds idempotent inserts for the lookup values
    Given an expanded schema and a dialect
    When enum_seed_queries builds the inserts
    Then it returns one insert-or-ignore per seed row in the dialect's ignore form, so re-running adds new values without disturbing existing rows

  Scenario: object_registry_queries brings the _hp_object registry in step with a schema
    Given a schema and a dialect
    When object_registry_queries builds the queries
    Then it ensures the registry table exists, clears it, and records each view, trigger, procedure, and check constraint as a row carrying its canonical definition as JSON

  Scenario: _constraint_registry_rows records a schema's check constraints for the registry
    Given the tables of a schema
    When _constraint_registry_rows collects them
    Then it returns a row per check constraint, keyed table.constraint and carrying its table, name, and definition, and skips any non-check constraint

  Scenario: table marks a Pydantic model as a named table
    Given a table name
    When table decorates a model
    Then it sets the model's table name and returns the model unchanged

  Scenario: _is_optional detects an Optional annotation
    Given a type annotation
    When _is_optional checks it
    Then it is true when the annotation is a union that includes None

  Scenario: _unwrap_optional returns the non-None member of an Optional
    Given a type annotation
    When _unwrap_optional unwraps it
    Then it returns the non-None member of an Optional, or the annotation unchanged

  Scenario: _is_literal detects a Literal annotation
    Given a type annotation
    When _is_literal checks it
    Then it is true when the annotation is a Literal

  Scenario: _literal_values reads the members of a Literal
    Given a Literal annotation
    When _literal_values reads it
    Then it returns the Literal's members as strings

  Scenario: _sql_type maps a Python annotation to an abstract SQL type
    Given a Python type annotation
    When _sql_type maps it
    Then it returns the abstract SQL type for the Python type or its name, defaulting to text when unknown

  Scenario: _quoted renders a string default as a SQL literal
    Given a string default value
    When _quoted renders it
    Then it returns the value as a quoted SQL string literal

  Scenario: _boolean renders a boolean default as a SQL literal
    Given a boolean default value
    When _boolean renders it
    Then it returns TRUE or FALSE

  Scenario: _numeric renders a numeric default as a SQL literal
    Given a numeric default value
    When _numeric renders it
    Then it returns the number as its string form

  Scenario: default_sql renders a Python default to its SQL literal
    Given a Python default value
    When default_sql renders it
    Then it dispatches on the value's type to its SQL literal, or returns nothing for a type with no literal form including a callable

  Scenario: _field_meta reads a Pydantic field's declared metadata
    Given a Pydantic field
    When _field_meta reads it
    Then it returns the json_schema_extra keys and the field's default when it has one

  Scenario: _column_from_field builds a column from a Pydantic field
    Given a field annotation and its field info
    When _column_from_field builds the column
    Then it sets the SQL type, nullability, Literal values, and the declared metadata and default

  Scenario: _table_extras reads a model's Meta inner class
    Given a model and its columns
    When _table_extras reads the Meta
    Then it adds a composite primary key clearing the per-column flags, and any indexes and constraints

  Scenario: _model_to_table converts a Pydantic model to a table
    Given a table-decorated Pydantic model
    When _model_to_table converts it
    Then it returns the table name and a table of columns from the model's public fields, with string annotations resolved

  Scenario: load_schema_from_models reads Pydantic models to a schema
    Given one or more table-decorated Pydantic models
    When load_schema_from_models reads them
    Then it returns a schema mapping each table name to its table definition, purely and with no I/O

  Scenario: cutover_phases lists the cutover phases in order
    Given a cutover
    When cutover_phases lists them
    Then it returns bulk transfer, mirror, promote, and detach in order

  Scenario: cutover_advance steps to the next cutover phase
    Given a cutover phase
    When cutover_advance steps it
    Then it returns the next phase, with detach terminal

  Scenario: cutover_read_target routes reads for a cutover phase
    Given a cutover phase
    When cutover_read_target routes reads
    Then it reads the source until promotion and the destination from promotion onward

  Scenario: cutover_plan orders tables by foreign key for bulk transfer
    Given a schema
    When cutover_plan orders it
    Then it returns the tables with each referenced table before its referrers, falling back to declared order on a cycle

  Scenario: copy_batch_query reads the next resumable batch
    Given a table, its primary key, the last-copied key, and a batch size
    When copy_batch_query builds it
    Then it returns a SELECT of the rows after the last key, ordered and limited, or from the start when there is no last key

  Scenario: bulk_copy_table copies a table between databases in batches
    Given a table, its columns, its primary key, a source, a destination, and a batch size
    When bulk_copy_table copies it
    Then it copies every row from the source to the destination in primary-key batches, resumable from the last key, and returns the count

  Scenario: mirror_write dual-writes a query to both databases
    Given a query, a source, and a destination
    When mirror_write writes it
    Then it runs the query against both databases and returns the source and destination results

  Scenario: _dj_type maps a Django field to an abstract SQL type
    Given a Django field
    When _dj_type maps it
    Then it returns the abstract SQL type for the field, a foreign key taking its target field's type, defaulting to text when unknown

  Scenario: _dj_choices reads the enum members of a Django field
    Given a Django field
    When _dj_choices reads its choices
    Then it returns the choice values as strings, or empty when the field has no choices

  Scenario: _dj_reference reads the target of a Django foreign key
    Given a Django foreign-key field
    When _dj_reference reads it
    Then it returns the related model's table and primary-key column as a reference

  Scenario: _dj_default reads a Django field's default as a SQL literal
    Given a Django field
    When _dj_default reads its default
    Then it returns the default rendered as a SQL literal, or nothing when there is no value default

  Scenario: _dj_column converts a Django field to a column
    Given a Django field
    When _dj_column converts it
    Then it sets the SQL type, nullability, primary key, uniqueness, enum choices, foreign-key reference, and default

  Scenario: load_schema_from_django reads Django models to a schema
    Given one or more Django models
    When load_schema_from_django reads them
    Then it returns a schema mapping each model's table name to its columns by db column name, purely and with no I/O

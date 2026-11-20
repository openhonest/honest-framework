Feature: honest-persist — generated, one scenario per function (97 total)

  Scenario: session_open opens a database for a caller and raises if it will not open
    Given target: str and shutdown: Shutdown and primary: str | NOTHING and token: str | NOTHING
    When session_open is called
    Then it opens a database for a caller and returns the Database, reading the engine off the target so nobody names one
    And it reads env:HONEST_PERSIST_CREW_SIZE and env:HONEST_PERSIST_CONNECTIONS, and it is awaited
    And it invokes session_connect
    And it is the one door that raises rather than returning a value: on could_not_open a server cannot start on a database that would not open
    And it is the one door a NoMatch does not come back through as a value: session_connect carries a NoMatch out to here and could_not_open is what the raise leaves on, carrying that record

  Scenario: query_ask answers a question or a declared write with one of three shapes
    Given db: Database and model: Model and written: Written
    When query_ask is called
    Then it takes a question or a declared write as the caller wrote it and answers Answer | Fault | NoMatch, and it is awaited, and it invokes query_answer
    And the Answer is the reply: rows, your own objects, a number, true or false, or NOTHING
    And the Fault is the driver's answer whose category decides whether to try again
    And the NoMatch is the library's answer to a question it could not read, carrying the caller's text, the key read out of it, and every key that table holds as data, and saying the database was not touched so nothing happened and there is nothing to undo

  Scenario: lifecycle_stop receives the shutdown signal and hands the shutdown off
    Given no parameters
    When lifecycle_stop is called
    Then it receives the platform's shutdown signal and hands the shutdown off, reading signal, awaited, invoking lifecycle_shut_down
    And it answers NOTHING when the drain finished or a Fault when it could not

  Scenario: clock_read asks the clock what time it is
    Given no parameters
    When clock_read is called
    Then it reads clock and returns the wall-clock time as a float

  Scenario: copy_on_disk answers whether a copy of the database is already there
    Given target: str
    When copy_on_disk is called
    Then it reads file:given and returns a bool, reading the path out of the target the caller wrote, because the calling program cannot know and the library looks

  Scenario: lifecycle_turn runs one drainer's turn and tells the three outcomes apart
    Given draining: Draining
    When lifecycle_turn is called
    Then it runs one drainer's turn, arriving because that drainer woke, and answers NOTHING | Fault | NoMatch, awaited, invoking lifecycle_catch_up
    And NOTHING means the turn did its work
    And a Fault means a driver was asked and answered badly
    And a NoMatch means no driver was asked because the engine word has no driver, carrying a turn that ran nothing and the list of engines there is a driver for, so the crew can stop this drainer and say which engine word has no driver

  Scenario: migration_plan says what a migration would change and changes nothing
    Given target: str
    When migration_plan is called
    Then it answers Plan | Fault, awaited, invoking migration_compare, reading the engine off the target so the caller names none
    And a matching database answers a plan with no operations, which is an answer and not a failure
    And it opens one connection and closes it, runs no statement against the schema, and on a replicated database opens no channel and neither pushes nor pulls
    And a failure comes back as a value and is never raised: the target naming no engine, the driver refusing a connection, an inspection question failing, a model claiming a name the library or an engine owns, a change that could be a rename or a drop and an add, and a plan that would destroy something no model asked to lose

  Scenario: schema_live answers with what the database holds right now
    Given target: str
    When schema_live is called
    Then it answers Schema | Fault, awaited, invoking schema_read_live, reading the engine off the target
    And the Schema is the current state and never the desired state because the models are not consulted, which is why it is a separate question from migration_plan
    And it opens one connection and closes it and writes nothing
    And a failure comes back as a value: the target naming no engine, the driver refusing a connection, or one of the six questions an engine answers about itself failing, with the already-open connection closed before the fault goes back

  Scenario: schema_declared answers with the models and views the host declared
    Given no parameters
    When schema_declared is called
    Then it answers Declared | Fault, invoking schema_say_declared, taking nothing because the host declared its models by importing its own modules and calling field in their class bodies
    And it is the one door of the three that touches no database and opens no connection, and it is not awaited
    And a failure comes back as a value when a model claims a name the library or an engine owns, named so the host can rename it

  Scenario: view_refreshes answers one schedule declaration per view asked to be refreshed
    Given db: Database
    When view_refreshes is called
    Then it answers list<ScheduleSpec> | Fault, invoking schema_say_refreshes, and runs none of them
    And it takes the open database because a schedule declaration carries work that writes rows through the handle session_open gave the host
    And it answers one ScheduleSpec per view whose freshness is refreshed when asked, and only those; a host that declared no such view gets an empty list, which is an answer and not a failure
    And it is not awaited and opens no connection
    And a failure comes back as a value: a view asking to be refreshed and naming no cadence, and a view whose name the library or an engine owns

  Scenario: session_connect works out the engine, connects, and builds the handle
    Given connecting: Connecting
    When session_connect is called
    Then it works out the engine, connects, and builds the Database handle everything downstream reads, answering Connecting | Fault | NoMatch, awaited, writing store:registered
    And it invokes engine_of, copy_on_disk, refuse_unusable_settings, permitted_connections, session_open_connection, crew_size, session_open_writer, session_open_channel, crew_make, crew_start, replicates, lifecycle_install_handler, lifecycle_register, channel_push, channel_pull, schema_read_declared, refuse_owned_names, schema_from_declared, schema_inspect, migration_needed, difference, name_what_is_ambiguous, order_operations, name_what_destroys, what_an_operation_carries, refuse_undeclared_loss, how_to_migrate, how_to_inspect, capability_of, mechanism_for, spell_operation, how_to_write, query_run_statement, query_run_together, session_close_connection and log_write
    And the NoMatch spell_operation answers travels out through this return as it stands, arriving while the migration is being spelled rather than run, stopping the open at the first attempt and handing up the list of words a view may name
    And it asks the disk whether a copy is already there so filling one is chosen rather than assumed
    And on a replicated database it pushes before it pulls and refuses the open if the push did not land, because the live schema read afterwards is the local copy

  Scenario: query_answer turns a caller's question into rows or a number
    Given asking: Answering
    When query_answer is called
    Then it turns a caller's question into rows or a number, waiting on the crew when it is a write, answering Answering | Fault | NoMatch, awaited
    And it invokes grammar_of, methods_of, asked_from_written, declaration_from_asked, refuse_undeclared_columns, refuse_some_columns_as_an_object, join_between, compile_statement, travels_together, query_run_statement, query_run_together, crew_deposit, crew_release_ticket, refusal_reaches_caller, answer_from_rows, answer_from_receipt and log_write
    And four cards can answer a NoMatch and this return carries each out as it stands: grammar_of when the text marks no spelling, asked_from_written when it calls a method no spelling gives, declaration_from_asked when it asks for a word that is not one of the eighteen, and compile_statement when the compiler or the comparison table has no row
    And all four are settled before a statement reaches a driver and before a write is deposited, so the question ran nothing: no row read, no write deposited, no ticket taken, nothing to undo

  Scenario: migration_compare works out what a migration would change and stops there
    Given planning: Planning
    When migration_compare is called
    Then it works out what a migration would change and stops, answering Planning | Fault, awaited
    And it invokes engine_of, session_open_connection, how_to_inspect, schema_inspect, schema_read_declared, refuse_owned_names, schema_from_declared, migration_needed, difference, name_what_is_ambiguous, order_operations, name_what_destroys, what_an_operation_carries, refuse_undeclared_loss and session_close_connection
    And it reads the engine off the target, borrows one connection, reads the live schema, reads the host's models, builds the wanted schema, compares, orders the operations, marks which lose data, refuses a loss no model asked for, and closes the connection on the way out and on every refusal
    And query_run_statement and query_run_together are not on this path, which is what makes the answer a plan rather than a migration
    And a plan that would destroy something no model asked to lose comes back as a fault rather than a plan, and it writes nothing to the log

  Scenario: schema_read_live asks one database what it holds and hands the answer back
    Given looking: Looking
    When schema_read_live is called
    Then it asks one database what it holds and hands the answer back, answering Looking | Fault, awaited
    And it invokes engine_of, session_open_connection, how_to_inspect, schema_inspect and session_close_connection
    And it reads the engine off the target, borrows one connection, asks the six questions, builds the schema, and closes the connection on the way out and on every refusal
    And nothing here reads a model, builds a wanted schema or works out a difference, so no model can refuse a reading of what is already there, and it writes nothing to the log

  Scenario: schema_say_declared reads what the host declared and refuses a name not the host's to claim
    Given no parameters
    When schema_say_declared is called
    Then it reads what the host declared, refuses a name that is not the host's to claim, and hands the models back, answering Declared | Fault
    And it invokes schema_read_declared and refuse_owned_names
    And it is the one orchestrator here that is not awaited because reading the host's own declarations waits for nothing
    And a model claiming a name the library or an engine owns is refused here rather than first at the next open, and it writes nothing to the log

  Scenario: schema_say_refreshes reads what the host declared and hands back what to schedule
    Given db: Database
    When schema_say_refreshes is called
    Then it reads what the host declared, refuses a name that is not the host's to claim, and hands back what to schedule, answering list<ScheduleSpec> | Fault
    And it invokes schema_read_declared, refuse_owned_names and refreshes_from_declared
    And it takes the open database because the handle is what makes the work callables possible, pairing each picked view with the work that rewrites its table through that handle and with what_to_do_after_a_refresh closed over the allowance the host wrote
    And it does not call what_to_do_after_a_refresh: it puts the rule into a schedule declaration and the scheduler calls it, on an outcome and a count that only exist once a refresh has run
    And it is not awaited, opens nothing, and writes nothing to the log

  Scenario: lifecycle_shut_down gets every local commit to the primary before the process dies
    Given shutting_down: ShuttingDown
    When lifecycle_shut_down is called
    Then it stops the crew and, for each replicating database, pushes until the cloud has it, backing off between pushes by next_wait and writing a progress line, then closes connections, answering ShuttingDown | Fault, awaited, reading store:registered
    And it invokes crew_stop, replicates, clock_read, channel_push, next_wait, progress_line, session_close_connection and log_write
    And it answers a NOTHING-bearing ShuttingDown on success or a Fault when a push could not land in time

  Scenario: lifecycle_catch_up spends a free turn running what the crew holds and drives the retry
    Given catching_up: CatchingUp
    When lifecycle_catch_up is called
    Then it waits for work, takes the next write in arrival order, asks how_to_retry for this engine's retry policy and how_to_write for how the engine wants the write wrapped, then drives the schedule, answering CatchingUp | Fault | NoMatch, awaited
    And it invokes crew_wait_for_work, writer_waiting, next_in_order, how_to_write, how_to_retry, crew_run_write, retry_schedule, clock_read, receipt_for, crew_post_receipt, replicates, channel_push, channel_pull and log_write
    And it performs the real write against crew_run_write, hands the outcome and the attempt number to retry_schedule, and reads the RetryStep back
    And on a run disposition it waits the step's delay and writes again
    And on a landed disposition it stops with the count touched
    And on a give_up_contention disposition it stops and builds a Fault categorised budget_spent, which is contention and never the caller's error
    And on a give_up_logical disposition it stops and surfaces the driver's Fault as it stands
    And crew_run_write answers a NoMatch when the engine word it was handed has no driver at all, settled before any write is put to a driver, so retry_schedule never sees it; the orchestrator propagates it through this return carrying the list of engines there is a driver for
    And the caller who deposited the write is parked on a waiter and reads a Receipt, so the record leaving this card goes up to this drainer's own door and not to that caller

  Scenario: session_open_connection asks the driver for a connection
    Given target: str and engine: Engine and connections: int
    When session_open_connection is called
    Then it asks the driver for a connection and answers Connection | Fault, awaited, reading and writing database

  Scenario: query_run_statement runs one statement on the connection it is handed and emits an event
    Given connection: Connection and engine: Engine and statement: Statement
    When query_run_statement is called
    Then it runs one statement on the connection it is handed and on no other, answering the rows a read returned or the count a write touched, as Rows | int | Fault, awaited, reading and writing database and writing honest-observe.emit
    And it is execute, the one I/O boundary instrumented: after every statement it emits hf.persist.query through the honest-observe.emit seam, carrying db_id and table, the operation, the row count, the duration in nanoseconds, a hash of the sql, and the request id, with the full sql only in development
    And the emission is best-effort: a failure to emit is logged to stderr and swallowed, never fails the query, and is a no-op when observe_queries is off

  Scenario: channel_pull brings down what the primary has and this copy does not
    Given channel: Channel
    When channel_pull is called
    Then it brings down what the primary has and this copy does not, answering NOTHING | Fault, awaited, reading database:given

  Scenario: channel_push sends local commits to the primary
    Given channel: Channel
    When channel_push is called
    Then it sends local commits to the primary, answering NOTHING | Fault, awaited, writing database:given
    And on a new channel it is the first call, so it proves the driver built its sync half, sends whatever is local, and on an empty copy brings the primary's whole schema down

  Scenario: session_close_connection closes one connection
    Given connection: Connection
    When session_close_connection is called
    Then it closes one connection, answering NOTHING | Fault, awaited, writing database
    And its callers are shutdown once it has pushed, and session_connect and migration_compare when a step refuses after connections were already opened

  Scenario: session_open_writer opens one drainer's connection held for its life
    Given target: str and engine: Engine
    When session_open_writer is called
    Then it opens one drainer's connection, held for its life, answering Connection | Fault, awaited, reading and writing database
    And a turso writer has MVCC turned on here, once, before it is handed back, running PRAGMA journal_mode = 'mvcc' and reading the cursor, so its BEGIN CONCURRENT is real; without it turso refuses BEGIN CONCURRENT outright; this is the write mode only, separate from master-to-slave replication; sqlite and postgresql are handed back as opened

  Scenario: session_open_channel opens the one line to the primary
    Given target: str and primary: str and token: str
    When session_open_channel is called
    Then it opens the one line to the primary, held for the life of the database, answering Channel | Fault, awaited, writing file:given
    And it makes the folder first because the driver takes a path and will not make the directory around it
    And it reaches no primary and proves nothing, so a dead primary is refused at channel_push and not here

  Scenario: crew_make builds a crew with nobody in it yet
    Given no parameters
    When crew_make is called
    Then it builds a Crew with nobody in it yet, and the doorbell a drainer sleeps on, writing process

  Scenario: crew_start hands one drainer per writer to the runtime
    Given db: Database and turn: Turn
    When crew_start is called
    Then it hands one drainer per writer to the runtime, each running the turn it was given, and keeps them so they can be stopped, answering Crew | Fault, awaited, writing process

  Scenario: crew_stop stops every drainer and waits for each to put its connection down
    Given crew: Crew
    When crew_stop is called
    Then it stops every drainer and waits for each to put its connection down, answering NOTHING | Fault, awaited, writing process

  Scenario: query_run_together runs several writes as one transaction
    Given writer: Connection and engine: Engine and statements: list<Statement> and transacting: Transacting
    When query_run_together is called
    Then it runs several writes as one transaction on one writer, the only rollback there is, answering int | Fault, awaited, writing database
    And it answers the rows affected or a Fault naming which write failed, rolling the whole transaction back

  Scenario: crew_run_write runs one write the way the engine needs it
    Given writer: Connection and engine: Engine and statement: Statement and transacting: Transacting
    When crew_run_write is called
    Then it runs one write the way the engine needs it, reading the words off the record it is handed, and answers a WriteOutcome: the rows it affected, or the driver's Fault when the write itself was asked and refused, answering WriteOutcome | NoMatch, awaited, writing database
    And an engine with no driver row answers a NoMatch before any write is put to a driver: table engines, looked_for that engine word, rows the three engines there is a driver for, reason no_row_for_the_key
    And it is the boundary that classifies a driver rejection into the conflict category using this engine's declared retryable set, so the schedule above it never reads driver text

  Scenario: crew_deposit hands a write to the crew and takes a ticket
    Given crew: Crew and statement: Statement
    When crew_deposit is called
    Then it hands a write to the crew, leaves a waiter, rings the doorbell and takes a ticket, answering Ticket | Fault, writing process and reading random

  Scenario: lifecycle_install_handler installs the signal handler
    Given no parameters
    When lifecycle_install_handler is called
    Then it installs the signal handler, chaining to whatever was already there, answering NOTHING | Fault, writing signal

  Scenario: crew_release_ticket awaits this caller's own waiter and takes its ticket off the crew
    Given crew: Crew and ticket: Ticket
    When crew_release_ticket is called
    Then it awaits this caller's own waiter and takes its ticket off the crew, answering Receipt | Fault, awaited, reading and writing process

  Scenario: crew_post_receipt hands a write's outcome to the waiter its caller is parked on
    Given crew: Crew and ticket: Ticket and receipt: Receipt
    When crew_post_receipt is called
    Then it hands a write's outcome to the waiter its caller is parked on, answering NOTHING | Fault, writing process and writing stderr

  Scenario: crew_wait_for_work sleeps until a write arrives, the crew stops, or the idle limit runs out
    Given draining: Draining
    When crew_wait_for_work is called
    Then it sleeps until a write arrives, the crew stops, or the idle limit runs out, answering NOTHING | Fault, awaited, reading and writing process

  Scenario: schema_read_declared asks the code which models and views it declares
    Given no parameters
    When schema_read_declared is called
    Then it asks the code which models and views it declares, answering Declared | Fault, reading process
    And it is where whatever field built enters, because a host calls that in its own class body and the answer sits in the model this reads

  Scenario: schema_inspect asks a database the six questions and builds what it holds
    Given connection: Connection and engine: Engine and inspecting: Inspecting
    When schema_inspect is called
    Then it asks a database the six questions and builds what it holds out of the answers, answering Schema | Fault, awaited, reading database

  Scenario: log_write writes a line an operator reads afterwards
    Given event: dict<str, Value>
    When log_write is called
    Then it writes a line an operator reads afterwards, answering NOTHING, writing stderr, and a failure never travels here

  Scenario: engine_of reads a target and names one of three engines
    Given target: str
    When engine_of is called
    Then it reads a target and names one of three engines, opening nothing: a bare path or a sqlite scheme is sqlite, a postgresql or postgres scheme is postgresql, a libsql scheme is turso, answering Engine | Fault
    And a scheme no engine ships a row for comes back as a refused Fault, carrying in detail the schemes that would have worked and the one that arrived

  Scenario: refuse_unusable_settings refuses a setting the engine cannot use
    Given engine: Engine and settings: dict<str, Value>
    When refuse_unusable_settings is called
    Then it refuses a setting the detected engine cannot use rather than ignoring it, answering dict<str, Value> | Fault

  Scenario: crew_size settles how many drainers run
    Given asked: int | NOTHING
    When crew_size is called
    Then it settles how many drainers run from what the deployment asked for, answering int | Fault, and NOTHING means the deployment named none and a default is settled here

  Scenario: permitted_connections settles how many connections this database opens
    Given asked: int | NOTHING
    When permitted_connections is called
    Then it settles how many connections this database opens from what the deployment asked for, answering int | Fault, and NOTHING means the deployment named none

  Scenario: compile_statement compiles a declaration into a statement for one engine
    Given declaration: Declaration and engine: Engine
    When compile_statement is called
    Then it compiles a declaration into a statement for one engine with values kept out, answering Statement | Fault | NoMatch, invoking how_to_compare
    And an asking word the renderers table holds no row for answers a NoMatch: table asking_words, looked_for that word, rows the eighteen words there are
    And a declaration short of what its word needs is still a Fault because the word was found and the parts beside it were missing, and the NoMatch how_to_compare answers travels out as it stands

  Scenario: refuse_undeclared_columns refuses a column no model declares
    Given model: Model and declaration: Declaration
    When refuse_undeclared_columns is called
    Then it refuses a column no model declares, naming the model and its columns, answering NOTHING | Fault

  Scenario: refuse_some_columns_as_an_object refuses asking for columns and your own model at once
    Given declaration: Declaration
    When refuse_some_columns_as_an_object is called
    Then it refuses a question that asks for some columns and for your own model at once, naming both words, answering NOTHING | Fault

  Scenario: travels_together answers whether these writes have to land together
    Given declaration: Declaration
    When travels_together is called
    Then it answers whether these writes have to land together, returning a bool

  Scenario: answer_from_receipt turns what the drainer did into the count a caller reads
    Given receipt: Receipt
    When answer_from_receipt is called
    Then it turns what the drainer did into the count a caller reads, answering Answer | Fault

  Scenario: answer_from_rows shapes driver rows the way the caller asked
    Given model: Model and rows: Rows and declaration: Declaration
    When answer_from_rows is called
    Then it shapes driver rows the way the caller asked: your own objects, plain rows, a number, true or false, or NOTHING, answering Answer | Fault

  Scenario: condition_from_narrowing turns what a caller wrote into the condition this library holds
    Given narrowing: AskedValue
    When condition_from_narrowing is called
    Then it turns what a caller wrote into the condition this library holds: a bare value means eq, or and not become any_of and none_of, answering Condition | Fault | NoMatch
    And a word inside a comparison the operators table holds no row for answers a NoMatch: table operators, looked_for every word in that comparison the table does not hold, rows the fifteen operators, detail the comparison as the caller wrote it
    And a comparison naming the wrong number of operators is still a Fault, refused on its count because nothing was looked up

  Scenario: methods_of gives the method names one way of writing uses
    Given grammar: Grammar
    When methods_of is called
    Then it returns the method names one way of writing uses, one row per way, as MethodNames

  Scenario: asked_from_written reads the writing and lifts the parts out
    Given written: Written and methods: MethodNames
    When asked_from_written is called
    Then it reads the writing and lifts the parts out: a model, then either a chain of calls or one call carrying named parts, with the method names telling which part is which, answering Asked | Fault | NoMatch
    And a method name no spelling gives any part of a question answers a NoMatch: table method_names, looked_for the method called, rows every method a question may carry, detail the question as typed
    And a part in the wrong shape is still a Fault because the method name was found and what it carried was wrong

  Scenario: declaration_from_asked turns the parts a reader lifted into the one declaration
    Given asked: Asked
    When declaration_from_asked is called
    Then it turns the parts a reader lifted into the one declaration all four ways of writing build, the only place a missing part is told no, answering Declaration | Fault | NoMatch, invoking condition_from_narrowing
    And an asking word no row holds answers a NoMatch: table asking_words, looked_for the word asked for, rows the eighteen words there are
    And a part the declaration cannot do without and nobody named is still a Fault, one per missing part, and the NoMatch condition_from_narrowing answers travels out as it stands

  Scenario: grammar_of reads which way of writing this is off the punctuation and shape
    Given written: Written
    When grammar_of is called
    Then it reads which way of writing this is off the punctuation and shape: .objects. is Django, .query. is SQLAlchemy, find_many( is Prisma, a bare method on the model is the library's own, answering Grammar | NoMatch
    And a question marking no spelling answers a NoMatch rather than a Fault: table grammars, rows the four spellings, reason no_key_to_look_up because nothing in the text named one and looked_for is empty, detail the question as typed

  Scenario: replicates answers whether this database replicates
    Given db: Database
    When replicates is called
    Then it answers whether this database replicates, derived from whether it holds a channel, returning a bool

  Scenario: next_wait gives the backoff delay before one retry attempt
    Given attempt: int
    When next_wait is called
    Then it gives the backoff delay in seconds before one retry attempt, worked out from the attempt number alone, zero before the first attempt and rising with each one, returning a float
    And it is invoked by retry_schedule for the conflict retry and by lifecycle_shut_down for its push backoff, and it holds no clock and no ticket, which is why it is pure

  Scenario: progress_line builds a shutdown log line
    Given db: Database and elapsed: float and done: bool
    When progress_line is called
    Then it builds a shutdown log line naming the database and the time elapsed, returning a dict<str, Value>

  Scenario: writer_waiting answers whether a writer is waiting for the connection
    Given crew: Crew
    When writer_waiting is called
    Then it answers whether a writer is waiting for the connection, returning a bool

  Scenario: next_in_order answers whose write is next in arrival order
    Given crew: Crew
    When next_in_order is called
    Then it answers whose write is next, in arrival order, returning Ticket | NOTHING, and taking it out is the boundary's work

  Scenario: worth_retrying answers whether a failure is worth another attempt
    Given fault: Fault
    When worth_retrying is called
    Then it answers whether a failure is worth another attempt, asked of its category, returning a bool
    And only a conflict is worth another attempt, because two writers wrote one row; a refused request, a spent budget and a killed process never improve on a retry

  Scenario: budget_spent answers whether the retry budget is gone
    Given attempts: int and budget: int
    When budget_spent is called
    Then it answers whether the retry budget is gone: true when the attempts made have reached the budget allowed, so a budget of three is spent at the third attempt, returning a bool

  Scenario: how_to_retry reads the per-engine retry table and hands back the conflict-retry declaration
    Given engine: Engine
    When how_to_retry is called
    Then it reads the per-engine retry table and hands back that engine's conflict-retry declaration, returning a RetryPolicy: which driver rejections mean contention on it, how many attempts the bound allows, and the contention level the bound was verified at
    And it exists so the retryable set and the bound are data an operator reads, never conditionals over driver message text scattered through the boundary

  Scenario: retry_schedule yields the next RetryStep for one write
    Given policy: RetryPolicy and outcome: WriteOutcome and attempt: int
    When retry_schedule is called
    Then it is the pure generator that owns the conflict-retry schedule for one write, driven by lifecycle_catch_up, returning one RetryStep, invoking worth_retrying, budget_spent and next_wait
    And a success, an int, yields the landed disposition
    And a Fault worth_retrying calls a conflict yields the run disposition again with the next attempt number and next_wait's backoff delay, unless budget_spent says the bound in policy is reached
    And when the bound is reached it yields the give_up_contention disposition and the failure is typed as contention rather than the caller's error
    And a Fault worth_retrying calls not a conflict, a constraint violation the caller owns, yields the give_up_logical disposition at once and is never retried
    And the first attempt is counted apart from the rest, from one, so first-attempt success is distinguishable from eventual success

  Scenario: refusal_reaches_caller decides whether a fault is raised or comes back as a receipt
    Given fault: Fault
    When refusal_reaches_caller is called
    Then it decides whether a fault is raised or comes back as a receipt, returning a bool

  Scenario: lifecycle_register adds a replicating database to the shutdown list
    Given db: Database
    When lifecycle_register is called
    Then it adds a replicating database to the list shutdown works through, answering NOTHING | Fault, and its answer is kept in the registered store, which is the list lifecycle_shut_down reads at exit

  Scenario: receipt_for builds the receipt a caller reads for its write
    Given ticket: Ticket and touched: int and failure: NOTHING | Fault and attempts: int
    When receipt_for is called
    Then it builds the receipt a caller reads for its write, carrying how many rows it touched and how many attempts it took, returning a Receipt

  Scenario: field says about one column what its annotation cannot
    Given renamed_from: str | NOTHING and references: Reference | NOTHING
    When field is called
    Then it says about one column what its annotation cannot: what it was renamed from, and where it points, returning a Field
    And it carries the pair in the field's extra and schema_read_declared reads it back, which is the only way Column.renamed_from and Column.references are ever anything but the named absence
    And neither argument has a default, because a column that forgot to say where it points and a column that points nowhere are different facts and only the host knows which

  Scenario: refuse_owned_names refuses a model that claims a name the library or an engine owns
    Given declared: Declared
    When refuse_owned_names is called
    Then it refuses a model that claims a name the library or an engine owns, answering NOTHING | Fault

  Scenario: schema_from_declared builds the target schema from what the code declares
    Given declared: Declared
    When schema_from_declared is called
    Then it builds the target schema from what the code declares and from nothing else: each model becomes a table named by its table, and the declared views carry over unchanged, answering Schema | Fault
    And an empty declaration builds an empty schema, which is an answer and not a failure

  Scenario: refuse_undeclared_loss stops a migration that would destroy something no model asked to lose
    Given plan: Plan and declared: Declared
    When refuse_undeclared_loss is called
    Then it stops a migration that would destroy something no model asked to lose, naming the table and what to declare to allow it, answering Plan | Fault

  Scenario: migration_needed answers whether the database still has to be brought up to the models
    Given live: Schema and target: Schema
    When migration_needed is called
    Then it answers whether the database still has to be brought up to the models: a live schema already matching the wanted one needs no migration, and any difference needs one, returning a bool

  Scenario: difference works out which operations turn the live schema into the target
    Given live: Schema and target: Schema
    When difference is called
    Then it works out which operations turn the live schema into the target, returning a list<Operation>

  Scenario: name_what_is_ambiguous stops on a change that could be a rename or a drop and an add
    Given operations: list<Operation> and declared: Declared
    When name_what_is_ambiguous is called
    Then it stops on a change that could be a rename or a drop and an add, naming the columns, answering list<Operation> | Fault

  Scenario: order_operations puts the operations in an order their dependencies allow
    Given operations: list<Operation>
    When order_operations is called
    Then it puts the operations in an order their dependencies allow, answering list<Operation> | Fault, and a cycle is a fault

  Scenario: name_what_destroys marks which operations lose data and names what each would lose
    Given operations: list<Operation>
    When name_what_destroys is called
    Then it marks which operations lose data and names what each would lose, returning a Plan

  Scenario: capability_of answers whether an engine does this natively and what builds it if not
    Given engine: Engine and feature: Feature
    When capability_of is called
    Then it answers whether an engine does this natively, and what builds it if not, returning a Capability

  Scenario: how_to_write reads the writers table and hands back what one engine needs around a write
    Given engine: Engine
    When how_to_write is called
    Then it reads the writers table and hands back what one engine needs around a write, returning a Transacting

  Scenario: how_to_migrate reads the facts table and hands back how far back a failed migration rolls
    Given engine: Engine
    When how_to_migrate is called
    Then it reads the facts table and hands back how far back a failed migration rolls, returning a MigrationMode

  Scenario: how_to_inspect reads the inspectors table and hands back the six questions
    Given engine: Engine
    When how_to_inspect is called
    Then it reads the inspectors table and hands back the six questions this engine answers about itself, returning an Inspecting
    And the sixth question asks which tables are materialized views, and each engine's row answers it its own way: PostgreSQL reads pg_matviews, SQLite and Turso read a table this package owns

  Scenario: how_to_spell reads the generators table and hands back how this engine writes this change
    Given kind: OperationKind and engine: Engine and replicating: bool
    When how_to_spell is called
    Then it reads the generators table and hands back how this engine writes this change, answering Spelling | Fault
    And whether the database replicates is part of the question, so a rename on a replicated database is spelled add, copy and drop, each committed on its own, because rename column and rename table run locally, report success and send nothing

  Scenario: what_an_operation_carries reads the operations table and hands back which fields this change fills
    Given kind: OperationKind
    When what_an_operation_carries is called
    Then it reads the operations table and hands back which fields this kind of change fills, returning a Carrying

  Scenario: how_to_compare reads the operators table and hands back how this engine writes this comparison
    Given operator: Operator and engine: Engine
    When how_to_compare is called
    Then it reads the operators table and hands back how this engine writes this comparison, answering Comparing | NoMatch
    And both ways this table can miss answer a NoMatch: an engine the package ships no row for is table engines, looked_for that engine word, rows the three engines; an operator the table holds no row for under this engine is table operators, looked_for that operator, rows the operators that do have a row; reason is no_row_for_the_key in both
    And it names no Fault at all because both its arguments are vocabularies, so no malformed value can arrive and there is nothing to refuse on shape, count or a missing part

  Scenario: spell_operation turns one schema change into the statements that carry it out
    Given operation: Operation and engine: Engine and replicating: bool
    When spell_operation is called
    Then it turns one schema change into the statements that carry it out, and a replicated database is handed a different spelling for the same change, answering list<Statement> | Fault | NoMatch, invoking how_to_spell and spell_view
    And the NoMatch spell_view answers travels out through this return as it stands, because a create_view is one of the changes this spells and spelling it means compiling the view's own declaration
    And a Fault on this card means the change itself cannot be carried out on this engine, a fact about the engine and not about anything the host wrote

  Scenario: join_between works out the join from the foreign key the model already declared
    Given near: Model and far: Model and condition: Condition
    When join_between is called
    Then it works out the join from the foreign key the model already declared, answering Join | Fault

  Scenario: spell_view writes the SELECT a declared view stands for
    Given view: View and engine: Engine
    When spell_view is called
    Then it writes the SELECT a declared view stands for, answering Statement | Fault | NoMatch, invoking compile_statement
    And a view holds a declaration and never a SELECT, so writing one out compiles it through the same card a caller's question goes through, and a view whose declaration names an asking word or an operator no row holds misses exactly the table a question would
    And the NoMatch compile_statement answers travels out through this return as it stands, carrying the word the host's own view named and every word that would have worked, as data

  Scenario: mechanism_for picks the mechanism that gives a materialized view the freshness asked for
    Given freshness: Freshness and engine: Engine and capability: Capability
    When mechanism_for is called
    Then it picks the mechanism that gives a materialized view the freshness asked for, answering list<Operation> | Fault

  Scenario: refreshes_from_declared picks out the views that asked to be refreshed on a clock
    Given declared: Declared
    When refreshes_from_declared is called
    Then it picks out the views that asked to be refreshed on a clock, keeping only the views whose freshness is refreshed when asked, answering list<View> | Fault
    And it refuses one that asks to be refreshed and names no cadence or no allowance, because a requirement with no period is a schedule nobody can run and a number invented here would be this package deciding how stale the host's data may be quietly
    And it answers views rather than schedule declarations, because a ScheduleSpec carries work that writes to a database and a pure function cannot hold an open connection; schema_say_refreshes turns each view into a schedule declaration

  Scenario: what_to_do_after_a_refresh reads one refresh's outcome and says whether to run again or stop
    Given written: int | Fault and attempt: Attempt and attempts_allowed: int
    When what_to_do_after_a_refresh is called
    Then it reads one refresh's outcome and says whether to run again or stop, the rule the scheduler calls and never reads into, returning a Disposition, invoking worth_retrying and budget_spent
    And it asks worth_retrying, which answers that only a conflict is worth another go, and budget_spent, which answers whether the tries are gone, rather than reading a category itself
    And attempt is handed in rather than counted here, which keeps it pure, and attempts_allowed is the host's number read off the view it declared
    And it never answers retry_after, because a refresh already has its cadence as the spacing, so a conflict worth another go is answered continue and tried again on the next tick, and attempt.overran changes nothing it answers

  Scenario: select builds a SELECT Query from names
    Given table: str and columns: list<str> | NOTHING and where: dict<str, Value> | NOTHING and order_by: list<str> | NOTHING and limit: int | NOTHING and offset: int | NOTHING and joins: list<QueryJoin> | NOTHING
    When select is called
    Then it builds a SELECT Query from names and does no I/O, returning a Query of parameterized SQL with every value carried in the Query's named params
    And table is the table read; columns is the column names wanted, or NOTHING for all of them, and a single * in the list is the all-columns wildcard; where is a map of column name to the Value it must equal, or NOTHING for no filter, and an empty map is also no filter
    And order_by is the column names to sort by, each optionally prefixed - for descending, or NOTHING; limit and offset are the row cap and the start offset, or NOTHING for neither; joins is the tables joined in, each a QueryJoin of a table name and a raw ON expression, or NOTHING
    And every optional part is an explicit NOTHING when absent, never a language default, so a caller that named nothing and a caller that chose nothing read the same

  Scenario: insert builds an INSERT Query
    Given table: str and values: dict<str, Value>
    When insert is called
    Then it builds an INSERT Query and does no I/O, returning a Query of parameterized SQL with every value carried in the Query's named params
    And table is the table written and values is the map of column name to the Value to write into it

  Scenario: update builds an UPDATE Query
    Given table: str and values: dict<str, Value> and where: dict<str, Value>
    When update is called
    Then it builds an UPDATE Query and does no I/O, returning a Query of parameterized SQL with every value carried in the Query's named params
    And table is the table written, values is the map of column name to the Value to set, and where is the map of column name to the Value a row must equal to be updated; an empty where map updates every row

  Scenario: delete builds a DELETE Query
    Given table: str and where: dict<str, Value>
    When delete is called
    Then it builds a DELETE Query and does no I/O, returning a Query of parameterized SQL with every value carried in the Query's named params
    And table is the table written and where is the map of column name to the Value a row must equal to be deleted; an empty where map deletes every row

  Scenario: raw builds a Query from SQL the caller wrote
    Given sql: str and params: dict<str, Value> | NOTHING
    When raw is called
    Then it builds a Query from SQL the caller wrote and does no I/O, returning a Query
    And sql is the raw SQL text and params is the named parameters to bind, or NOTHING when the SQL carries none
    And it is the one builder that carries no column names to check, the boundary raw draws between the checked and unchecked building of spec 7.3

  Scenario: execute runs a query on the caller's connection and answers the rows
    Given query: Query and conn: QueryConnection
    When execute is called
    Then it runs a query on the connection the caller handed in and answers the Rows it returned, awaited, reading and writing database
    And it awaits conn.execute(query.sql, query.params), which answers {rows, rowcount}, and hands back rows, each a plain dict and never a model instance: no ORM, no lazy loading, no identity map
    And it opens no connection and closes none; the connection is the caller's, resolved and supplied by persist's routing outside this layer
    And it does not catch: a driver error propagates to honest-type's catch_at_boundary, so this return carries rows and never a Fault

  Scenario: execute_one runs a query and answers its first row or NOTHING
    Given query: Query and conn: QueryConnection
    When execute_one is called
    Then it runs a query and answers its first row, or NOTHING when the query returned no rows, awaited, reading and writing database
    And it awaits conn.execute exactly as execute does and takes the first of rows; NOTHING is the host language's null for an empty result
    And it does not catch: a driver error propagates to honest-type's catch_at_boundary, so this return carries a row or NOTHING and never a Fault

  Scenario: execute_scalar runs a query and answers the first cell or NOTHING
    Given query: Query and conn: QueryConnection
    When execute_scalar is called
    Then it runs a query and answers the first column of its first row, or NOTHING when there were no rows, awaited, reading and writing database
    And the scalar is one cell, a Value, the same bound value a Row holds; NOTHING stands for no rows, which a cell that is itself null cannot be told apart from
    And it does not catch: a driver error propagates to honest-type's catch_at_boundary, so this return carries a Value or NOTHING and never a Fault

  Scenario: execute_many runs a write query and answers the rowcount
    Given query: Query and conn: QueryConnection
    When execute_many is called
    Then it runs a write query and answers the rowcount the driver reported, the number of rows affected, awaited, reading and writing database
    And it awaits conn.execute and hands back rowcount
    And it does not catch: a driver error propagates to honest-type's catch_at_boundary, so this return carries a count and never a Fault

  Scenario: transaction runs several writes as one all-or-nothing step
    Given writes: list<Query> and conn: QueryConnection
    When transaction is called
    Then it runs several writes as one all-or-nothing step on the connection the caller handed in, so either every write commits or none does, answering list<int> | Fault, awaited, writing database
    And it awaits conn.begin(), runs each write the way execute_many does on this one connection, collects each write's rows-affected count in arrival order, awaits conn.commit() and answers the list of counts
    And on a driver error it catches, awaits conn.rollback(), and answers a Fault instead of the list, the one sanctioned catch at this boundary, because a transaction cannot roll back without first seeing the failure
    And the success value is the bare list of per-write counts and the failure is the module's own bare-union Fault, not spec 7.5's ok/err envelope: the Fault's code is write_failed and its detail carries failed_at, the index of the write that failed, and message, the driver's text

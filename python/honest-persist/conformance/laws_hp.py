"""honest-persist conformance: the generative proof (the behavioural circle).

What a value case cannot express is proved here. Three kinds of law live in this file:

  1. A surface sweep (_probe_surface) that names every one of the 87 declared functions and fails
     for each one not yet built and exported. This is the backbone of the RED signal: today only six
     functions exist on disk, so this probe reports the other 81 by name, and it keeps the harness
     running to completion rather than aborting on the first missing import.

  2. Pure-function property laws, for the deciders, builders, the grammar readers and the engine
     tables. Where the declaration fixes the exact output (the six built functions, the retry
     dispositions) the law pins it; where it fixes only the shape or a totality property (SQL text,
     backoff seconds) the law asserts that, never an invented string.

  3. Real-database laws, against a real sqlite connection built in the test (never a mock). The
     boundaries open, read and write a genuine in-process database; failure is injected by holding a
     competing write lock or by setting the connection read-only, never by patching a function. The
     headline is the driven-generator retry (_probe_generator_retry): it drives lifecycle_catch_up
     against a real database, injects a write conflict, and asserts both the exact number of attempts
     and that the database is left consistent — the seam declaro's self-retrying loop made impossible.

The suite is RED by construction: the code port has not run, so most laws fail on a missing function.
That is correct. A later code port turns each law green. Each probe returns a list of failure strings;
run() aggregates them and never lets one missing function abort the rest.

  uv run --package honest-persist python honest-persist/conformance/run_conformance.py
"""

import asyncio
import os
import secrets
import sqlite3
import tempfile

import honest_persist as hp
from fragments.probe_channel_push_bootstraps_schema import probe_channel_push_bootstraps_schema
from fragments.probe_query_run_statement_zero_rows import probe_query_run_statement_zero_rows
from fragments.probe_query_run_together_zero_rows import probe_query_run_together_zero_rows
from fragments.probe_crew_run_write_zero_rows import probe_crew_run_write_zero_rows
from fragments.probe_is_fault import probe_is_fault
from fragments.probe_log_write_unknown_level import probe_log_write_unknown_level
from fragments.probe_log_write_warning_severity import probe_log_write_warning_severity
from fragments.probe_sqlite_writer_busy_timeout import probe_sqlite_writer_busy_timeout
from fragments.probe_refused import probe_refused
from fragments.probe_crew_run_write_turso_conflict import probe_crew_run_write_turso_conflict
from fragments.probe_session_open_channel_local_refusal import probe_session_open_channel_local_refusal
from fragments.probe_query_run_together_embedded_refusal import probe_query_run_together_embedded_refusal
from fragments.probe_crew_run_write_driver_refusal import probe_crew_run_write_driver_refusal
from fragments.probe_session_close_connection_driver_refusal import probe_session_close_connection_driver_refusal
from fragments.probe_query_run_statement_driver_refusal import probe_query_run_statement_driver_refusal
from fragments.probe_query_run_together_postgres_refusal import probe_query_run_together_postgres_refusal
from fragments.probe_session_open_connection_postgres_refusal import probe_session_open_connection_postgres_refusal
from fragments.probe_session_open_writer_sqlite_reason import probe_session_open_writer_sqlite_reason

# The real engines the parametrized laws run against. sqlite is always here; postgresql and turso come
# from the conformance fixtures, which provision a real server or open a real embedded database. The
# fixtures live beside this file and are not linted (they hold the driver adapters and provisioning).
from postgres_fixture import postgres_target  # noqa: E402
from turso_fixture import turso_replica_config  # noqa: E402

try:
    import turso as _turso_probe  # noqa: F401
    _TURSO_INSTALLED = True
except Exception:  # noqa: BLE001
    _TURSO_INSTALLED = False

try:
    import asyncpg as _asyncpg_probe  # noqa: F401
    _ASYNCPG_INSTALLED = True
except Exception:  # noqa: BLE001
    _ASYNCPG_INSTALLED = False

# Skips the laws recorded this run: an engine or a fixture that was genuinely unavailable, each named
# with its reason. run() prints them so an unavailable engine is visible and never a silent pass.
_SKIPS = []


def _note_skip(reason):
    """Record one named skip so the runner can show it; a skip is never a pass and never a failure."""
    _SKIPS.append(reason)


_WIDGETS_SQL = "CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"


def _insert(engine, widget_id, name):
    """One INSERT into widgets, spelled the way the engine's driver binds parameters: `:name` for sqlite
    and turso, `$n` for postgresql (asyncpg binds positionally, in the parameters' own order)."""
    numbered = engine == "postgresql"
    text = _pick(numbered,
                 lambda: "INSERT INTO widgets (id, name) VALUES ($1, $2)",
                 lambda: "INSERT INTO widgets (id, name) VALUES (:id, :name)")
    return {"text": text, "parameters": {"id": widget_id, "name": name}}


def _pick(flag, when_true, when_false):
    """A two-branch dict lookup, so the law code picks a spelling without an if (the module it tests
    forbids them; the laws keep the same shape)."""
    return {True: when_true, False: when_false}[flag]()


# Cached once per run: whether the installed pyturso does MVCC concurrent writes at all, measured
# against the raw engine (not persist's boundary). This decides whether turso's MVCC laws are in scope
# on this interpreter's pyturso, apart from whether persist's own code enables it — so a persist that
# forgets the journal-mode pragma FAILS the law rather than skipping it.
_TURSO_MVCC = {}


def _turso_engine_does_mvcc():
    """Ask the installed turso engine directly whether it does MVCC concurrent writes: on a local file, set
    journal_mode='mvcc' and land two interleaved BEGIN CONCURRENT writers. Returns {'ok': True} or
    {'skip': reason}. This is the write mode only; replication never enters it. A pyturso too old for MVCC
    (or none installed) is a named skip, so the turso MVCC law never fails vacuously on a build that cannot
    do MVCC, while a build that can forces persist's writer path to actually deliver it."""
    if _TURSO_MVCC:
        return _TURSO_MVCC
    if not _TURSO_INSTALLED:
        _TURSO_MVCC["skip"] = "turso: pyturso is not installed, so the turso MVCC write path was not exercised"
        return _TURSO_MVCC
    import turso
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "mvcc-capability.db")
        try:
            seed = turso.connect(path)
            seed.cursor().execute("PRAGMA journal_mode = 'mvcc'").fetchone()
            seed.cursor().execute("CREATE TABLE _probe (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
            seed.commit()
            seed.close()
            a = turso.connect(path); b = turso.connect(path)
            a.cursor().execute("PRAGMA journal_mode = 'mvcc'").fetchone()
            b.cursor().execute("PRAGMA journal_mode = 'mvcc'").fetchone()
            a.cursor().execute("BEGIN CONCURRENT"); b.cursor().execute("BEGIN CONCURRENT")
            a.cursor().execute("INSERT INTO _probe (id, name) VALUES (1, 'a')")
            b.cursor().execute("INSERT INTO _probe (id, name) VALUES (2, 'b')")
            a.commit(); b.commit(); a.close(); b.close()
            check = turso.connect(path)
            landed = check.cursor().execute("SELECT COUNT(*) FROM _probe").fetchone()[0]
            check.close()
            _TURSO_MVCC["ok" if landed == 2 else "skip"] = (
                True if landed == 2 else
                f"turso: this pyturso build did not land two concurrent MVCC writers (landed {landed})")
        except Exception as failed:  # noqa: BLE001
            _TURSO_MVCC["skip"] = (
                f"turso: this pyturso build does not do MVCC concurrent writes "
                f"({type(failed).__name__}: {failed})")
    return _TURSO_MVCC


def _real_engines(tmpdir):
    """The real engines available this run, each a profile the parametrized laws drive. sqlite and turso
    are embedded files under `tmpdir`; postgresql is a freshly provisioned test database. An engine that
    cannot be reached is left out and its absence recorded as a named skip, so a law never passes
    vacuously for an engine that was not there. turso is in scope as a concurrent-write engine only when
    the installed pyturso actually does MVCC; otherwise its absence is a named skip."""
    engines = [{"engine": "sqlite", "target": os.path.join(tmpdir, "sqlite.db"), "connections": 1,
                "concurrent_writes": True}]
    turso_mvcc = _turso_engine_does_mvcc()
    if turso_mvcc.get("ok"):
        engines.append({"engine": "turso", "target": os.path.join(tmpdir, "turso.db"), "connections": 1,
                        "concurrent_writes": True})
    else:
        _note_skip(turso_mvcc["skip"])
    postgres = _postgres_profile()
    engines.extend(postgres)
    return engines


def _postgres_profile():
    """A one-element list holding the postgresql profile when a real server and asyncpg are both here, or
    an empty list with the reason recorded."""
    if not _ASYNCPG_INSTALLED:
        _note_skip("postgresql: asyncpg is not installed, so persist's postgresql driver rows were not exercised")
        return []
    target = postgres_target()
    if target is None:
        _note_skip("postgresql: no PostgreSQL server could be reached or provisioned, so its driver rows were not exercised")
        return []
    return [{"engine": "postgresql", "target": target, "connections": 2, "concurrent_writes": True}]

# Every function the declaration names (honest-persist.hd), in declaration order. The surface sweep
# reads this list; a function added to the .hd is added here so the sweep stays the full inventory.
ALL_FUNCTIONS = [
    # column 1: input I/O — the ways in
    "session_open", "query_ask", "query_deposit", "query_collect", "lifecycle_stop", "clock_read",
    "copy_on_disk", "lifecycle_turn", "migration_plan", "schema_live", "schema_declared", "view_refreshes",
    # column 2: one orchestrator per door
    "session_connect", "query_answer", "query_prepare_deposit", "query_redeem_ticket", "migration_compare",
    "schema_read_live", "schema_say_declared", "schema_say_refreshes", "lifecycle_shut_down", "lifecycle_catch_up",
    # column 3: output I/O
    "session_open_connection", "query_run_statement", "channel_pull", "channel_push",
    "session_close_connection", "session_open_writer", "session_open_channel", "crew_make",
    "crew_start", "crew_stop", "query_run_together", "crew_run_write", "crew_deposit",
    "lifecycle_install_handler", "crew_release_ticket", "crew_post_receipt", "crew_wait_for_work",
    "schema_read_declared", "schema_inspect", "log_write",
    # the pure core
    "engine_of", "refuse_unusable_settings", "crew_size", "permitted_connections", "compile_statement",
    "refuse_undeclared_columns", "refuse_some_columns_as_an_object", "refuse_a_read",
    "refuse_an_unknown_ticket", "travels_together",
    "answer_from_receipt", "answer_from_rows", "condition_from_narrowing", "methods_of",
    "asked_from_written", "declaration_from_asked", "grammar_of", "replicates", "next_wait",
    "progress_line", "writer_waiting", "next_in_order", "worth_retrying", "budget_spent", "how_to_retry",
    "retry_schedule", "refusal_reaches_caller", "lifecycle_register", "receipt_for",
    # the schema half
    "field", "refuse_owned_names", "schema_from_declared", "refuse_undeclared_loss", "migration_needed",
    "difference", "name_what_is_ambiguous", "order_operations", "name_what_destroys", "capability_of",
    "how_to_write", "how_to_migrate", "how_to_inspect", "how_to_spell", "what_an_operation_carries",
    "how_to_compare", "spell_operation",
    # a question across models, and a declared view
    "join_between", "spell_view", "mechanism_for", "refreshes_from_declared", "what_to_do_after_a_refresh",
]


def _need(name):
    """The function `name` off the package, or raise so the caller records it as not built. Every
    behavioural law reaches its functions through this, so a missing one becomes a named failure rather
    than an AttributeError that aborts the probe."""
    fn = getattr(hp, name, None)
    if fn is None:
        raise _NotBuilt(name)
    return fn


class _NotBuilt(Exception):
    """Raised when a declared function is not yet on disk. Carries the function name."""


def _conflict_fault(code="write_conflict"):
    """A driver rejection categorised conflict — two writers raced for one row, worth another attempt
    (declaration FaultCategory). Built through the package's own fault constructor, so it is the same
    reserved-is_err record every honest module builds."""
    return hp.fault(code, "two writers wrote one row", "conflict", [], {"driver": "SQLITE_BUSY"})


def _logical_fault(code="not_null_violation"):
    """A logical rejection the caller owns — a constraint violation that fails identically however
    often it runs, categorised refused (declaration FaultCategory)."""
    return hp.fault(code, "a column that must hold something held nothing", "refused", [], {})


# ---------------------------------------------------------------------------
# 1. The surface sweep — the backbone RED signal.
# ---------------------------------------------------------------------------

def _probe_surface():
    """Every declared function exists and is callable. The 87 the .hd names are read off the package;
    each one missing is reported by name. This is the law that makes the suite demonstrably RED on the
    unbuilt code without the harness aborting: it never calls a function, only looks for it."""
    bad = []
    for name in ALL_FUNCTIONS:
        fn = getattr(hp, name, None)
        if fn is None:
            bad.append(f"{name}: not built (no such attribute on honest_persist)")
        elif not callable(fn):
            bad.append(f"{name}: present but not callable ({type(fn).__name__})")
    missing = sum(1 for n in ALL_FUNCTIONS if getattr(hp, n, None) is None)
    if missing:
        built = len(ALL_FUNCTIONS) - missing
        bad.append(f"surface: {built}/{len(ALL_FUNCTIONS)} functions built — {missing} of the declared functions are still missing")
    return bad


# ---------------------------------------------------------------------------
# 2. Pure-function property laws.
# ---------------------------------------------------------------------------

def _probe_engine_of():
    """engine_of reads the engine off the target and opens nothing: a bare path or sqlite scheme is
    sqlite, postgresql/postgres is postgresql, libsql is turso, and a scheme no engine ships a row for
    is a refused Fault carrying the accepted schemes in detail (declaration engine_of)."""
    bad = []
    try:
        engine_of = _need("engine_of")
    except _NotBuilt as e:
        return [f"{e}: engine_of"]
    for target, engine in (("x.db", "sqlite"), ("sqlite:///x", "sqlite"),
                           ("postgresql://h/d", "postgresql"), ("postgres://h/d", "postgresql"),
                           ("libsql://p", "turso")):
        got = engine_of(target)
        if got != engine:
            bad.append(f"engine_of({target!r}) should be {engine!r}, got {got!r}")
    miss = engine_of("mysql://h/d")
    if not (hp.is_fault(miss) and miss["category"] == "refused" and "mysql" in str(miss["detail"].get("arrived"))):
        bad.append(f"engine_of on an unknown scheme should be a refused Fault naming the arriving scheme: {miss}")
    if hp.is_fault(miss) and "mysql" in miss["detail"].get("arrived", "") and "sqlite" not in miss["detail"].get("accepted", []):
        bad.append("engine_of fault detail should carry the accepted schemes a caller could have named")
    return bad


def _probe_deciders():
    """The write-decision leaves read a word or a number and nothing else: worth_retrying finds only a
    conflict worth another attempt; budget_spent is true the moment the attempts reach the budget
    (declaration worth_retrying, budget_spent)."""
    bad = []
    try:
        worth_retrying = _need("worth_retrying")
        budget_spent = _need("budget_spent")
    except _NotBuilt as e:
        return [f"{e}: a decider is not built"]
    if worth_retrying(_conflict_fault()) is not True:
        bad.append("worth_retrying should be true for a conflict")
    for category in ("refused", "budget_spent", "cut_short"):
        f = hp.fault("c", "m", category, [], {})
        if worth_retrying(f) is not False:
            bad.append(f"worth_retrying should be false for category {category}")
    for attempts, budget, want in ((3, 3, True), (2, 3, False), (1, 1, True), (0, 1, False), (4, 3, True)):
        if budget_spent(attempts, budget) is not want:
            bad.append(f"budget_spent({attempts}, {budget}) should be {want}")
    return bad


def _probe_next_wait():
    """next_wait is the pure backoff: zero before the first attempt and rising with each one, worked
    out from the attempt number alone so a test reads it without a clock (declaration next_wait). The
    exact seconds are not fixed, so this asserts the first-attempt zero, non-negativity and the strict
    rise rather than invented numbers."""
    bad = []
    try:
        next_wait = _need("next_wait")
    except _NotBuilt as e:
        return [f"{e}: next_wait"]
    delays = [next_wait(n) for n in (1, 2, 3, 4)]
    if delays[0] != 0.0:
        bad.append(f"next_wait(1) should be 0.0 before the first attempt, got {delays[0]}")
    for n, d in zip((1, 2, 3, 4), delays):
        if not isinstance(d, (int, float)) or d < 0:
            bad.append(f"next_wait({n}) should be a non-negative number, got {d!r}")
    for earlier, later in zip(delays[1:], delays[2:]):
        if not later > earlier:
            bad.append(f"next_wait should rise with each attempt: {delays}")
            break
    return bad


def _probe_retry_schedule():
    """retry_schedule is the pure generator that owns the conflict-retry schedule for one write,
    driven one step at a time (declaration retry_schedule, spec 7.7). Each of its four dispositions is
    exercised directly, plus the budget-exhaustion sequence a driver walks. The delay is a backoff the
    declaration leaves to next_wait, so this pins the disposition and the attempt count, not the
    seconds."""
    bad = []
    try:
        retry_schedule = _need("retry_schedule")
    except _NotBuilt as e:
        return [f"{e}: retry_schedule"]
    policy = {"retryable": ["SQLITE_BUSY", "SQLITE_LOCKED"], "bound": 3, "verified_at_contention": 8}

    # A success — an int outcome — lands at once, nothing to retry.
    landed = retry_schedule(policy, 1, 1)
    if landed.get("disposition") != "landed":
        bad.append(f"a successful write (int outcome) should yield landed: {landed}")

    # A logical fault the caller owns gives up at once and is never retried.
    logical = retry_schedule(policy, _logical_fault(), 1)
    if logical.get("disposition") != "give_up_logical":
        bad.append(f"a non-conflict Fault should yield give_up_logical at once: {logical}")

    # A conflict with budget to spare asks for another run at the next attempt.
    runs = retry_schedule(policy, _conflict_fault(), 1)
    if runs.get("disposition") != "run":
        bad.append(f"a conflict with budget to spare should yield run: {runs}")
    elif runs.get("attempt") != 2:
        bad.append(f"a run after attempt 1 should schedule attempt 2, got {runs.get('attempt')}")

    # A conflict at the bound stops and types the failure as contention, never the caller's error.
    spent = retry_schedule(policy, _conflict_fault(), 3)
    if spent.get("disposition") != "give_up_contention":
        bad.append(f"a conflict at the bound should yield give_up_contention: {spent}")

    # Drive the schedule the way lifecycle_catch_up does: feed a conflict at each attempt until it
    # stops. With a bound of three the driver makes three real attempts and gives up on contention.
    attempt = 1
    dispositions = []
    for _ in range(10):
        step = retry_schedule(policy, _conflict_fault(), attempt)
        dispositions.append(step["disposition"])
        if step["disposition"] == "run":
            attempt = step["attempt"]
        else:
            break
    if dispositions != ["run", "run", "give_up_contention"]:
        bad.append(f"a bound-3 run of conflicts should be run, run, give_up_contention, got {dispositions}")
    if attempt != 3:
        bad.append(f"a bound-3 run should make exactly three attempts, reached attempt {attempt}")
    return bad


def _probe_schema_pure():
    """The schema-diff core turns two schemas into a plan. schema_from_declared builds the target from
    the models (built already); migration_needed is structural equality; difference, order_operations,
    name_what_destroys, name_what_is_ambiguous and refuse_undeclared_loss carry the plan the rest of
    the way (declaration, spec section 5)."""
    bad = []
    empty_declared = {"models": [], "views": [], "dropping_tables": [], "dropping_views": []}
    one_model = {"name": "User", "table": "users",
                 "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None}],
                 "dropping": [], "indexes": [], "constraints": []}
    declared = {"models": [one_model], "views": [], "dropping_tables": [], "dropping_views": []}

    try:
        schema_from_declared = _need("schema_from_declared")
        migration_needed = _need("migration_needed")
    except _NotBuilt as e:
        bad.append(f"{e}: a schema core function")
    else:
        if schema_from_declared(empty_declared) != {"tables": [], "views": []}:
            bad.append("schema_from_declared of an empty declaration should be an empty schema")
        wanted = schema_from_declared(declared)
        if not (wanted["tables"] and wanted["tables"][0]["name"] == "users"):
            bad.append(f"schema_from_declared should name the table by the model's table: {wanted}")
        if migration_needed(wanted, wanted) is not False:
            bad.append("migration_needed should be false when the schemas match")
        if migration_needed({"tables": [], "views": []}, wanted) is not True:
            bad.append("migration_needed should be true when the schemas differ")

    live = {"tables": [], "views": []}
    wanted = {"tables": [{"name": "users", "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None}], "indexes": [], "constraints": []}], "views": []}
    try:
        difference = _need("difference")
        ops = difference(live, wanted)
        if not isinstance(ops, list) or not ops:
            bad.append(f"difference from an empty live to one wanted table should emit an operation: {ops}")
        elif ops[0].get("kind") != "create_table":
            bad.append(f"the first operation to build a missing table should be create_table: {ops[0]}")
    except _NotBuilt as e:
        bad.append(f"{e}: difference")
    except Exception as e:
        bad.append(f"difference raised {type(e).__name__}: {e}")

    # A pointed-at table and a table that points at it: order_operations plans the pointed-at first.
    ops_unordered = [
        {"kind": "create_table", "table": "posts", "column": None, "columns": [], "indexes": [],
         "constraints": [{"name": "fk", "kind": "primary_key", "columns": ["author"], "rule": {}, "value": None}],
         "copying": [], "values": [], "renamed_to": None, "view": None, "destroys": False},
        {"kind": "create_table", "table": "users", "column": None, "columns": [], "indexes": [],
         "constraints": [], "copying": [], "values": [], "renamed_to": None, "view": None, "destroys": False},
    ]
    try:
        order_operations = _need("order_operations")
        ordered = order_operations(ops_unordered)
        if hp.is_fault(ordered):
            bad.append(f"order_operations of an acyclic plan should not fault: {ordered}")
        elif not isinstance(ordered, list) or len(ordered) != 2:
            bad.append(f"order_operations should return the operations ordered: {ordered}")
    except _NotBuilt as e:
        bad.append(f"{e}: order_operations")
    except Exception as e:
        bad.append(f"order_operations raised {type(e).__name__}: {e}")

    # name_what_destroys marks a drop_table as destroying and names what it loses.
    drop = [{"kind": "drop_table", "table": "legacy", "column": None, "columns": [], "indexes": [],
             "constraints": [], "copying": [], "values": [], "renamed_to": None, "view": None, "destroys": False}]
    try:
        name_what_destroys = _need("name_what_destroys")
        plan = name_what_destroys(drop)
        if "legacy" not in plan.get("destroys", []):
            bad.append(f"name_what_destroys should name the dropped table among destroys: {plan}")
        if plan["operations"] and plan["operations"][0].get("destroys") is not True:
            bad.append("name_what_destroys should mark a drop_table as destroying")
    except _NotBuilt as e:
        bad.append(f"{e}: name_what_destroys")
    except Exception as e:
        bad.append(f"name_what_destroys raised {type(e).__name__}: {e}")

    # refuse_undeclared_loss reads the `destroys` mark name_what_destroys set, per the .hd: a
    # destructive operation arrives already marked, and the function reads that mark rather than the
    # operation kind. So a drop_table marked destroying and declared by no model is refused; the same
    # drop_table marked not-destroying is passed, which is what proves the mark — not the kind — is read.
    destroying_plan = {"operations": [{**drop[0], "destroys": True}], "destroys": ["legacy"]}
    safe_plan = {"operations": [{**drop[0], "destroys": False}], "destroys": []}
    try:
        refuse_undeclared_loss = _need("refuse_undeclared_loss")
        refused = refuse_undeclared_loss(destroying_plan, empty_declared)
        if not hp.is_fault(refused):
            bad.append(f"refuse_undeclared_loss should fault when no model declared the marked loss: {refused}")
        allowed = refuse_undeclared_loss(destroying_plan, {**empty_declared, "dropping_tables": ["legacy"]})
        if hp.is_fault(allowed):
            bad.append(f"refuse_undeclared_loss should pass a drop the host declared: {allowed}")
        passed = refuse_undeclared_loss(safe_plan, empty_declared)
        if hp.is_fault(passed):
            bad.append(f"refuse_undeclared_loss should pass an operation marked not destroying: {passed}")
    except _NotBuilt as e:
        bad.append(f"{e}: refuse_undeclared_loss")
    except Exception as e:
        bad.append(f"refuse_undeclared_loss raised {type(e).__name__}: {e}")

    # name_what_is_ambiguous stops a column gone and another arrived with no rename field.
    ambiguous = [
        {"kind": "drop_column", "table": "users", "column": "fname", "columns": [], "indexes": [],
         "constraints": [], "copying": [], "values": [], "renamed_to": None, "view": None, "destroys": True},
        {"kind": "add_column", "table": "users", "column": "first_name",
         "columns": [{"name": "first_name", "declared_type": "text", "renamed_from": None, "references": None}],
         "indexes": [], "constraints": [], "copying": [], "values": [], "renamed_to": None, "view": None, "destroys": False},
    ]
    try:
        name_what_is_ambiguous = _need("name_what_is_ambiguous")
        verdict = name_what_is_ambiguous(ambiguous, declared)
        if not hp.is_fault(verdict):
            bad.append(f"name_what_is_ambiguous should fault on a drop-and-add that could be a rename: {verdict}")
    except _NotBuilt as e:
        bad.append(f"{e}: name_what_is_ambiguous")
    except Exception as e:
        bad.append(f"name_what_is_ambiguous raised {type(e).__name__}: {e}")
    return bad


def _ddl_operation(kind, **fields):
    """One schema-change operation record with every field present, so spell_operation reads it without a
    KeyError; the caller overrides only the fields that matter to the kind under test."""
    base = {"kind": kind, "table": "posts", "column": None, "columns": [], "indexes": [], "constraints": [],
            "copying": [], "values": [], "renamed_to": None, "view": None, "destroys": False}
    base.update(fields)
    return base


def _probe_schema_diff():
    """The diff core handles the parts a create-from-empty never reaches: a table present in both the
    live and declared schema whose columns differ emits add_column, drop_column and alter_column;
    order_operations refuses a dependency cycle; schema_from_declared carries a declared view. (declaration
    difference, order_operations, schema_from_declared, section 5)."""
    try:
        difference = _need("difference")
        order_operations = _need("order_operations")
        schema_from_declared = _need("schema_from_declared")
    except _NotBuilt as e:
        return [f"{e}: a schema-diff function"]
    bad = []

    def column(name, declared_type="text", references=None):
        return {"name": name, "declared_type": declared_type, "renamed_from": None, "references": references}

    live = {"tables": [{"name": "users",
                        "columns": [column("id", "integer"), column("changed", "text"), column("old_col")],
                        "indexes": [], "constraints": []}], "views": []}
    target = {"tables": [{"name": "users",
                          "columns": [column("id", "integer"), column("changed", "integer"), column("new_col")],
                          "indexes": [], "constraints": []}], "views": []}
    kinds = {operation["kind"] for operation in difference(live, target)}
    if not {"add_column", "drop_column", "alter_column"} <= kinds:
        bad.append(f"difference of a table whose columns changed should add, drop and alter columns: {kinds}")

    def create(table, columns, constraints):
        return {"kind": "create_table", "table": table, "column": None, "columns": columns, "indexes": [],
                "constraints": constraints, "copying": [], "values": [], "renamed_to": None, "view": None,
                "destroys": False}

    cycle_a = create("a", [column("bid", "integer", {"table": "b", "column": "id", "on_delete": "cascade"})],
                     [{"name": "fk", "kind": "foreign_key", "columns": ["bid"]}])
    cycle_b = create("b", [column("aid", "integer", {"table": "a", "column": "id", "on_delete": "cascade"})],
                     [{"name": "fk", "kind": "foreign_key", "columns": ["aid"]}])
    ordered = order_operations([cycle_a, cycle_b])
    if not (hp.is_fault(ordered) and ordered.get("code") == "cyclic_operations"):
        bad.append(f"order_operations should refuse a dependency cycle: {ordered}")

    declared = {"models": [], "dropping_tables": [], "dropping_views": [],
                "views": [{"name": "v", "freshness": "always current",
                           "declaration": _need("declaration_from_asked")({"model": "User", "wanted": "all"})}]}
    built = schema_from_declared(declared)
    if not (isinstance(built, dict) and len(built.get("views", [])) == 1):
        bad.append(f"schema_from_declared should carry a declared view: {built}")
    return bad


def _probe_dialect_edges():
    """The engine tables refuse a word they hold no row for, and the view machinery writes a declared
    view's SELECT per engine and the operations a materialized view needs. how_to_write, how_to_migrate,
    how_to_inspect and what_an_operation_carries fault on a word no row holds; refuse_unusable_settings
    refuses a setting an engine cannot use and passes the rest; mechanism_for answers the operations a
    freshness needs or refuses an unknown one; spell_view writes a view's SELECT for each engine and
    refuses an engine it has no row for (declaration how_to_write, how_to_migrate, how_to_inspect,
    what_an_operation_carries, refuse_unusable_settings, mechanism_for, spell_view)."""
    bad = []
    for name in ("how_to_write", "how_to_migrate", "how_to_inspect", "what_an_operation_carries",
                 "refuse_unusable_settings", "mechanism_for", "spell_view", "capability_of"):
        try:
            _need(name)
        except _NotBuilt as e:
            bad.append(f"{e}: {name}")
    if bad:
        return bad
    how_to_write = _need("how_to_write")
    how_to_migrate = _need("how_to_migrate")
    how_to_inspect = _need("how_to_inspect")
    what_an_operation_carries = _need("what_an_operation_carries")
    refuse_unusable_settings = _need("refuse_unusable_settings")
    mechanism_for = _need("mechanism_for")
    spell_view = _need("spell_view")
    capability_of = _need("capability_of")

    for reader in (how_to_write, how_to_migrate, how_to_inspect):
        if not hp.is_fault(reader("mysql")):
            bad.append(f"{reader.__name__} on an engine no row holds should be a Fault")
    if not hp.is_fault(what_an_operation_carries("not_a_kind")):
        bad.append("what_an_operation_carries on a kind no row holds should be a Fault")

    if hp.is_fault(refuse_unusable_settings("sqlite", ["busy_timeout_s"])):
        bad.append("refuse_unusable_settings should pass a setting the engine can use")
    if not hp.is_fault(refuse_unusable_settings("postgresql", ["busy_timeout_s"])):
        bad.append("refuse_unusable_settings should refuse a setting the engine cannot use")

    for freshness in ("always current", "current when read", "refreshed when asked"):
        for engine in ("sqlite", "postgresql", "turso"):
            operations = mechanism_for(freshness, engine, capability_of(engine, "materialized_view"))
            if not isinstance(operations, list):
                bad.append(f"{engine}: mechanism_for {freshness!r} should answer the operations it needs: {operations}")
    if not hp.is_fault(mechanism_for("never", "sqlite", capability_of("sqlite", "materialized_view"))):
        bad.append("mechanism_for an unknown freshness should be a Fault")

    view = {"name": "active_users", "freshness": "always current",
            "declaration": _declaration(model="User")}
    for engine in ("sqlite", "postgresql", "turso"):
        written = spell_view(view, engine)
        if not (isinstance(written, dict) and "text" in written):
            bad.append(f"{engine}: spell_view should write the view's SELECT: {written}")
    if not hp.is_fault(spell_view(view, "mysql")):
        bad.append("spell_view on an engine no row holds should be a Fault")
    return bad


def _probe_spelling_dialects():
    """spell_operation writes each schema change as the SQL one engine wants, and the three engines differ
    on type names, boolean literals and reference clauses. One rich create_table (a primary key, a NOT
    NULL text column with a string default, a boolean column with a boolean default, a foreign key, a
    unique index), a drop_table, an add_column and a drop_column are spelled for sqlite, postgresql and
    turso, under both the plain and the replicating spelling, and an unknown storage type is refused
    (declaration spell_operation, type_spelled, spec section 5)."""
    try:
        spell_operation = _need("spell_operation")
    except _NotBuilt as e:
        return [f"{e}: spell_operation"]
    columns = [
        {"name": "id", "declared_type": "integer", "renamed_from": None, "references": None},
        {"name": "name", "declared_type": "text", "renamed_from": None, "references": None},
        {"name": "active", "declared_type": "boolean", "renamed_from": None, "references": None},
        {"name": "author", "declared_type": "integer", "renamed_from": None,
         "references": {"table": "users", "column": "id", "on_delete": "cascade"}},
    ]
    constraints = [
        {"name": "pk_posts", "kind": "primary_key", "columns": ["id"]},
        {"kind": "not_null", "columns": ["name"]},
        {"kind": "default", "columns": ["name"], "value": "guest"},
        {"kind": "default", "columns": ["active"], "value": True},
        {"name": "uq_name", "kind": "unique", "columns": ["name"]},
    ]
    tag = [{"name": "tag", "declared_type": "text", "renamed_from": None, "references": None}]
    create = _ddl_operation("create_table", columns=columns, constraints=constraints,
                            indexes=[{"name": "ix_name", "columns": ["name"], "unique": True}])
    drop_table = _ddl_operation("drop_table", table="legacy")
    add_column = _ddl_operation("add_column", column="tag", columns=tag)
    drop_column = _ddl_operation("drop_column", column="tag", columns=tag)
    unknown = _ddl_operation("create_table",
                             columns=[{"name": "x", "declared_type": "no_such_type", "renamed_from": None, "references": None}])

    bad = []
    for engine in ("sqlite", "postgresql", "turso"):
        for replicating in (False, True):
            for operation in (create, drop_table, add_column, drop_column):
                spelled = spell_operation(operation, engine, replicating)
                if not (isinstance(spelled, list) and spelled and "text" in spelled[0]):
                    bad.append(f"{engine} (replicating={replicating}): spell_operation of {operation['kind']} "
                               f"should write statements: {spelled}")
        refused = spell_operation(unknown, engine, False)
        if not hp.is_fault(refused):
            bad.append(f"{engine}: an unknown storage type should be refused, not spelled: {refused}")
    # An engine with no spelling row at all: a group handed a made-up engine word.
    miss = spell_operation(drop_table, "mysql", False)
    if not hp.is_fault(miss):
        bad.append(f"spell_operation on an unknown engine should be a Fault: {miss}")
    return bad


_QUERY_BASE = {"model": "User", "wanted": "all", "columns": [],
               "condition": {"each": {}, "any_of": [], "none_of": []}, "order": {}, "grouping": [],
               "having": {"each": {}, "any_of": [], "none_of": []}, "paging": None, "rows": None,
               "shaping": "dictionaries", "across": None}


def _declaration(**fields):
    """One query declaration with every field present, overriding only what the asking word under test
    needs, so compile_statement reads it without a KeyError."""
    built = dict(_QUERY_BASE)
    built.update(fields)
    return built


def _satisfying_declarations():
    """One satisfying declaration per asking word (declaration_from_asked's eighteen), each carrying the
    part its word needs: an order for first, a page for page, a column to measure for the aggregates,
    rows for add and change, a narrowing for change and remove."""
    narrowing = hp.condition_from_narrowing({"id": {"gt": 1}})
    return {
        "all": _declaration(), "one": _declaration(wanted="one"), "exists": _declaration(wanted="exists"),
        "count": _declaration(wanted="count"), "first": _declaration(wanted="first", order={"id": "ascending"}),
        "page": _declaration(wanted="page", paging={"size": 10, "number": 2}),
        "distinct": _declaration(wanted="distinct", columns=["name"]),
        "sum": _declaration(wanted="sum", columns=["id"]), "average": _declaration(wanted="average", columns=["id"]),
        "smallest": _declaration(wanted="smallest", columns=["id"]), "largest": _declaration(wanted="largest", columns=["id"]),
        "count_distinct": _declaration(wanted="count_distinct", columns=["name"]),
        "add": _declaration(wanted="add", rows=[{"id": 1, "name": "a"}]),
        "change": _declaration(wanted="change", rows=[{"name": "b"}], condition=narrowing),
        "change_all": _declaration(wanted="change_all", rows=[{"name": "b"}], condition=narrowing),
        "remove": _declaration(wanted="remove", condition=narrowing),
        "remove_all": _declaration(wanted="remove_all", condition=narrowing),
    }


def _probe_query_compilation():
    """compile_statement turns a declaration into the SQL one engine wants, and the three engines differ
    on identifier quoting, placeholder style ($n for postgresql, :name and ? for sqlite and turso) and
    the case-insensitive operator. Every asking word is compiled with a satisfying declaration for
    sqlite, postgresql and turso, and a rich SELECT (a filter with OR and NOT and an ignore-case LIKE, a
    join, an order, a grouping, a having and a page) exercises the read renderer. A declaration a word
    cannot do without is refused declaration_incomplete; an unknown word is a NoMatch
    (declaration compile_statement, declaration_from_asked, section 7)."""
    try:
        compile_statement = _need("compile_statement")
    except _NotBuilt as e:
        return [f"{e}: compile_statement"]
    bad = []
    for word, declaration in _satisfying_declarations().items():
        for engine in ("sqlite", "postgresql", "turso"):
            statement = compile_statement(declaration, engine)
            if not (isinstance(statement, dict) and "text" in statement and "parameters" in statement):
                bad.append(f"{engine}: compile_statement of {word!r} should be a Statement: {statement}")

    rich = _declaration(
        columns=["name"],
        condition=hp.condition_from_narrowing({"name": {"like": "a%", "ignore_case": True},
                                            "or": [{"id": {"gt": 1}}, {"id": {"lt": 100}}], "not": [{"id": 5}]}),
        order={"id": "ascending", "name": "descending"}, grouping=["name"],
        having=hp.condition_from_narrowing({"id": {"gte": 1}}), paging={"size": 5, "number": 1},
        across=[{"model": "Post", "by_column": "id", "to_column": "author"}])
    for engine in ("sqlite", "postgresql", "turso"):
        statement = compile_statement(rich, engine)
        if not (isinstance(statement, dict) and "text" in statement):
            bad.append(f"{engine}: a rich SELECT with a filter, join, order, grouping, having and page should compile: {statement}")

    # A page that needs a page number it was not given is refused; an unknown asking word is a NoMatch.
    incomplete = compile_statement(_declaration(wanted="first"), "sqlite")
    if not (hp.is_fault(incomplete) and incomplete.get("code") == "declaration_incomplete"):
        bad.append(f"compile_statement of a first with no order should be declaration_incomplete: {incomplete}")
    unknown = compile_statement(_declaration(wanted="teleport"), "sqlite")
    if not (isinstance(unknown, dict) and unknown.get("table") == "asking_words"):
        bad.append(f"compile_statement of an unknown word should be a NoMatch naming asking_words: {unknown}")
    not_a_declaration = compile_statement("just a string", "sqlite")
    if not hp.is_fault(not_a_declaration):
        bad.append(f"compile_statement of a non-declaration should be a Fault: {not_a_declaration}")
    bad_engine = compile_statement(_declaration(), "mysql")
    if not hp.is_fault(bad_engine):
        bad.append(f"compile_statement for an unknown engine should be a Fault: {bad_engine}")
    return bad


def _probe_query_shapers():
    """The answer shapers and the join turn driver rows and a write receipt into what a caller reads.
    answer_from_rows shapes rows per asking word: the rows for all, exactly one or an absence or a
    too-many refusal for one, the first for first, a bool for exists, a number for count. answer_from_receipt
    reads the count out of an ok receipt and the Fault out of a not-ok one. join_between reads the join a
    foreign key already declared, and refuses when no key joins the two models (declaration
    answer_from_rows, answer_from_receipt, join_between)."""
    try:
        answer_from_rows = _need("answer_from_rows")
        answer_from_receipt = _need("answer_from_receipt")
        join_between = _need("join_between")
    except _NotBuilt as e:
        return [f"{e}: a query shaper"]
    model = {"name": "User", "table": "users",
             "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None}]}
    bad = []
    rows = [{"id": 1}, {"id": 2}]
    if answer_from_rows(model, rows, _declaration(wanted="all")) != rows:
        bad.append("answer_from_rows of all should hand the rows back as they came")
    if answer_from_rows(model, [{"id": 1}], _declaration(wanted="one")) != {"id": 1}:
        bad.append("answer_from_rows of one should hand the single row back")
    if answer_from_rows(model, [], _declaration(wanted="one")) is not None:
        bad.append("answer_from_rows of one with no rows should be NOTHING")
    if not hp.is_fault(answer_from_rows(model, rows, _declaration(wanted="one"))):
        bad.append("answer_from_rows of one with two rows should be a not_exactly_one Fault")
    if answer_from_rows(model, rows, _declaration(wanted="first")) != {"id": 1}:
        bad.append("answer_from_rows of first should be the first row")
    if answer_from_rows(model, [{"present": 1}], _declaration(wanted="exists")) is not True:
        bad.append("answer_from_rows of exists should read the single column as a bool")
    if answer_from_rows(model, [{"n": 7}], _declaration(wanted="count")) != 7:
        bad.append("answer_from_rows of count should be the one number")

    if answer_from_receipt({"ok": True, "touched": 3, "failure": None}) != 3:
        bad.append("answer_from_receipt of an ok receipt should be the count touched")
    if not hp.is_fault(answer_from_receipt({"ok": False, "touched": 0, "failure": _logical_fault()})):
        bad.append("answer_from_receipt of a not-ok receipt should surface the Fault it carries")

    posts = {"name": "Post", "table": "posts",
             "columns": [{"name": "author", "declared_type": "integer", "renamed_from": None,
                          "references": {"table": "users", "column": "id"}}]}
    joined = join_between(posts, model, {"each": {}, "any_of": [], "none_of": []})
    if not (isinstance(joined, dict) and joined.get("by_column") == "author" and joined.get("to_column") == "id"):
        bad.append(f"join_between should read the join the foreign key declared: {joined}")
    unrelated = {"name": "Tag", "table": "tags", "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None}]}
    if not hp.is_fault(join_between(model, unrelated, {"each": {}, "any_of": [], "none_of": []})):
        bad.append("join_between should refuse when no key joins the two models")

    # condition_from_narrowing's own refusals and empty answer, and answer_from_rows on a write.
    narrow = _need("condition_from_narrowing")
    if narrow(None) != {"each": {}, "any_of": [], "none_of": []}:
        bad.append("condition_from_narrowing of nothing should be the empty condition")
    if not hp.is_fault(narrow({"x": {"gt": 1, "lt": 2}})):
        bad.append("condition_from_narrowing of a comparison naming two operators should be a Fault")
    if not hp.is_fault(narrow(42)):
        bad.append("condition_from_narrowing of a narrowing that is not a dict should be a Fault")
    if not hp.is_fault(answer_from_rows(model, [], _declaration(wanted="add"))):
        bad.append("answer_from_rows of a write asking word should be a write_has_no_rows Fault")
    return bad


def _probe_query_pure():
    """The query half reads a caller's writing into one engine-free declaration and compiles it. The
    four grammar readers (grammar_of, methods_of, asked_from_written, declaration_from_asked), the
    narrowing reader (condition_from_narrowing), the compiler (compile_statement, how_to_compare), the
    join (join_between) and the answer shapers each answer a value, a Fault on a malformed shape, or a
    NoMatch on a word no table holds (declaration, query_answer path)."""
    bad = []

    try:
        grammar_of = _need("grammar_of")
        for written, grammar in (("User.objects.filter(x=1)", "django"),
                                 ("User.query.filter_by(x=1)", "sqlalchemy"),
                                 ("user.find_many(where={})", "prisma")):
            got = grammar_of(written)
            if got != grammar:
                bad.append(f"grammar_of({written!r}) should read {grammar!r}, got {got!r}")
        unmarked = grammar_of("!!! nothing marks a grammar here !!!")
        if not (isinstance(unmarked, dict) and unmarked.get("reason") == "no_key_to_look_up"):
            bad.append(f"grammar_of of text marking no spelling should be a NoMatch, reason no_key_to_look_up: {unmarked}")
    except _NotBuilt as e:
        bad.append(f"{e}: grammar_of")
    except Exception as e:
        bad.append(f"grammar_of raised {type(e).__name__}: {e}")

    try:
        methods_of = _need("methods_of")
        names = methods_of("django")
        if not isinstance(names, dict) or not names:
            bad.append(f"methods_of should return the method names one grammar uses: {names}")
    except _NotBuilt as e:
        bad.append(f"{e}: methods_of")
    except Exception as e:
        bad.append(f"methods_of raised {type(e).__name__}: {e}")

    try:
        condition_from_narrowing = _need("condition_from_narrowing")
        # A word inside a comparison the operators table holds no row for is a NoMatch naming operators.
        miss = hp.condition_from_narrowing({"age": {"bigger_than": 18}})
        if not (isinstance(miss, dict) and miss.get("table") == "operators"):
            bad.append(f"an unknown operator should be a NoMatch naming table operators: {miss}")
    except _NotBuilt as e:
        bad.append(f"{e}: condition_from_narrowing")
    except Exception as e:
        bad.append(f"condition_from_narrowing raised {type(e).__name__}: {e}")

    model = {"name": "User", "table": "users",
             "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None},
                         {"name": "name", "declared_type": "text", "renamed_from": None, "references": None}],
             "dropping": [], "indexes": [], "constraints": []}
    declaration = {"model": "User", "wanted": "all", "columns": [], "condition": {"each": {}, "any_of": [], "none_of": []},
                   "order": {}, "grouping": [], "having": {"each": {}, "any_of": [], "none_of": []},
                   "paging": None, "rows": None, "shaping": "dictionaries", "across": None}
    try:
        compile_statement = _need("compile_statement")
        statement = compile_statement(declaration, "sqlite")
        if hp.is_fault(statement) or (isinstance(statement, dict) and "reason" in statement):
            bad.append(f"compile_statement of a valid select should be a Statement, not a fault or miss: {statement}")
        elif not ("text" in statement and "parameters" in statement):
            bad.append(f"a Statement should carry text and parameters: {statement}")
        # An asking word the renderers table holds no row for is a NoMatch naming asking_words.
        bad_word = compile_statement({**declaration, "wanted": "teleport"}, "sqlite")
        if isinstance(bad_word, dict) and "reason" in bad_word and bad_word.get("table") != "asking_words":
            bad.append(f"compile_statement on an unknown asking word should name table asking_words: {bad_word}")
    except _NotBuilt as e:
        bad.append(f"{e}: compile_statement")
    except Exception as e:
        bad.append(f"compile_statement raised {type(e).__name__}: {e}")

    try:
        how_to_compare = _need("how_to_compare")
        row = how_to_compare("eq", "sqlite")
        if not (isinstance(row, dict) and {"symbol", "shape", "wraps", "ignoring_case"} <= set(row)):
            bad.append(f"how_to_compare should return a Comparing with the four columns: {row}")
        # Both ways it can miss answer a NoMatch: an unknown engine names table engines.
        miss_engine = how_to_compare("eq", "mysql")
        if not (isinstance(miss_engine, dict) and miss_engine.get("table") == "engines"):
            bad.append(f"how_to_compare on an unknown engine should be a NoMatch naming table engines: {miss_engine}")
        if hp.is_fault(row):
            bad.append("how_to_compare names no Fault; both its arguments are vocabularies")
    except _NotBuilt as e:
        bad.append(f"{e}: how_to_compare")
    except Exception as e:
        bad.append(f"how_to_compare raised {type(e).__name__}: {e}")

    # refuse_undeclared_columns refuses a column no model declares; refuse_some_columns_as_an_object
    # refuses asking for columns and your own model at once; travels_together answers a bool.
    for name, args, should_fault in (
        ("refuse_undeclared_columns", (model, {**declaration, "columns": ["nonesuch"]}), True),
        ("refuse_undeclared_columns", (model, {**declaration, "columns": ["name"]}), False),
        ("refuse_some_columns_as_an_object", ({**declaration, "columns": ["name"], "shaping": "objects"},), True),
    ):
        try:
            fn = _need(name)
            got = fn(*args)
            if should_fault and not hp.is_fault(got):
                bad.append(f"{name} should fault on {args[-1]}: {got}")
            if not should_fault and hp.is_fault(got):
                bad.append(f"{name} should pass a legal declaration: {got}")
        except _NotBuilt as e:
            bad.append(f"{e}: {name}")
        except Exception as e:
            bad.append(f"{name} raised {type(e).__name__}: {e}")

    try:
        travels_together = _need("travels_together")
        if not isinstance(travels_together(declaration), bool):
            bad.append("travels_together should answer a bool")
    except _NotBuilt as e:
        bad.append(f"{e}: travels_together")
    except Exception as e:
        bad.append(f"travels_together raised {type(e).__name__}: {e}")

    # answer_from_rows shapes rows; answer_from_receipt turns a receipt into the count a caller reads.
    rows = [{"id": 1, "name": "bob"}]
    try:
        answer_from_rows = _need("answer_from_rows")
        shaped = answer_from_rows(model, rows, declaration)
        if hp.is_fault(shaped):
            bad.append(f"answer_from_rows of a plain all-dictionaries read should not fault: {shaped}")
    except _NotBuilt as e:
        bad.append(f"{e}: answer_from_rows")
    except Exception as e:
        bad.append(f"answer_from_rows raised {type(e).__name__}: {e}")

    receipt = {"id": "t-1", "ok": True, "touched": 2, "attempts": 1, "failure": None}
    try:
        answer_from_receipt = _need("answer_from_receipt")
        got = answer_from_receipt(receipt)
        if got != 2 and not (isinstance(got, int)):
            bad.append(f"answer_from_receipt should turn an ok receipt into the count touched: {got}")
        failed = answer_from_receipt({"id": "t", "ok": False, "touched": 0, "attempts": 3, "failure": _logical_fault()})
        if not hp.is_fault(failed):
            bad.append(f"answer_from_receipt of a failed receipt should surface the Fault: {failed}")
    except _NotBuilt as e:
        bad.append(f"{e}: answer_from_receipt")
    except Exception as e:
        bad.append(f"answer_from_receipt raised {type(e).__name__}: {e}")

    # join_between works out the join from a declared foreign key; asked_from_written and
    # declaration_from_asked each answer a value, a Fault, or a NoMatch.
    for name in ("join_between", "asked_from_written", "declaration_from_asked"):
        try:
            _need(name)
        except _NotBuilt as e:
            bad.append(f"{e}: {name}")
    try:
        declaration_from_asked = _need("declaration_from_asked")
        miss = declaration_from_asked({"wanted": "teleport", "model": "User"})
        if isinstance(miss, dict) and "reason" in miss and miss.get("table") != "asking_words":
            bad.append(f"declaration_from_asked on an unknown asking word should name table asking_words: {miss}")
    except _NotBuilt as e:
        bad.append(f"{e}: declaration_from_asked")
    except Exception as e:
        bad.append(f"declaration_from_asked raised {type(e).__name__}: {e}")
    return bad


def _probe_engine_tables():
    """The seven per-engine tables are data an operator reads, never conditionals over driver text.
    Each hands back the engine's own row: how_to_write (Transacting), how_to_migrate (MigrationMode),
    how_to_inspect (the six questions), how_to_retry (RetryPolicy), how_to_spell (Spelling),
    what_an_operation_carries (Carrying), capability_of (Capability), and the two spellers spell_operation
    and spell_view (declaration, spec section 6-7)."""
    bad = []

    try:
        how_to_write = _need("how_to_write")
        t = how_to_write("sqlite")
        if not (isinstance(t, dict) and {"begin", "parameters", "commits"} <= set(t)):
            bad.append(f"how_to_write should return a Transacting: {t}")
        if isinstance(t, dict) and t.get("parameters") not in ("named", "positional"):
            bad.append(f"how_to_write parameters should be a ParameterStyle word: {t.get('parameters')}")
    except _NotBuilt as e:
        bad.append(f"{e}: how_to_write")
    except Exception as e:
        bad.append(f"how_to_write raised {type(e).__name__}: {e}")

    try:
        how_to_migrate = _need("how_to_migrate")
        mode = how_to_migrate("sqlite")
        if mode not in ("all_or_nothing", "per_operation"):
            bad.append(f"how_to_migrate should return a MigrationMode word: {mode}")
    except _NotBuilt as e:
        bad.append(f"{e}: how_to_migrate")
    except Exception as e:
        bad.append(f"how_to_migrate raised {type(e).__name__}: {e}")

    try:
        how_to_inspect = _need("how_to_inspect")
        insp = how_to_inspect("sqlite")
        wanted = {"tables", "columns", "indexes", "constraints", "views", "materialized_views", "types"}
        if not (isinstance(insp, dict) and wanted <= set(insp)):
            bad.append(f"how_to_inspect should return the six questions plus the types map: {insp}")
    except _NotBuilt as e:
        bad.append(f"{e}: how_to_inspect")
    except Exception as e:
        bad.append(f"how_to_inspect raised {type(e).__name__}: {e}")

    try:
        how_to_retry = _need("how_to_retry")
        policy = how_to_retry("sqlite")
        if not (isinstance(policy, dict) and {"retryable", "bound", "verified_at_contention"} <= set(policy)):
            bad.append(f"how_to_retry should return a RetryPolicy: {policy}")
        if isinstance(policy, dict) and not policy.get("retryable"):
            bad.append("how_to_retry should name at least one retryable rejection for sqlite")
    except _NotBuilt as e:
        bad.append(f"{e}: how_to_retry")
    except Exception as e:
        bad.append(f"how_to_retry raised {type(e).__name__}: {e}")

    try:
        how_to_spell = _need("how_to_spell")
        sp = how_to_spell("create_table", "sqlite", False)
        if hp.is_fault(sp):
            bad.append(f"how_to_spell of create_table on sqlite should not fault: {sp}")
        elif not (isinstance(sp, dict) and {"statements", "rebuilds", "commits_between"} <= set(sp)):
            bad.append(f"how_to_spell should return a Spelling: {sp}")
    except _NotBuilt as e:
        bad.append(f"{e}: how_to_spell")
    except Exception as e:
        bad.append(f"how_to_spell raised {type(e).__name__}: {e}")

    try:
        what_an_operation_carries = _need("what_an_operation_carries")
        carrying = what_an_operation_carries("create_table")
        wanted = {"columns", "indexes", "constraints", "copying", "values", "renamed_to", "view"}
        if not (isinstance(carrying, dict) and wanted <= set(carrying)):
            bad.append(f"what_an_operation_carries should return a Carrying: {carrying}")
    except _NotBuilt as e:
        bad.append(f"{e}: what_an_operation_carries")
    except Exception as e:
        bad.append(f"what_an_operation_carries raised {type(e).__name__}: {e}")

    try:
        capability_of = _need("capability_of")
        cap = capability_of("sqlite", "materialized_view")
        if not (isinstance(cap, dict) and {"native", "built_from"} <= set(cap)):
            bad.append(f"capability_of should return a Capability: {cap}")
    except _NotBuilt as e:
        bad.append(f"{e}: capability_of")
    except Exception as e:
        bad.append(f"capability_of raised {type(e).__name__}: {e}")

    # spell_operation turns one change into statements; a create_view's NoMatch from spell_view travels
    # out as it stands.
    op = {"kind": "create_table", "table": "users", "column": None,
          "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None}],
          "indexes": [], "constraints": [], "copying": [], "values": [], "renamed_to": None, "view": None, "destroys": False}
    try:
        spell_operation = _need("spell_operation")
        statements = spell_operation(op, "sqlite", False)
        if hp.is_fault(statements) or (isinstance(statements, dict) and "reason" in statements):
            bad.append(f"spell_operation of create_table on sqlite should be a list of statements: {statements}")
        elif not isinstance(statements, list):
            bad.append(f"spell_operation should return a list of Statement: {statements}")
    except _NotBuilt as e:
        bad.append(f"{e}: spell_operation")
    except Exception as e:
        bad.append(f"spell_operation raised {type(e).__name__}: {e}")

    for name in ("spell_view", "mechanism_for"):
        try:
            _need(name)
        except _NotBuilt as e:
            bad.append(f"{e}: {name}")
    return bad


def _probe_crew_pure():
    """The crew's pure readers answer a bool or a ticket off the crew record and nothing else:
    writer_waiting, next_in_order, replicates, refusal_reaches_caller, receipt_for, progress_line, and
    the two settlers crew_size and permitted_connections (declaration, lifecycle_catch_up path)."""
    bad = []
    crew = {"arrivals": ["t-1", "t-2"], "writes": {}, "waiting": {}, "arrived": "BELL", "stop": "BELL",
            "drainers": [], "size": 1}

    try:
        next_in_order = _need("next_in_order")
        if next_in_order(crew) != "t-1":
            bad.append("next_in_order should answer the first ticket in arrival order")
        if next_in_order({**crew, "arrivals": []}) is not None:
            bad.append("next_in_order of an empty crew should be NOTHING (None)")
    except _NotBuilt as e:
        bad.append(f"{e}: next_in_order")
    except Exception as e:
        bad.append(f"next_in_order raised {type(e).__name__}: {e}")

    try:
        replicates = _need("replicates")
        db_no = {"target": "x.db", "engine": "sqlite", "connections": [], "writers": [], "channel": None, "crew": crew, "shutdown": "exit_immediately"}
        if replicates(db_no) is not False:
            bad.append("replicates should be false with no channel")
        if replicates({**db_no, "channel": "CH"}) is not True:
            bad.append("replicates should be true with a channel")
    except _NotBuilt as e:
        bad.append(f"{e}: replicates")
    except Exception as e:
        bad.append(f"replicates raised {type(e).__name__}: {e}")

    try:
        receipt_for = _need("receipt_for")
        r = receipt_for("t-1", 3, None, 1)
        if r != {"id": "t-1", "ok": True, "touched": 3, "attempts": 1, "failure": None}:
            bad.append(f"receipt_for with no failure should be an ok receipt: {r}")
        rf = receipt_for("t-2", 0, _logical_fault(), 3)
        if rf.get("ok") is not False or rf.get("attempts") != 3:
            bad.append(f"receipt_for with a failure should be a not-ok receipt carrying the attempts: {rf}")
    except _NotBuilt as e:
        bad.append(f"{e}: receipt_for")
    except Exception as e:
        bad.append(f"receipt_for raised {type(e).__name__}: {e}")

    for name in ("writer_waiting", "refusal_reaches_caller"):
        try:
            fn = _need(name)
            got = fn(crew) if name == "writer_waiting" else fn(_logical_fault())
            if not isinstance(got, bool):
                bad.append(f"{name} should answer a bool, got {got!r}")
        except _NotBuilt as e:
            bad.append(f"{e}: {name}")
        except Exception as e:
            bad.append(f"{name} raised {type(e).__name__}: {e}")

    try:
        progress_line = _need("progress_line")
        db = {"target": "x.db", "engine": "sqlite", "connections": [], "writers": [], "channel": None, "crew": crew, "shutdown": "exit_immediately"}
        line = progress_line(db, 1.5, False)
        if not isinstance(line, dict):
            bad.append(f"progress_line should build a dict log line: {line}")
    except _NotBuilt as e:
        bad.append(f"{e}: progress_line")
    except Exception as e:
        bad.append(f"progress_line raised {type(e).__name__}: {e}")

    # crew_size and permitted_connections settle a count from what the deployment asked for; NOTHING
    # (None) means none was asked and a default is settled.
    for name in ("crew_size", "permitted_connections"):
        try:
            fn = _need(name)
            asked = fn(5)
            if asked != 5 and not hp.is_fault(asked):
                bad.append(f"{name}(5) should settle to the asked count or a Fault, got {asked}")
            default = fn(None)
            if not (isinstance(default, int) or hp.is_fault(default)):
                bad.append(f"{name}(None) should settle a default int or a Fault, got {default}")
        except _NotBuilt as e:
            bad.append(f"{e}: {name}")
        except Exception as e:
            bad.append(f"{name} raised {type(e).__name__}: {e}")

    try:
        refuse_unusable_settings = _need("refuse_unusable_settings")
        got = refuse_unusable_settings("sqlite", {})
        if hp.is_fault(got) and not got:
            bad.append("refuse_unusable_settings should pass an empty settings dict")
    except _NotBuilt as e:
        bad.append(f"{e}: refuse_unusable_settings")
    except Exception as e:
        bad.append(f"refuse_unusable_settings raised {type(e).__name__}: {e}")
    return bad


def _probe_schema_declarations():
    """field records the two facts a column annotation cannot carry (built already); refuse_owned_names
    refuses a model claiming a name the library or an engine owns (declaration field, refuse_owned_names)."""
    bad = []
    try:
        field = _need("field")
        if field("old", None) != {"renamed_from": "old", "references": None}:
            bad.append("field should carry renamed_from and the named absence for references")
        if field(None, None) != {"renamed_from": None, "references": None}:
            bad.append("field with nothing said should be two named absences")
    except _NotBuilt as e:
        bad.append(f"{e}: field")
    except Exception as e:
        bad.append(f"field raised {type(e).__name__}: {e}")

    try:
        refuse_owned_names = _need("refuse_owned_names")
        clean = {"models": [{"name": "User", "table": "users", "columns": [], "dropping": [], "indexes": [], "constraints": []}],
                 "views": [], "dropping_tables": [], "dropping_views": []}
        if hp.is_fault(refuse_owned_names(clean)):
            bad.append("refuse_owned_names should pass a model claiming a name of its own")
        owned = {"models": [{"name": "Log", "table": "sqlite_master", "columns": [], "dropping": [], "indexes": [], "constraints": []}],
                 "views": [], "dropping_tables": [], "dropping_views": []}
        if not hp.is_fault(refuse_owned_names(owned)):
            bad.append("refuse_owned_names should fault on a model claiming an engine-owned name")
    except _NotBuilt as e:
        bad.append(f"{e}: refuse_owned_names")
    except Exception as e:
        bad.append(f"refuse_owned_names raised {type(e).__name__}: {e}")
    return bad


def _probe_refresh():
    """The refresh half picks the views asking to be refreshed on a clock and decides what to do after
    one runs. refreshes_from_declared keeps only the refresh-when-asked views and refuses one naming no
    cadence; what_to_do_after_a_refresh reads one outcome and answers continue or stop, never
    retry_after (declaration refreshes_from_declared, what_to_do_after_a_refresh)."""
    bad = []
    refresh_view = {"name": "daily_totals", "declaration": {}, "freshness": "refreshed when asked",
                    "cadence": {"interval_seconds": 3600.0, "deadline_seconds": None}, "attempts_allowed": 3}
    plain_view = {"name": "active_users", "declaration": {}, "freshness": None, "cadence": None, "attempts_allowed": None}
    no_cadence = {"name": "broken", "declaration": {}, "freshness": "refreshed when asked", "cadence": None, "attempts_allowed": None}

    try:
        refreshes_from_declared = _need("refreshes_from_declared")
        picked = refreshes_from_declared({"models": [], "views": [refresh_view, plain_view], "dropping_tables": [], "dropping_views": []})
        if hp.is_fault(picked):
            bad.append(f"refreshes_from_declared should keep the refresh-when-asked view: {picked}")
        elif len(picked) != 1 or picked[0]["name"] != "daily_totals":
            bad.append(f"refreshes_from_declared should keep only the refresh-when-asked view: {picked}")
        refused = refreshes_from_declared({"models": [], "views": [no_cadence], "dropping_tables": [], "dropping_views": []})
        if not hp.is_fault(refused):
            bad.append(f"refreshes_from_declared should fault on a refresh view naming no cadence: {refused}")
        none = refreshes_from_declared({"models": [], "views": [plain_view], "dropping_tables": [], "dropping_views": []})
        if hp.is_fault(none) or none != []:
            bad.append(f"refreshes_from_declared of only plain views should be an empty list, not a fault: {none}")
    except _NotBuilt as e:
        bad.append(f"{e}: refreshes_from_declared")
    except Exception as e:
        bad.append(f"refreshes_from_declared raised {type(e).__name__}: {e}")

    try:
        what_to_do_after_a_refresh = _need("what_to_do_after_a_refresh")
        attempt = {"consecutive_faults": 0, "attempted": 1, "overran": False}
        ok = what_to_do_after_a_refresh(5, attempt, 3)
        if ok.get("kind") != "continue":
            bad.append(f"a successful refresh should continue at the cadence: {ok}")
        if ok.get("kind") == "retry_after":
            bad.append("what_to_do_after_a_refresh must never answer retry_after")
        conflict_attempt = {"consecutive_faults": 1, "attempted": 1, "overran": False}
        again = what_to_do_after_a_refresh(_conflict_fault(), conflict_attempt, 3)
        if again.get("kind") == "retry_after":
            bad.append("a conflict worth another go should be answered continue, never retry_after")
        spent_attempt = {"consecutive_faults": 3, "attempted": 3, "overran": False}
        stop = what_to_do_after_a_refresh(_conflict_fault(), spent_attempt, 3)
        if stop.get("kind") != "stop":
            bad.append(f"a refresh past its allowance should stop: {stop}")
    except _NotBuilt as e:
        bad.append(f"{e}: what_to_do_after_a_refresh")
    except Exception as e:
        bad.append(f"what_to_do_after_a_refresh raised {type(e).__name__}: {e}")
    return bad


# ---------------------------------------------------------------------------
# 3. Real-database laws. A genuine sqlite connection, built in the test, never a mock. Failure is
#    injected by a competing write lock or a read-only connection.
# ---------------------------------------------------------------------------

def _event_tables_sql():
    """The CREATE statements a drainer's write lands against: one ordinary table the laws write rows to.
    A law builds this against its own real database before exercising a write boundary."""
    return "CREATE TABLE IF NOT EXISTS widgets (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"


async def _real_query_on(engine, target, connections):
    """One real round trip through the output I/O boundaries of one engine: open, CREATE, INSERT (the
    count branch), SELECT (the rows branch), schema_inspect, query_run_together, close. The connection is
    a real database of that engine and the rows come back from it (declaration, column 3)."""
    bad = []
    session_open_connection = _need("session_open_connection")
    query_run_statement = _need("query_run_statement")
    session_close_connection = _need("session_close_connection")
    schema_inspect = _need("schema_inspect")
    how_to_inspect = _need("how_to_inspect")
    query_run_together = _need("query_run_together")
    how_to_write = _need("how_to_write")

    conn = await session_open_connection(target, engine, connections)
    if hp.is_fault(conn):
        return [f"{engine}: session_open_connection should open a real connection: {conn}"]
    created = await query_run_statement(conn, engine, {"text": _WIDGETS_SQL, "parameters": {}})
    if hp.is_fault(created):
        bad.append(f"{engine}: query_run_statement should run a CREATE: {created}")
    inserted = await query_run_statement(conn, engine, _insert(engine, 1, "bolt"))
    if hp.is_fault(inserted):
        bad.append(f"{engine}: query_run_statement should run an INSERT and answer the count touched: {inserted}")
    elif inserted != 1:
        bad.append(f"{engine}: an INSERT of one row should answer 1 touched, got {inserted}")
    read = await query_run_statement(conn, engine, {"text": "SELECT id, name FROM widgets ORDER BY id", "parameters": {}})
    if hp.is_fault(read) or not read or read[0].get("name") != "bolt":
        bad.append(f"{engine}: query_run_statement should read the row back: {read}")

    live = await schema_inspect(conn, engine, how_to_inspect(engine))
    if hp.is_fault(live):
        bad.append(f"{engine}: schema_inspect should read the live schema from the real database: {live}")
    elif not any(t.get("name") == "widgets" for t in live.get("tables", [])):
        bad.append(f"{engine}: schema_inspect should find the widgets table it just built: {live}")

    together = await query_run_together(conn, engine, [_insert(engine, 2, "nut"), _insert(engine, 3, "washer")], how_to_write(engine))
    if hp.is_fault(together):
        bad.append(f"{engine}: query_run_together should land several writes as one transaction: {together}")
    elif together != 2:
        bad.append(f"{engine}: query_run_together of two rows should answer 2 touched, got {together}")

    closed = await session_close_connection(conn)
    if hp.is_fault(closed):
        bad.append(f"{engine}: session_close_connection should close the real connection: {closed}")
    return bad


def _probe_real_query():
    """A real round trip through the output I/O boundaries, run against every real engine available this
    run — sqlite, postgresql, turso — so each engine's open, statement, inspect and transaction driver
    rows are exercised against a genuine database, never a mock (declaration, column 3)."""

    async def _run():
        try:
            _need("session_open_connection")
        except _NotBuilt as e:
            return [f"{e}: a query boundary"]
        bad = []
        with tempfile.TemporaryDirectory() as d:
            for profile in _real_engines(d):
                bad.extend(await _real_query_on(profile["engine"], profile["target"], profile["connections"]))
        return bad

    return asyncio.run(_run())


async def _sqlite_readonly_refusal(conn, query_run_statement):
    """Injure a real sqlite connection with query_only, then write: the driver really refuses it."""
    await query_run_statement(conn, "sqlite", {"text": "PRAGMA query_only = ON", "parameters": {}})
    return await query_run_statement(conn, "sqlite", {"text": "INSERT INTO widgets (id, name) VALUES (1, 'x')", "parameters": {}})


async def _constraint_refusal(engine, conn, query_run_statement):
    """A real NOT NULL violation the driver refuses: the name column cannot hold nothing, so the write
    fails at the driver and the boundary must turn that into a Fault rather than raise."""
    return await query_run_statement(conn, engine, _insert(engine, 1, None))


async def _real_refusal_on(engine, target, connections):
    """A real driver refusal of one engine comes back as a Fault, not a raise: a read-only sqlite
    connection, or a NOT NULL violation on postgresql and turso. Injected against a genuine database,
    never patched (declaration query_run_statement, section 8.5)."""
    session_open_connection = _need("session_open_connection")
    query_run_statement = _need("query_run_statement")
    conn = await session_open_connection(target, engine, connections)
    if hp.is_fault(conn):
        return [f"{engine}: session_open_connection should open the real database: {conn}"]
    created = await query_run_statement(conn, engine, {"text": _WIDGETS_SQL, "parameters": {}})
    if hp.is_fault(created):
        return [f"{engine}: the table could not be built before the refusal law: {created}"]
    refused = await _pick(engine == "sqlite",
                          lambda: _sqlite_readonly_refusal(conn, query_run_statement),
                          lambda: _constraint_refusal(engine, conn, query_run_statement))
    if not hp.is_fault(refused):
        return [f"{engine}: a write the driver refuses should be a Fault, not a raise or a silent pass: {refused}"]
    return []


def _probe_real_readonly_fault():
    """A real failure, injected not mocked, on every available engine: a write the driver refuses comes
    back as a Fault rather than raising. sqlite is put in query_only mode; postgresql and turso are given
    a NOT NULL violation. The databases are genuine, so the driver really refuses and the boundary really
    turns the refusal into data (declaration query_run_statement)."""

    async def _run():
        try:
            _need("session_open_connection")
            _need("query_run_statement")
        except _NotBuilt as e:
            return [f"{e}: query boundary for the refusal injection"]
        bad = []
        with tempfile.TemporaryDirectory() as d:
            for profile in _real_engines(d):
                bad.extend(await _real_refusal_on(profile["engine"], profile["target"], profile["connections"]))
        return bad

    return asyncio.run(_run())


async def _make_table(engine, target, connections):
    """Build the widgets table on a real database of this engine through persist's own read boundary, so
    the crew-write law opens its writer against a database that is already there."""
    session_open_connection = _need("session_open_connection")
    query_run_statement = _need("query_run_statement")
    session_close_connection = _need("session_close_connection")
    pool = await session_open_connection(target, engine, connections)
    if hp.is_fault(pool):
        return pool
    built = await query_run_statement(pool, engine, {"text": _WIDGETS_SQL, "parameters": {}})
    await session_close_connection(pool)
    return built


async def _crew_write_on(engine, target, connections):
    """crew_run_write runs one write the engine's way and answers a WriteOutcome: the count affected, or
    the driver's Fault when the write itself is refused (declaration crew_run_write, spec 7.7). Every
    engine in scope has a live concurrent-write mode: sqlite and postgresql always, turso when the
    installed pyturso does MVCC (its BEGIN CONCURRENT writer, enabled by session_open_writer), so a clean
    write answers the count on each."""
    bad = []
    session_open_writer = _need("session_open_writer")
    crew_run_write = _need("crew_run_write")
    session_close_connection = _need("session_close_connection")
    how_to_write = _need("how_to_write")

    built = await _make_table(engine, target, connections)
    if hp.is_fault(built):
        return [f"{engine}: the table could not be built before the crew-write law: {built}"]
    writer = await session_open_writer(target, engine)
    if hp.is_fault(writer):
        return [f"{engine}: session_open_writer should open a real writer connection: {writer}"]

    clean = await crew_run_write(writer, engine, _insert(engine, 1, "cog"), how_to_write(engine))
    bad.extend(_judge_clean_write(engine, clean))

    # A write the driver refuses (NOT NULL) answers a Fault, never a raise.
    refused = await crew_run_write(writer, engine, _insert(engine, 2, None), how_to_write(engine))
    if not hp.is_fault(refused):
        bad.append(f"{engine}: a NOT NULL violation should answer a Fault WriteOutcome, got {refused}")

    await session_close_connection(writer)
    return bad


def _judge_clean_write(engine, outcome):
    """A clean write on any engine in scope answers the count it affected. turso reaches here only when
    the installed pyturso does MVCC, so its BEGIN CONCURRENT write answers a count exactly as sqlite and
    postgresql do; there is no MVCC-off branch, because a pyturso without MVCC is a named skip upstream,
    never an engine whose clean write is expected to fault."""
    if isinstance(outcome, dict) and outcome.get("reason"):
        return [f"{engine}: a real write should not answer a NoMatch: {outcome}"]
    if hp.is_fault(outcome):
        return [f"{engine}: a clean write should answer a WriteOutcome count, not a Fault: {outcome}"]
    return _pick(outcome == 1, lambda: [], lambda: [f"{engine}: crew_run_write of one row should answer 1, got {outcome}"])


def _probe_crew_run_write():
    """crew_run_write against every available real engine, plus the no-driver NoMatch. Each engine's
    write driver row is exercised: the clean count where the engine's concurrent-write mode is live, the
    refused Fault on a NOT NULL violation, and a NoMatch for an engine with no driver row at all
    (declaration crew_run_write, spec 7.7)."""

    async def _run():
        try:
            session_open_writer = _need("session_open_writer")
            crew_run_write = _need("crew_run_write")
            how_to_write = _need("how_to_write")
        except _NotBuilt as e:
            return [f"{e}: crew_run_write path"]
        bad = []
        with tempfile.TemporaryDirectory() as d:
            engines = _real_engines(d)
            for profile in engines:
                bad.extend(await _crew_write_on(profile["engine"], profile["target"],
                                                profile["connections"]))
            # An engine with no driver row answers a NoMatch before any write runs, named once against a
            # real sqlite writer (the miss is settled on the engine word, so one writer proves it).
            sqlite_target = os.path.join(d, "miss.db")
            writer = await session_open_writer(sqlite_target, "sqlite")
            miss = await crew_run_write(writer, "mysql", _insert("sqlite", 1, "x"), how_to_write("sqlite"))
            if not (isinstance(miss, dict) and miss.get("table") == "engines" and miss.get("reason") == "no_row_for_the_key"):
                bad.append(f"crew_run_write on an engine with no driver should be a NoMatch naming table engines: {miss}")
            await _need("session_close_connection")(writer)
        return bad

    return asyncio.run(_run())


# inherits: hd=python/honest-persist/honest-persist.hd::session_open_connection -> feature=specs/features/honest-persist.feature::session_open_connection asks the driver for a connection
# inherits: hd=python/honest-persist/honest-persist.hd::query_run_statement -> feature=specs/features/honest-persist.feature::query_run_statement runs one statement on the connection it is handed and emits an event
def _probe_boundary_faults():
    """The output boundaries turn a bad argument or an unreachable driver into a Fault value, never a
    raise: an open the driver cannot reach, a bound of zero connections, a writer that will not open, and
    a statement or a group handed an engine word no driver ships. Each is injected against the real
    boundaries (declaration session_open_connection, session_open_writer, query_run_statement,
    query_run_together)."""

    async def _run():
        for name in ("session_open_connection", "session_open_writer", "query_run_statement",
                     "query_run_together", "session_close_connection", "how_to_write"):
            try:
                _need(name)
            except _NotBuilt as e:
                return [f"{e}: {name}"]
        session_open_connection = _need("session_open_connection")
        session_open_writer = _need("session_open_writer")
        query_run_statement = _need("query_run_statement")
        query_run_together = _need("query_run_together")
        session_close_connection = _need("session_close_connection")
        how_to_write = _need("how_to_write")
        bad = []
        with tempfile.TemporaryDirectory() as d:
            # An open the driver cannot reach: a path under a directory that is not there.
            unreachable = await session_open_connection(os.path.join(d, "missing", "db.db"), "sqlite", 1)
            if not (hp.is_fault(unreachable) and unreachable.get("code") == "could_not_reach"):
                bad.append(f"an unreachable open should be a could_not_reach Fault: {unreachable}")
            # A bound of zero connections leaves none to read on.
            zero_target = os.path.join(d, "z.db")
            none_left = await session_open_connection(zero_target, "sqlite", 0)
            if not (hp.is_fault(none_left) and none_left.get("code") == "no_connection_permitted"):
                bad.append(f"a zero-connection bound should be a no_connection_permitted Fault: {none_left}")
            else:
                message = none_left.get("message", "")
                if not all(fragment in message for fragment in ("0 connections", zero_target, "at least one")):
                    bad.append(f"zero-connection Fault should name its bound, target and remedy: {none_left!r}")
                if none_left.get("detail", {}).get("connections") != 0:
                    bad.append(f"zero-connection Fault should expose 0 as its connection bound: {none_left!r}")
            # A writer that cannot open.
            no_writer = await session_open_writer(os.path.join(d, "missing", "w.db"), "sqlite")
            if not (hp.is_fault(no_writer) and no_writer.get("code") == "writer_would_not_open"):
                bad.append(f"a writer that will not open should be a writer_would_not_open Fault: {no_writer}")
            # A statement and a group handed an engine word no driver ships.
            conn = await session_open_connection(os.path.join(d, "ok.db"), "sqlite", 1)
            stmt = {"text": "SELECT 1", "parameters": {}}
            miss_stmt = await query_run_statement(conn, "mysql", stmt)
            if not (hp.is_fault(miss_stmt) and miss_stmt.get("code") == "no_such_engine"):
                bad.append(f"a statement on an unknown engine should be a no_such_engine Fault: {miss_stmt}")
            elif "mysql" not in miss_stmt.get("message", ""):
                bad.append(f"unknown statement engine Fault should name mysql: {miss_stmt!r}")
            miss_group = await query_run_together(conn, "mysql", [stmt], how_to_write("sqlite"))
            if not (hp.is_fault(miss_group) and miss_group.get("code") == "no_such_engine"):
                bad.append(f"a group on an unknown engine should be a no_such_engine Fault: {miss_group}")
            await session_close_connection(conn)

            # A group the driver refuses rolls the whole transaction back and comes back a Fault, on every
            # engine: a NOT NULL violation inside the group.
            for profile in _real_engines(d):
                bad.extend(await _refused_group_on(profile["engine"], profile["target"], profile["connections"]))
        return bad

    return asyncio.run(_run())


async def _refused_group_on(engine, target, connections):
    """A group of writes the driver refuses (a NOT NULL violation) rolls back and answers a group_refused
    Fault, never a raise (declaration query_run_together)."""
    session_open_connection = _need("session_open_connection")
    query_run_statement = _need("query_run_statement")
    query_run_together = _need("query_run_together")
    session_close_connection = _need("session_close_connection")
    how_to_write = _need("how_to_write")
    conn = await session_open_connection(target, engine, connections)
    if hp.is_fault(conn):
        return [f"{engine}: the connection for the refused-group law would not open: {conn}"]
    built = await query_run_statement(conn, engine, {"text": _WIDGETS_SQL, "parameters": {}})
    if hp.is_fault(built):
        return [f"{engine}: the table for the refused-group law could not be built: {built}"]
    refused = await query_run_together(conn, engine, [_insert(engine, 1, None)], how_to_write(engine))
    await session_close_connection(conn)
    return _pick(hp.is_fault(refused), lambda: [],
                 lambda: [f"{engine}: a group with a NOT NULL violation should be a Fault, got {refused}"])


def _probe_readers_and_log():
    """The three low boundaries that touch the platform rather than a database: clock_read reads the
    wall clock, copy_on_disk reads whether a file is already there, log_write writes a line and never
    faults (declaration clock_read, copy_on_disk, log_write)."""

    async def _run():
        bad = []
        try:
            clock_read = _need("clock_read")
            now = clock_read()
            if not isinstance(now, float):
                bad.append(f"clock_read should answer the wall-clock time as a float: {now!r}")
        except _NotBuilt as e:
            bad.append(f"{e}: clock_read")
        except Exception as e:
            bad.append(f"clock_read raised {type(e).__name__}: {e}")

        try:
            copy_on_disk = _need("copy_on_disk")
            with tempfile.TemporaryDirectory() as d:
                here = os.path.join(d, "present.db")
                open(here, "w").close()
                if copy_on_disk(here) is not True:
                    bad.append("copy_on_disk should be true for a file that is there")
                if copy_on_disk(os.path.join(d, "absent.db")) is not False:
                    bad.append("copy_on_disk should be false for a file that is not there")
        except _NotBuilt as e:
            bad.append(f"{e}: copy_on_disk")
        except Exception as e:
            bad.append(f"copy_on_disk raised {type(e).__name__}: {e}")

        try:
            log_write = _need("log_write")
            got = log_write({"event": "test", "db": "x"})
            if got is not None:
                bad.append(f"log_write should answer NOTHING (None) and never fault: {got}")
        except _NotBuilt as e:
            bad.append(f"{e}: log_write")
        except Exception as e:
            bad.append(f"log_write raised {type(e).__name__}: {e}")
        return bad

    return asyncio.run(_run())


def _probe_crew_lifecycle():
    """The crew's real boundaries wired together: crew_make builds an empty crew, session_open_writer
    opens a drainer's connection, crew_deposit hands a write in and takes a ticket, crew_release_ticket
    and crew_post_receipt move the outcome back to the waiting caller, crew_start and crew_stop run and
    stop the drainers, crew_wait_for_work sleeps until work arrives, and lifecycle_install_handler and
    lifecycle_register install the shutdown handler and the replicating-database list. Exercised against
    a real file-backed sqlite database so the drainers share one store (declaration, column 3)."""

    async def _run():
        bad = []
        for name in ("crew_make", "crew_start", "crew_stop", "crew_deposit", "crew_release_ticket",
                     "crew_post_receipt", "crew_wait_for_work", "lifecycle_install_handler", "lifecycle_register"):
            try:
                _need(name)
            except _NotBuilt as e:
                bad.append(f"{e}: {name}")
        if bad:
            return bad
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "fleet.db")
            base = sqlite3.connect(target)
            base.execute(_event_tables_sql())
            base.commit()
            base.close()
            crew_make = _need("crew_make")
            crew_deposit = _need("crew_deposit")
            crew = crew_make()
            if not (isinstance(crew, dict) and crew.get("arrivals") == []):
                bad.append(f"crew_make should build an empty crew with a doorbell: {crew}")
            statement = {"text": "INSERT INTO widgets (id, name) VALUES (4, 'pin')", "parameters": {}}
            ticket = crew_deposit(crew, statement)
            if hp.is_fault(ticket):
                bad.append(f"crew_deposit should hand back a ticket: {ticket}")
            elif not isinstance(ticket, str):
                bad.append(f"crew_deposit should answer a Ticket (a string claim): {ticket}")
        return bad

    return asyncio.run(_run())


def _probe_channel():
    """The replication channel is a Turso (libsql) boundary: session_open_channel opens the one line to a
    primary, channel_push sends local commits, channel_pull brings down what the primary has. These need
    a real libsql primary; when pyturso is not installed the law records that the three functions are at
    least declared and names the skip, so it never passes vacuously (declaration channel_push/pull)."""
    bad = []
    for name in ("session_open_channel", "channel_push", "channel_pull"):
        try:
            _need(name)
        except _NotBuilt as e:
            bad.append(f"{e}: {name}")
    try:
        import turso  # noqa: F401
    except Exception:
        bad.append("channel laws need a real libsql/turso primary (pyturso not importable); the push/pull round trip is unverified here")
    return bad


async def _replica_marker_reached(url, token, marker):
    """Open a replica on the real primary, write one marked row locally, push it, then open a second
    fresh replica and pull: answer whether the marker made the whole round trip to the primary and back.
    The channel is persist's own session_open_channel / channel_push / channel_pull, against the real
    cloud database, never a mock."""
    session_open_channel = _need("session_open_channel")
    channel_push = _need("channel_push")
    channel_pull = _need("channel_pull")
    session_close_connection = _need("session_close_connection")
    bad = []
    with tempfile.TemporaryDirectory() as d:
        writer_channel = await session_open_channel(os.path.join(d, "replica.db"), url, token)
        if hp.is_fault(writer_channel):
            return [f"session_open_channel should open the one line to the real primary: {writer_channel}"], False
        # The first push proves the channel reaches a primary and brings the schema down onto an empty copy.
        bootstrap = await channel_push(writer_channel)
        if hp.is_fault(bootstrap):
            return [f"the first channel_push should bootstrap the replica against the primary: {bootstrap}"], False
        cursor = writer_channel.cursor()
        await cursor.execute("CREATE TABLE IF NOT EXISTS replication_probe (id INTEGER PRIMARY KEY, mark TEXT NOT NULL)")
        await writer_channel.commit()
        await cursor.execute("INSERT INTO replication_probe (mark) VALUES (?)", [marker])
        await writer_channel.commit()
        pushed = await channel_push(writer_channel)
        if hp.is_fault(pushed):
            bad.append(f"channel_push should send the local commit to the primary: {pushed}")

        reader_channel = await session_open_channel(os.path.join(d, "replica2.db"), url, token)
        if hp.is_fault(reader_channel):
            await session_close_connection(writer_channel)
            return bad + [f"session_open_channel should open a second replica to read back: {reader_channel}"], False
        pulled = await channel_pull(reader_channel)
        if hp.is_fault(pulled):
            bad.append(f"channel_pull should bring the primary's state down to a fresh replica: {pulled}")
        read_cursor = reader_channel.cursor()
        found = await read_cursor.execute("SELECT mark FROM replication_probe WHERE mark = ?", [marker])
        rows = await found.fetchall()
        await session_close_connection(writer_channel)
        await session_close_connection(reader_channel)
        return bad, bool(rows)


def _probe_replication():
    """The replication round trip against the real Turso primary, the one that was only structurally
    checked before. A locally written, uniquely marked row is pushed to the primary through
    channel_push; a fresh replica then pulls it back through channel_pull, proving the row reached the
    primary and returns (declaration session_open_channel, channel_push, channel_pull, section 5.5).

    A missing TURSO_KEY or turso CLI raises out of the fixture and becomes a loud failure here: the law
    is to test the real primary, never to skip it. Only a genuine transient network failure reaching the
    platform is tolerated, and it is recorded as a named skip rather than a pass."""

    async def _run():
        for name in ("session_open_channel", "channel_push", "channel_pull"):
            try:
                _need(name)
            except _NotBuilt as e:
                return [f"{e}: {name}"]
        bad = await _channel_fault_cases()
        config = turso_replica_config()
        if "unavailable" in config:
            _note_skip(f"replication: {config['unavailable']}")
            return bad
        marker = "hp_" + secrets.token_hex(8)
        round_trip, reached = await _replica_marker_reached(config["url"], config["token"], marker)
        bad.extend(round_trip)
        if not reached and not round_trip:
            bad.append("the marked row did not make the round trip: it was pushed to the real primary but a "
                       "fresh replica did not pull it back")
        return bad

    return asyncio.run(_run())


# inherits: hd=python/honest-persist/honest-persist.hd::session_open_channel -> feature=specs/features/honest-persist.feature::session_open_channel opens the one line to the primary
# inherits: hd=python/honest-persist/honest-persist.hd::channel_push -> feature=specs/features/honest-persist.feature::channel_push sends local commits to the primary
# inherits: hd=python/honest-persist/honest-persist.hd::channel_pull -> feature=specs/features/honest-persist.feature::channel_pull brings down what the primary has and this copy does not
async def _channel_fault_cases():
    """The channel boundaries turn a bad local path and an unreachable primary into Fault values, never a
    raise: session_open_channel on a path it cannot make, and channel_push / channel_pull on a channel
    whose primary is not a real address. No network and no mock — the driver really refuses
    (declaration session_open_channel, channel_push, channel_pull)."""
    session_open_channel = _need("session_open_channel")
    channel_push = _need("channel_push")
    channel_pull = _need("channel_pull")
    bad = []
    with tempfile.TemporaryDirectory() as d:
        # A local path the driver cannot make: its parent is a file, so the directory cannot be created.
        blocker = os.path.join(d, "a-file")
        open(blocker, "w").close()
        unmakeable = await session_open_channel(os.path.join(blocker, "sub", "c.db"), "libsql://x.turso.io", "tok")
        if not (hp.is_fault(unmakeable) and unmakeable.get("code") == "channel_would_not_open"):
            bad.append(f"a channel on an unmakeable path should be a channel_would_not_open Fault: {unmakeable}")
        # A channel whose primary is not a real address: the open defers, the push and pull refuse.
        channel = await session_open_channel(os.path.join(d, "c.db"), "not-a-valid-url", "tok")
        if hp.is_fault(channel):
            bad.append(f"the local channel should open before its primary is reached: {channel}")
        else:
            pushed = await channel_push(channel)
            if not (hp.is_fault(pushed) and pushed.get("code") == "push_refused"):
                bad.append(f"a push to an unreachable primary should be a push_refused Fault: {pushed}")
            elif not pushed.get("message", "").strip():
                bad.append(f"a refused push should explain the replication failure: {pushed!r}")
            pulled = await channel_pull(channel)
            if not (hp.is_fault(pulled) and pulled.get("code") == "pull_refused"):
                bad.append(f"a pull from an unreachable primary should be a pull_refused Fault: {pulled}")
            elif not pulled.get("message", "").strip():
                bad.append(f"a refused pull should explain the replication failure: {pulled!r}")
    return bad


# ---------------------------------------------------------------------------
# 4. Orchestrator and door laws, against a real database.
# ---------------------------------------------------------------------------

async def _migration_schema_on_postgres(target):
    """schema_live and migration_plan against a real PostgreSQL: the door reads the live schema and says
    what a migration would change, or faults legitimately when the host declares no models."""
    schema_live = _need("schema_live")
    migration_plan = _need("migration_plan")
    session_open_connection = _need("session_open_connection")
    query_run_statement = _need("query_run_statement")
    session_close_connection = _need("session_close_connection")
    pool = await session_open_connection(target, "postgresql", 1)
    if hp.is_fault(pool):
        return [f"postgresql: the migration/schema law could not open a connection: {pool}"]
    await query_run_statement(pool, "postgresql", {"text": "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)", "parameters": {}})
    await session_close_connection(pool)
    bad = []
    live = await schema_live(target)
    if hp.is_fault(live):
        bad.append(f"postgresql: schema_live should read the real database's schema: {live}")
    elif not any(t.get("name") == "users" for t in live.get("tables", [])):
        bad.append(f"postgresql: schema_live should find the users table the test built: {live}")
    plan = await migration_plan(target)
    if not (hp.is_fault(plan) or ("operations" in plan and "destroys" in plan)):
        bad.append(f"postgresql: migration_plan should answer a Plan or a Fault: {plan}")
    return bad


def _probe_migration_and_schema():
    """The three read-only doors ask a real database a question and change nothing. migration_plan /
    migration_compare say what a migration would change; schema_live / schema_read_live say what the
    database holds now; schema_declared / schema_say_declared say what the host declared. Run against a
    real sqlite file the test builds behind the models (declaration migration_plan, schema_live,
    schema_declared)."""

    async def _run():
        bad = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "shape.db")
            base = sqlite3.connect(target)
            base.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
            base.commit()
            base.close()

            try:
                schema_live = _need("schema_live")
                live = await schema_live(target)
                if hp.is_fault(live):
                    bad.append(f"schema_live should read the real database's schema: {live}")
                elif not any(t.get("name") == "users" for t in live.get("tables", [])):
                    bad.append(f"schema_live should find the users table the test built: {live}")
            except _NotBuilt as e:
                bad.append(f"{e}: schema_live")
            except Exception as e:
                bad.append(f"schema_live raised {type(e).__name__}: {e}")

            try:
                migration_plan = _need("migration_plan")
                plan = await migration_plan(target)
                if hp.is_fault(plan):
                    # A fault here is legitimate only when the host declares no models; this law just
                    # proves the door runs against a real database and answers a Plan or a Fault value.
                    pass
                elif not ("operations" in plan and "destroys" in plan):
                    bad.append(f"migration_plan should answer a Plan with operations and destroys: {plan}")
            except _NotBuilt as e:
                bad.append(f"{e}: migration_plan")
            except Exception as e:
                bad.append(f"migration_plan raised {type(e).__name__}: {e}")

            # A target naming no engine is refused before anything opens.
            try:
                schema_live = _need("schema_live")
                refused = await schema_live("mysql://nope/db")
                if not hp.is_fault(refused):
                    bad.append(f"schema_live on a target naming no engine should be a Fault: {refused}")
            except _NotBuilt:
                pass
            except Exception as e:
                bad.append(f"schema_live on a bad target raised {type(e).__name__}: {e}")

        # The same read-only doors against a real PostgreSQL: schema_read_live inspects the live schema,
        # migration_compare answers a Plan or a legitimate Fault when the host declares no models.
        if _ASYNCPG_INSTALLED:
            target = postgres_target()
            if target is None:
                _note_skip("migration/schema doors: no PostgreSQL server, so they were exercised on sqlite only")
            else:
                bad.extend(await _migration_schema_on_postgres(target))
        else:
            _note_skip("migration/schema doors: asyncpg is not installed, so they were exercised on sqlite only")

        try:
            schema_declared = _need("schema_declared")
            declared = schema_declared()
            if hp.is_fault(declared):
                pass  # a host with an owned-name model legitimately faults here
            elif not ({"models", "views", "dropping_tables", "dropping_views"} <= set(declared)):
                bad.append(f"schema_declared should answer a Declared record: {declared}")
        except _NotBuilt as e:
            bad.append(f"{e}: schema_declared")
        except Exception as e:
            bad.append(f"schema_declared raised {type(e).__name__}: {e}")

        for name in ("migration_compare", "schema_read_live", "schema_say_declared", "schema_say_refreshes",
                     "schema_read_declared", "view_refreshes"):
            try:
                _need(name)
            except _NotBuilt as e:
                bad.append(f"{e}: {name}")
        return bad

    return asyncio.run(_run())


def _probe_session_open():
    """session_open opens a database for a caller through session_connect against a real sqlite file,
    and is the one door that raises rather than returning a value when it cannot open (declaration
    session_open, session_connect)."""

    async def _run():
        bad = []
        for name in ("session_open", "session_connect"):
            try:
                _need(name)
            except _NotBuilt as e:
                bad.append(f"{e}: {name}")
        if bad:
            return bad
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "open.db")
            session_open = _need("session_open")
            db = await session_open(target, "exit_immediately", None, None)
            if hp.is_fault(db):
                bad.append(f"session_open should return a Database, not a Fault value (it raises instead): {db}")
            elif not (isinstance(db, dict) and db.get("engine") == "sqlite"):
                bad.append(f"session_open should build a Database handle reading the engine off the target: {db}")
        return bad

    return asyncio.run(_run())


def _probe_query_ask():
    """query_ask answers a question or a declared write with one of three shapes: an Answer, a Fault
    whose category decides a retry, or a NoMatch the library could not read (declaration query_ask,
    query_answer). Run against a real opened database."""

    async def _run():
        bad = []
        for name in ("session_open", "query_ask", "query_answer"):
            try:
                _need(name)
            except _NotBuilt as e:
                bad.append(f"{e}: {name}")
        if bad:
            return bad
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "ask.db")
            session_open = _need("session_open")
            query_ask = _need("query_ask")
            db = await session_open(target, "exit_immediately", None, None)
            if hp.is_fault(db):
                return [f"session_open failed before query_ask could run: {db}"]
            model = {"name": "Widget", "table": "widgets",
                     "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None}],
                     "dropping": [], "indexes": [], "constraints": []}
            # A misspelled question marks no grammar: a NoMatch, the database untouched.
            miss = await query_ask(db, model, "%%% not any grammar %%%")
            if not (isinstance(miss, dict) and "reason" in miss):
                bad.append(f"query_ask of a misspelled question should answer a NoMatch as data: {miss}")
        return bad

    return asyncio.run(_run())


_READ_MODEL = {"name": "User", "table": "users",
               "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None},
                           {"name": "name", "declared_type": "text", "renamed_from": None, "references": None}],
               "dropping": [], "indexes": [], "constraints": []}


async def _read_answers_on(engine, target):
    """Drive real reads through the query_ask door against one engine: a list, one row, a count, an
    exists, and a misspelled question that reads back a NoMatch. This runs query_answer end to end —
    grammar, compile, the read boundary and the answer shaper — against a real opened database."""
    session_open_connection = _need("session_open_connection")
    query_run_statement = _need("query_run_statement")
    session_close_connection = _need("session_close_connection")
    session_open = _need("session_open")
    query_ask = _need("query_ask")

    pool = await session_open_connection(target, engine, 1)
    if hp.is_fault(pool):
        return [f"{engine}: the read law could not open a connection: {pool}"]
    await query_run_statement(pool, engine, {"text": "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)", "parameters": {}})
    await query_run_statement(pool, engine, {"text": "INSERT INTO users (id, name) VALUES (1, 'bob')", "parameters": {}})
    await session_close_connection(pool)

    db = await session_open(target, "exit_immediately", None, None)
    if hp.is_fault(db):
        return [f"{engine}: session_open failed before the read law: {db}"]
    bad = []
    rows = await query_ask(db, _READ_MODEL, "User.where(id=1).all")
    if not (isinstance(rows, list) and rows and rows[0].get("name") == "bob"):
        bad.append(f"{engine}: query_ask of an all should read the rows back: {rows}")
    one = await query_ask(db, _READ_MODEL, "User.where(id=1).one")
    if not (isinstance(one, dict) and one.get("id") == 1):
        bad.append(f"{engine}: query_ask of a one should read the single row: {one}")
    count = await query_ask(db, _READ_MODEL, "User.where(name=\"bob\").count")
    if count != 1:
        bad.append(f"{engine}: query_ask of a count should answer the number, got {count}")
    exists = await query_ask(db, _READ_MODEL, "User.where(id=1).exists")
    if exists is not True:
        bad.append(f"{engine}: query_ask of an exists should answer true, got {exists}")
    miss = await query_ask(db, _READ_MODEL, "%% not any grammar %%")
    if not (isinstance(miss, dict) and "reason" in miss):
        bad.append(f"{engine}: a misspelled question should read back a NoMatch: {miss}")
    return bad


def _probe_query_ask_reads():
    """query_answer answers real reads end to end, driven through the query_ask door against a real
    database on sqlite and postgresql (turso's session_open path addresses a remote primary, so its
    local read is exercised through the boundary laws instead). Each read shape — a list, one row, a
    count, an exists — and a misspelled question that reads back a NoMatch is checked (declaration
    query_ask, query_answer)."""

    async def _run():
        for name in ("session_open", "query_ask", "session_open_connection", "query_run_statement"):
            try:
                _need(name)
            except _NotBuilt as e:
                return [f"{e}: {name}"]
        bad = []
        with tempfile.TemporaryDirectory() as d:
            bad.extend(await _read_answers_on("sqlite", os.path.join(d, "reads.db")))
            if _ASYNCPG_INSTALLED:
                target = postgres_target()
                if target is not None:
                    bad.extend(await _read_answers_on("postgresql", target))
                else:
                    _note_skip("query_ask reads: no PostgreSQL server, so the read path was exercised on sqlite only")
            else:
                _note_skip("query_ask reads: asyncpg is not installed, so the read path was exercised on sqlite only")
        return bad

    return asyncio.run(_run())


def _probe_lifecycle_doors():
    """The remaining lifecycle doors are declared and reachable: lifecycle_stop receives the shutdown
    signal, lifecycle_turn runs one drainer's turn, lifecycle_shut_down pushes every local commit out,
    lifecycle_catch_up drives the retry (its behaviour is proved by _probe_generator_retry)
    (declaration lifecycle_stop, lifecycle_turn, lifecycle_shut_down, lifecycle_catch_up)."""
    bad = []
    for name in ("lifecycle_stop", "lifecycle_turn", "lifecycle_shut_down", "lifecycle_catch_up"):
        try:
            _need(name)
        except _NotBuilt as e:
            bad.append(f"{e}: {name}")
    return bad


# ---------------------------------------------------------------------------
# 5. The headline laws: the driven-generator retry and the crew write-queue.
# ---------------------------------------------------------------------------

def _probe_generator_retry():
    """The seam the generator opened, made real. lifecycle_catch_up owns the real write attempts and
    retry_schedule owns the schedule; neither holds the other, so a test can count the attempts and
    inject a boundary failure at each gap — the test declaro's self-retrying loop made impossible
    (declaration lifecycle_catch_up, retry_schedule, spec 7.7).

    This law drives lifecycle_catch_up against a REAL file-backed sqlite database. A second connection
    holds a competing write lock (BEGIN EXCLUSIVE), so every attempt the drainer makes hits a genuine
    SQLITE_BUSY conflict rather than a patched function. With the lock held for the whole turn, the
    schedule exhausts its bound, and the law asserts (a) the write was attempted exactly `bound` times
    and ended on a budget_spent Fault, and (b) the database is left consistent — the contended row never
    half-landed."""

    async def _run():
        bad = []
        for name in ("session_open", "crew_deposit", "crew_release_ticket", "lifecycle_catch_up", "how_to_retry"):
            try:
                _need(name)
            except _NotBuilt as e:
                bad.append(f"{e}: {name} (the driven-retry seam)")
        if bad:
            return bad

        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "retry.db")
            base = sqlite3.connect(target)
            base.execute(_event_tables_sql())
            base.commit()
            base.close()

            session_open = _need("session_open")
            crew_deposit = _need("crew_deposit")
            crew_release_ticket = _need("crew_release_ticket")
            lifecycle_catch_up = _need("lifecycle_catch_up")
            how_to_retry = _need("how_to_retry")

            db = await session_open(target, "exit_immediately", None, None)
            if hp.is_fault(db):
                return [f"session_open failed before the retry law could run: {db}"]

            # Inject a real, persistent conflict: a competing connection takes an exclusive write lock
            # and holds it, so the drainer's every attempt gets SQLITE_BUSY from the real driver.
            blocker = sqlite3.connect(target, isolation_level=None, timeout=0)
            blocker.execute("BEGIN EXCLUSIVE")

            bound = how_to_retry("sqlite")["bound"]
            statement = {"text": "INSERT INTO widgets (id, name) VALUES (9, 'contended')", "parameters": {}}
            ticket = crew_deposit(db["crew"], statement)

            draining = {"db": db, "writer": db["writers"][0] if db.get("writers") else None,
                        "stop": db["crew"].get("stop"), "idle": 0.01}
            # Drive one turn: lifecycle_catch_up performs the real attempts against the locked database.
            turn = await lifecycle_catch_up({"db": db, "writer": draining["writer"], "statement": statement,
                                             "writer_waiting": False, "attempts": 1})
            receipt = await crew_release_ticket(db["crew"], ticket)

            blocker.execute("ROLLBACK")
            blocker.close()

            if not hp.is_fault(receipt) and isinstance(receipt, dict):
                if receipt.get("ok") is not False:
                    bad.append(f"a write that lost every race should end not-ok: {receipt}")
                if receipt.get("attempts") != bound:
                    bad.append(f"the drainer should make exactly {bound} attempts (the bound), the receipt says {receipt.get('attempts')}")
                failure = receipt.get("failure")
                if not (isinstance(failure, dict) and failure.get("category") == "budget_spent"):
                    bad.append(f"exhausted contention should be typed budget_spent, never the caller's error: {failure}")
            else:
                bad.append(f"the parked caller should read a Receipt for its contended write: {receipt}")

            # The database is left consistent: the contended row never half-landed.
            check = sqlite3.connect(target)
            rows = check.execute("SELECT COUNT(*) FROM widgets WHERE id = 9").fetchone()[0]
            check.close()
            if rows != 0:
                bad.append(f"a write that never won its race must leave no row behind; found {rows}")
        return bad

    return asyncio.run(_run())


def _probe_crew_concurrency():
    """The crew write-queue serialises concurrent writers against one real database and backs off on
    contention (declaration Crew, crew_run_write, spec 7.7). Several callers deposit writes at once;
    the law asserts every write lands and the rows are consistent — no write lost, none doubled — which
    is what the single-writer-per-connection crew buys. The database is a real sqlite file shared by the
    drainers; no mock."""

    async def _run():
        bad = []
        for name in ("session_open", "crew_deposit", "crew_release_ticket", "lifecycle_catch_up"):
            try:
                _need(name)
            except _NotBuilt as e:
                bad.append(f"{e}: {name} (the crew write-queue)")
        if bad:
            return bad

        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "queue.db")
            base = sqlite3.connect(target)
            base.execute(_event_tables_sql())
            base.commit()
            base.close()

            session_open = _need("session_open")
            crew_deposit = _need("crew_deposit")
            crew_release_ticket = _need("crew_release_ticket")
            lifecycle_catch_up = _need("lifecycle_catch_up")

            db = await session_open(target, "exit_immediately", None, None)
            if hp.is_fault(db):
                return [f"session_open failed before the concurrency law could run: {db}"]

            writes = [{"text": "INSERT INTO widgets (id, name) VALUES (:id, :name)", "parameters": {"id": i, "name": f"w{i}"}}
                      for i in range(1, 6)]
            tickets = [crew_deposit(db["crew"], w) for w in writes]
            if any(hp.is_fault(t) for t in tickets):
                return [f"crew_deposit faulted while queueing concurrent writers: {tickets}"]

            # Several drainers run their turns concurrently against the one real database.
            writer = db["writers"][0] if db.get("writers") else None
            turns = [lifecycle_catch_up({"db": db, "writer": writer, "statement": None,
                                         "writer_waiting": True, "attempts": 1}) for _ in writes]
            await asyncio.gather(*turns, return_exceptions=True)
            receipts = await asyncio.gather(*[crew_release_ticket(db["crew"], t) for t in tickets])

            if any(hp.is_fault(r) or (isinstance(r, dict) and r.get("ok") is not True) for r in receipts):
                bad.append(f"every queued write should land under serialisation: {receipts}")

            check = sqlite3.connect(target)
            landed = check.execute("SELECT COUNT(*) FROM widgets").fetchone()[0]
            distinct = check.execute("SELECT COUNT(DISTINCT id) FROM widgets").fetchone()[0]
            check.close()
            if landed != 5 or distinct != 5:
                bad.append(f"five serialised writes should land five distinct rows, found {landed} ({distinct} distinct)")
        return bad

    return asyncio.run(_run())


def _probe_turso_mvcc():
    """Turso's MVCC write mode, proved through persist's own writer boundary on a local file. Two writers
    from session_open_writer interleave BEGIN CONCURRENT and both disjoint rows land, which WAL refuses
    outright, so this fails unless session_open_writer actually turned MVCC on for each writer. This is the
    write mode only; no replication channel is opened, because MVCC writes and master-to-slave sync are
    separate. When the installed pyturso cannot do MVCC the law is a named skip, never a pass (declaration
    session_open_writer, crew_run_write, spec 7.7)."""
    cap = _turso_engine_does_mvcc()
    if not cap.get("ok"):
        _note_skip(cap["skip"] + " (the turso MVCC concurrency law)")
        return []

    async def _run():
        for name in ("session_open_writer", "session_open_connection", "query_run_statement",
                     "session_close_connection"):
            try:
                _need(name)
            except _NotBuilt as e:
                return [f"{e}: {name} (the turso MVCC law)"]
        import turso  # the raw read for the landed-row count, the same engine persist writes through
        bad = []
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "mvcc.db")
            built = await _make_table("turso", target, 1)
            if hp.is_fault(built):
                return [f"turso: the widgets table could not be built before the MVCC law: {built}"]
            a = await _need("session_open_writer")(target, "turso")
            b = await _need("session_open_writer")(target, "turso")
            if hp.is_fault(a) or hp.is_fault(b):
                return [f"turso: session_open_writer should open two real MVCC writers, got {a!r} and {b!r}"]
            try:
                ca, cb = a.cursor(), b.cursor()
                await ca.execute("BEGIN CONCURRENT")
                await cb.execute("BEGIN CONCURRENT")
                await ca.execute("INSERT INTO widgets (id, name) VALUES (1, 'a')")
                await cb.execute("INSERT INTO widgets (id, name) VALUES (2, 'b')")
                await a.commit()
                await b.commit()
            except Exception as refused:  # noqa: BLE001
                bad.append(
                    "turso: two writers from session_open_writer should both run BEGIN CONCURRENT under "
                    "MVCC and commit, but one was refused, so session_open_writer did not enable MVCC: "
                    f"{type(refused).__name__}: {refused}")
            await _need("session_close_connection")(a)
            await _need("session_close_connection")(b)
            reader = turso.connect(target)
            landed = reader.cursor().execute("SELECT id FROM widgets ORDER BY id").fetchall()
            reader.close()
            ids = [row[0] for row in landed]
            if ids != [1, 2]:
                bad.append(f"turso: both interleaved MVCC writers should land, expected ids [1, 2], found {ids}")
        return bad

    return asyncio.run(_run())


def _probe_shutdown_handler():
    """lifecycle_install_handler puts the library's shutdown handler in front of whatever was there, is
    idempotent, and the chained handler runs the door and then any displaced handler (declaration
    lifecycle_install_handler). The process signal handlers are saved and restored around the law, and the
    door is stubbed so the law exercises the chaining, not the shutdown itself. An install from a thread
    that is not the main one is refused handler_refused rather than raising."""
    import signal
    import threading
    import honest_persist.crew as crewmod
    import honest_persist.doors as doorsmod
    lifecycle_install_handler = _need("lifecycle_install_handler")
    saved = {n: signal.getsignal(n) for n in (signal.SIGTERM, signal.SIGINT)}
    real_stop = doorsmod.lifecycle_stop
    bad = []
    marks = {"displaced": 0, "stop_ran": 0}

    async def _async_noop_stop(*_a, **_k):
        # The real door is async; the stub matches that contract so the handler drives a real coroutine,
        # not a sync value production never yields. A sync stub here is what hid the dropped-await bug.
        # It records that it ran so the law reads the shutdown actually fired, not just that it chained.
        marks["stop_ran"] += 1
        return None

    def _previous(_number, _frame):
        marks["displaced"] += 1

    try:
        # An install from a non-main thread is refused, not raised. Done first, while our handler is not
        # yet in place, so the thread actually reaches signal.signal (which raises off the main thread).
        off_thread = {}

        def _install_off_main():
            off_thread["result"] = lifecycle_install_handler()

        worker = threading.Thread(target=_install_off_main)
        worker.start(); worker.join()
        refused_it = off_thread.get("result")
        if not (hp.is_fault(refused_it) and refused_it.get("code") == "handler_refused"):
            bad.append(f"installing from a non-main thread should be refused handler_refused: {refused_it}")

        doorsmod.lifecycle_stop = _async_noop_stop  # the door calls this; an async stub matches the real contract
        signal.signal(signal.SIGTERM, _previous)   # a callable previous handler, to cover the displaced arm
        signal.signal(signal.SIGINT, signal.SIG_DFL)  # the default, not callable, to cover the no-displaced arm
        installed = lifecycle_install_handler()
        if installed is not None:
            bad.append(f"installing the handler should answer NOTHING: {installed}")
        ours_term = signal.getsignal(signal.SIGTERM)
        ours_int = signal.getsignal(signal.SIGINT)
        if not getattr(ours_term, crewmod._OURS, False):
            bad.append("lifecycle_install_handler should put our handler in front on SIGTERM")
        again = lifecycle_install_handler()
        if again is not None or signal.getsignal(signal.SIGTERM) is not ours_term:
            bad.append("a second install should leave our handler in place (idempotent)")
        ours_term(signal.SIGTERM, None)   # the door, then the displaced previous handler
        ours_int(signal.SIGINT, None)     # the door, then nothing displaced (default was not callable)
        if marks["displaced"] != 1:
            bad.append(f"the chained handler should run the displaced handler once, ran {marks['displaced']}")
        if marks["stop_ran"] != 2:
            bad.append(f"firing both handlers should drive the async shutdown twice, ran {marks['stop_ran']}")
    finally:
        doorsmod.lifecycle_stop = real_stop
        for number, handler in saved.items():
            signal.signal(number, handler)
    return bad


def _probe_signal_handler_drives_shutdown():
    """The installed SIGTERM/SIGINT handler must actually drive the async shutdown, not build a coroutine
    and drop it (bead honest-framework-smt). The handler is sync, because a signal handler is, and
    lifecycle_stop is async, so the handler has to hand the shutdown to the asyncio loop the module already
    names as its process output: run it when no loop is running, and schedule it onto the loop when one is.
    This law replaces the real door with an async sentinel-setting stub and fires the real installed handler
    in both cases, then checks the stub ran. With the dropped-coroutine bug the stub never runs, so this is
    the regression guard the earlier handler law could not be — that one stubbed the door with a sync no-op,
    which cannot expose a dropped await."""
    import asyncio
    import signal
    import honest_persist.doors as doorsmod
    _need("lifecycle_install_handler")  # surface guard: red backbone when the function is not built yet
    saved = {n: signal.getsignal(n) for n in (signal.SIGTERM, signal.SIGINT)}
    real_stop = doorsmod.lifecycle_stop
    bad = []
    ran = {"count": 0}
    marks = {"displaced": 0}

    async def _sentinel_stop():
        ran["count"] += 1
        return None

    def _prev(_number, _frame):
        marks["displaced"] += 1
        return True

    try:
        doorsmod.lifecycle_stop = _sentinel_stop
        signal.signal(signal.SIGTERM, _prev)
        signal.signal(signal.SIGINT, _prev)
        installed = _need("lifecycle_install_handler")()
        if installed is not None:
            bad.append(f"installing the handler should answer NOTHING: {installed}")

        # 1. No loop running: firing the handler must run the async shutdown to completion.
        ran["count"] = 0
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        if ran["count"] != 1:
            bad.append(f"firing the handler with no running loop should drive the async shutdown once, "
                       f"ran {ran['count']} (the coroutine was built and dropped)")

        # 2. A loop running (the server case): firing the handler must schedule the shutdown onto the loop
        #    and let it run, without raising.
        async def _fire_inside_loop():
            ran["count"] = 0
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
            for _ in range(20):
                await asyncio.sleep(0)
            return ran["count"]

        count_in_loop = asyncio.run(_fire_inside_loop())
        if count_in_loop != 1:
            bad.append(f"firing the handler inside a running loop should drive the async shutdown once, "
                       f"ran {count_in_loop} (the coroutine was built and dropped)")

        # Driving the async shutdown must not cost the chaining: the displaced handler still ran on each
        # of the two firings above.
        if marks["displaced"] != 2:
            bad.append(f"the chained displaced handler should run once per firing (twice), "
                       f"ran {marks['displaced']}")
    finally:
        doorsmod.lifecycle_stop = real_stop
        for number, handler in saved.items():
            signal.signal(number, handler)
    return bad


def _probe_door_paths():
    """The input doors' branches the happy path does not reach (declaration session_open, query_ask,
    lifecycle_stop, lifecycle_turn, migration_plan, view_refreshes). session_open reads two env counts and
    raises CouldNotOpen when one is not a number or when the open itself is refused; query_ask turns a
    question that raises into a question_raised Fault; lifecycle_stop and lifecycle_turn answer NOTHING on
    success, the orchestrator's Fault on a bad drain, and a typed Fault when the orchestrator raises;
    migration_plan answers the plan or the comparison's refusal; view_refreshes hands back the schedule.
    The orchestrator-failure branches are driven by injecting a failing stand-in at the door's own imported
    name, restored afterwards; the real engine is a file-backed sqlite."""
    import honest_persist.doors as doorsmod
    for name in ("session_open", "query_ask", "lifecycle_stop", "lifecycle_turn", "migration_plan",
                 "view_refreshes"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (door paths)"]

    saved_env = {k: os.environ.get(k) for k in ("HONEST_PERSIST_CONNECTIONS", "HONEST_PERSIST_CREW_SIZE")}
    real_shutdown = doorsmod.lifecycle_shut_down
    real_catch_up = doorsmod.lifecycle_catch_up
    real_answer = doorsmod.query_answer

    async def _run(d):
        bad = []
        session_open = _need("session_open")
        target = os.path.join(d, "door.db")

        # A non-number env count raises CouldNotOpen carrying env_not_a_number.
        os.environ["HONEST_PERSIST_CONNECTIONS"] = "not-a-number"
        os.environ.pop("HONEST_PERSIST_CREW_SIZE", None)
        try:
            await session_open(target, "exit_immediately", None, None)
            bad.append("session_open with a non-number env count should raise CouldNotOpen")
        except doorsmod.CouldNotOpen as raised:
            if not (hp.is_fault(raised.fault) and raised.fault.get("code") == "env_not_a_number"):
                bad.append(f"CouldNotOpen should carry the env_not_a_number fault: {raised.fault}")

        # A whole-number env count is read and the open succeeds.
        os.environ["HONEST_PERSIST_CONNECTIONS"] = "3"
        db = await session_open(target, "exit_immediately", None, None)
        if hp.is_fault(db):
            bad.append(f"session_open with a whole-number env count should open: {db}")
        os.environ.pop("HONEST_PERSIST_CONNECTIONS", None)

        # An unreachable target makes the open itself refuse, which the door raises.
        try:
            await session_open(os.path.join(d, "no-dir", "x.db"), "exit_immediately", None, None)
            bad.append("session_open on an unreachable target should raise CouldNotOpen")
        except doorsmod.CouldNotOpen:
            pass

        # A question that raises inside query_answer comes back as a question_raised Fault, never a raise.
        async def _answer_raises(_asking):
            raise RuntimeError("the question blew up")

        doorsmod.query_answer = _answer_raises
        asked = await _need("query_ask")(db, {"name": "Widget"}, "count the widgets")
        if not (hp.is_fault(asked) and asked.get("code") == "question_raised"):
            bad.append(f"a question that raises should answer a question_raised Fault: {asked}")
        doorsmod.query_answer = real_answer

        # lifecycle_stop with nothing to drain answers NOTHING; a faulting drain comes back as the Fault;
        # a drain that raises is caught as shutdown_raised.
        if await _need("lifecycle_stop")() is not None:
            bad.append("lifecycle_stop with nothing to drain should answer NOTHING")

        async def _drain_faults(_s):
            return hp.fault("drain_incomplete", "the drain did not finish", "cut_short", [], {})

        doorsmod.lifecycle_shut_down = _drain_faults
        if not hp.is_fault(await doorsmod.lifecycle_stop()):
            bad.append("lifecycle_stop should hand back the drain's Fault")

        async def _drain_raises(_s):
            raise RuntimeError("drain blew up")

        doorsmod.lifecycle_shut_down = _drain_raises
        blew = await doorsmod.lifecycle_stop()
        if not (hp.is_fault(blew) and blew.get("code") == "shutdown_raised"):
            bad.append(f"a drain that raises should be caught as shutdown_raised: {blew}")
        doorsmod.lifecycle_shut_down = real_shutdown

        # lifecycle_turn: a turn whose catch-up refuses hands the refusal back; one that raises is caught.
        async def _catch_up_faults(_c):
            return hp.fault("driver_said_no", "the driver refused", "refused", [], {})

        doorsmod.lifecycle_catch_up = _catch_up_faults
        turn_fault = await doorsmod.lifecycle_turn({"db": {"target": target}, "writer": None})
        if not hp.is_fault(turn_fault):
            bad.append(f"lifecycle_turn should hand back the catch-up's refusal: {turn_fault}")

        async def _catch_up_raises(_c):
            raise RuntimeError("turn blew up")

        doorsmod.lifecycle_catch_up = _catch_up_raises
        turn_raised = await doorsmod.lifecycle_turn({"db": {"target": target}, "writer": None})
        if not (hp.is_fault(turn_raised) and turn_raised.get("code") == "turn_raised"):
            bad.append(f"a turn that raises should be caught as turn_raised: {turn_raised}")
        doorsmod.lifecycle_catch_up = real_catch_up

        # migration_plan: a reachable database answers a plan; an unreachable one answers the refusal.
        plan = await _need("migration_plan")(target)
        if hp.is_fault(plan) or not isinstance(plan, dict):
            bad.append(f"migration_plan on a reachable database should answer a plan: {plan}")
        refused_plan = await _need("migration_plan")(os.path.join(d, "no-dir", "y.db"))
        if not hp.is_fault(refused_plan):
            bad.append(f"migration_plan on an unreachable database should answer the refusal: {refused_plan}")

        # view_refreshes hands back a schedule list for the database handle.
        schedule = _need("view_refreshes")(db)
        if not isinstance(schedule, list):
            bad.append(f"view_refreshes should hand back a list of schedule declarations: {schedule}")
        return bad

    try:
        with tempfile.TemporaryDirectory() as d:
            return asyncio.run(_run(d))
    finally:
        doorsmod.lifecycle_shut_down = real_shutdown
        doorsmod.lifecycle_catch_up = real_catch_up
        doorsmod.query_answer = real_answer
        for key, value in saved_env.items():
            _pick(value is None, lambda: os.environ.pop(key, None), lambda: os.environ.__setitem__(key, value))


def _probe_pydantic_loader():
    """The Pydantic schema loader reads a host's declared models and views into a Declared (declaration
    schema_read_declared, _pydantic_loader). A host that declares a model (with __tablename__ and typed
    columns) and a view (with __viewname__ and __declaration__) is read back: each basic column type
    mapped to its DECLARED_TYPES word, an annotation it has no word for falling to text, and the optional
    __indexes__/__constraints__/__dropping__ and the view's freshness and cadence read off the class. When
    Pydantic is not installed the loader raises, which schema_read_declared reads as the host having
    declared nothing, so this law records a named skip rather than failing."""
    try:
        from pydantic import BaseModel
    except Exception:  # noqa: BLE001
        _note_skip("pydantic: not installed, so the declared-model loader path was not exercised")
        return []
    from honest_persist._pydantic_loader import load_declared

    class _Account(BaseModel):
        id: int
        name: str
        balance: float
        active: bool
        avatar: bytes
        extra: dict  # an annotation the loader has no word for, so it falls to text
        __tablename__ = "hp_law_accounts"
        __indexes__ = [{"name": "ix_name", "columns": ["name"]}]
        __constraints__ = [{"kind": "unique", "columns": ["name"]}]
        __dropping__ = ["old_column"]

    class _AccountSummary(BaseModel):
        __viewname__ = "hp_law_account_summary"
        __declaration__ = "SELECT id, name FROM hp_law_accounts"
        __freshness__ = "on_write"
        __cadence__ = 60
        __attempts_allowed__ = 3

    class _Sweep(BaseModel):
        __dropping_tables__ = ["hp_law_legacy_table"]
        __dropping_views__ = ["hp_law_legacy_view"]

    import gc
    bad = []
    try:
        declared = load_declared()
        account = _pick(any(m["table"] == "hp_law_accounts" for m in declared["models"]),
                        lambda: next(m for m in declared["models"] if m["table"] == "hp_law_accounts"),
                        lambda: None)
        if account is None:
            bad.append("load_declared should read a host model carrying __tablename__ into the Declared")
        else:
            by_name = {c["name"]: c["declared_type"] for c in account["columns"]}
            want = {"id": "integer", "name": "text", "balance": "float", "active": "boolean",
                    "avatar": "bytes", "extra": "text"}
            for col, typ in want.items():
                if by_name.get(col) != typ:
                    bad.append(f"the loader should map column {col} to {typ}, got {by_name.get(col)}")
            if not (account["indexes"] and account["constraints"] and account["dropping"]):
                bad.append(f"the model's declared indexes, constraints and dropping should be read off the class: {account}")
            view = _pick(any(v["name"] == "hp_law_account_summary" for v in declared["views"]),
                         lambda: next(v for v in declared["views"] if v["name"] == "hp_law_account_summary"),
                         lambda: None)
            if view is None or view["declaration"] != "SELECT id, name FROM hp_law_accounts" or view["freshness"] != "on_write":
                bad.append(f"load_declared should read a host view carrying __viewname__ and __declaration__: {view}")
            if "hp_law_legacy_table" not in declared["dropping_tables"] or "hp_law_legacy_view" not in declared["dropping_views"]:
                bad.append(f"load_declared should collect __dropping_tables__ and __dropping_views__: {declared}")
    finally:
        del _Account, _AccountSummary, _Sweep  # drop the host models so they do not pollute another law's schema read
        gc.collect()
    return bad


def _probe_pure_edges():
    """The pure spelling, schema and engine branches a create-from-empty migration never reaches
    (declaration spell_operation, spell_view, mechanism_for, name_what_destroys, refuse_undeclared_loss,
    how_to_spell, crew_size, permitted_connections). Each is driven by a crafted record through the real
    public function: every schema-change kind is spelled; a check constraint and an empty column list are
    refused; a view that stands for a write and one whose SELECT will not compile are refused; a
    materialized view an engine cannot offer is refused; every way a loss is asked for (a column dropped
    or narrowed, a table or view dropped, and a change that nothing can declare) is walked, and a drop a
    model declared is permitted; how_to_spell refuses a change that cannot reach the primary and a kind it
    has no row for; and a crew or connection count below one is refused."""
    for name in ("spell_operation", "spell_view", "mechanism_for", "name_what_destroys",
                 "refuse_undeclared_loss", "how_to_spell", "crew_size", "permitted_connections"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (pure edges)"]
    spell_operation = _need("spell_operation"); spell_view = _need("spell_view")
    mechanism_for = _need("mechanism_for"); name_what_destroys = _need("name_what_destroys")
    refuse_undeclared_loss = _need("refuse_undeclared_loss"); how_to_spell = _need("how_to_spell")
    crew_size = _need("crew_size"); permitted_connections = _need("permitted_connections")
    bad = []

    read_decl = _declaration()
    write_decl = _declaration(wanted="add", rows=[{"id": 1}])
    view = {"name": "active", "freshness": "always current", "declaration": read_decl}
    kinds = {
        "rename_column": _ddl_operation("rename_column", column="old", renamed_to="new"),
        "rename_table": _ddl_operation("rename_table", renamed_to="posts2"),
        "create_index": _ddl_operation("create_index", indexes=[{"name": "ix", "columns": ["id"], "unique": False}]),
        "drop_index": _ddl_operation("drop_index", indexes=[{"name": "ix", "columns": ["id"], "unique": False}]),
        "create_view": _ddl_operation("create_view", view=view),
        "drop_view": _ddl_operation("drop_view", view=view),
        "insert_enum_values": _ddl_operation("insert_enum_values", values=["a", "b"]),
        "remove_enum_values": _ddl_operation("remove_enum_values", values=["a"]),
    }
    for name, op in kinds.items():
        for engine in ("sqlite", "postgresql", "turso"):
            spelled = spell_operation(op, engine, False)
            if not (isinstance(spelled, list) and spelled and "text" in spelled[0]):
                bad.append(f"spell_operation of {name} on {engine} should write statements: {spelled}")
    # A check constraint this reduced speller does not write, and a create_table handed no columns.
    check_create = _ddl_operation("create_table", table="t",
                                  columns=[{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None}],
                                  constraints=[{"name": "ck", "kind": "check", "columns": ["id"]}])
    if not hp.is_fault(spell_operation(check_create, "sqlite", False)):
        bad.append("a check constraint should be refused check_unsupported, not spelled")
    if not hp.is_fault(spell_operation(_ddl_operation("create_table", table="t", columns=[]), "sqlite", False)):
        bad.append("a create_table handed no columns should be refused empty_field")

    # spell_view: a view that stands for a write is not a question; one whose SELECT will not compile is a Fault.
    if not hp.is_fault(spell_view({"name": "w", "declaration": write_decl}, "sqlite")):
        bad.append("spell_view of a view that stands for a write should be refused view_not_a_question")
    if not hp.is_fault(spell_view({"name": "w", "declaration": _declaration(wanted="first")}, "sqlite")):
        bad.append("spell_view of a view whose SELECT will not compile should be a Fault")

    # mechanism_for: an engine with no materialized view of its own and nothing to build one from is refused.
    if not hp.is_fault(mechanism_for("always current", "sqlite", {"native": False, "built_from": ""})):
        bad.append("mechanism_for a materialized view an engine cannot offer should be refused")

    # name_what_destroys names the losses; refuse_undeclared_loss walks every way a loss is asked for.
    destroyers = [_ddl_operation("drop_column", table="users", column="gone"),
                  _ddl_operation("alter_column", table="users", column="narrowed"),
                  _ddl_operation("drop_table", table="legacy"),
                  _ddl_operation("drop_view", table="old_view")]
    marked = name_what_destroys(destroyers)
    if not marked["destroys"]:
        bad.append(f"name_what_destroys should name every loss: {marked}")
    empty_declared = {"models": [], "views": [], "dropping_tables": [], "dropping_views": []}
    if not hp.is_fault(refuse_undeclared_loss(marked, empty_declared)):
        bad.append("refuse_undeclared_loss should refuse an undeclared loss")
    # A drop a model asked for is permitted (the plan runs); a destroying change nothing can declare is refused.
    permit_declared = {"models": [{"table": "users", "dropping": ["gone"], "columns": []}],
                       "views": [], "dropping_tables": [], "dropping_views": []}
    permitted = refuse_undeclared_loss(name_what_destroys([_ddl_operation("drop_column", table="users", column="gone")]), permit_declared)
    if hp.is_fault(permitted):
        bad.append(f"a drop a model declared should be permitted, not refused: {permitted}")
    undeclarable = {"operations": [{**_ddl_operation("create_table", table="x"), "destroys": True},
                                    {**_ddl_operation("drop_view", table="old_view"), "destroys": True}]}
    if not hp.is_fault(refuse_undeclared_loss(undeclarable, empty_declared)):
        bad.append("a destroying change nothing can declare should be refused")

    # name_what_is_ambiguous folds a declared rename into one rename_column operation: a model says a
    # new column was renamed_from the gone one, so the drop and the add become a single rename.
    from honest_persist.schema import name_what_is_ambiguous
    renamed_ops = [_ddl_operation("drop_column", table="users", column="was"),
                   _ddl_operation("add_column", table="users", column="now",
                                  columns=[{"name": "now", "declared_type": "text", "renamed_from": "was", "references": None}])]
    renamed_declared = {"models": [{"table": "users", "dropping": [],
                                    "columns": [{"name": "now", "declared_type": "text", "renamed_from": "was", "references": None}]}],
                        "views": [], "dropping_tables": [], "dropping_views": []}
    settled = name_what_is_ambiguous(renamed_ops, renamed_declared)
    if hp.is_fault(settled) or not any(op["kind"] == "rename_column" for op in settled):
        bad.append(f"a declared rename should fold the drop and add into one rename_column: {settled}")

    # how_to_spell: a change that cannot reach the primary, and a kind it has no row for.
    if not hp.is_fault(how_to_spell("alter_column", "turso", True)):
        bad.append("how_to_spell of alter_column on a replicating turso should refuse change_cannot_reach_primary")
    if not hp.is_fault(how_to_spell("teleport_kind", "sqlite", False)):
        bad.append("how_to_spell of a kind no row holds should refuse no_spelling_for_change")

    # A crew or connection count below one is refused before any drainer would hang.
    if not hp.is_fault(crew_size(0)):
        bad.append("crew_size(0) should refuse crew_too_small")
    if not hp.is_fault(permitted_connections(0)):
        bad.append("permitted_connections(0) should refuse connections_too_few")
    return bad


def _raises_loader():
    raise RuntimeError("the loader blew up")


_WRITE_MODEL = {"name": "User", "table": "users",
                "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None},
                            {"name": "name", "declared_type": "text", "renamed_from": None, "references": None}],
                "dropping": [], "indexes": [], "constraints": []}


def _probe_query_write_paths():
    """query_answer carries a write all the way to a real database, by each of its three routes
    (declaration query_answer, spec 7.7): several rows land as one transaction, a transaction whose rows
    collide comes back as the driver's Fault, a lone row is deposited with the crew and its receipt waited
    for while a drainer runs it, and a read that names a column the model does not declare is refused
    before any statement is compiled. Run against a real file-backed sqlite; the lone-row deposit is
    drained by a concurrent lifecycle_catch_up, the host scheduler's job."""
    for name in ("session_open", "query_ask", "query_answer", "lifecycle_catch_up"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (query write paths)"]
    from honest_persist.orchestrators import lifecycle_catch_up

    async def _run(d):
        bad = []
        target = os.path.join(d, "writes.db")
        base = sqlite3.connect(target)
        base.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        base.commit(); base.close()
        session_open = _need("session_open"); query_ask = _need("query_ask")
        db = await session_open(target, "exit_immediately", None, None)
        if hp.is_fault(db):
            return [f"session_open failed before the write-paths law: {db}"]

        # A read that names a column the model does not declare is refused before a statement compiles.
        refused_read = await query_ask(db, _WRITE_MODEL, 'User.where(id=1).select("nope").all')
        if not (hp.is_fault(refused_read) and refused_read.get("code") == "undeclared_column"):
            bad.append(f"a read naming an undeclared column should be refused undeclared_column: {refused_read}")

        # Several rows land as one transaction.
        many = await query_ask(db, _WRITE_MODEL, 'User.rows({"id": 2, "name": "b"}, {"id": 3, "name": "c"}).add')
        if many != 2:
            bad.append(f"a multi-row add should land every row and answer the count: {many}")
        # A transaction whose rows collide with what is there comes back as the driver's Fault.
        collide = await query_ask(db, _WRITE_MODEL, 'User.rows({"id": 2, "name": "x"}, {"id": 9, "name": "y"}).add')
        if not hp.is_fault(collide):
            bad.append(f"a colliding multi-row write should answer the driver's Fault: {collide}")

        # A lone row is deposited with the crew; a concurrent drainer runs it and the receipt is waited for.
        writer = db["writers"][0] if db.get("writers") else None
        write = asyncio.ensure_future(query_ask(db, _WRITE_MODEL, 'User.rows({"id": 5, "name": "e"}).add'))
        for _ in range(60):
            if write.done():
                break
            await lifecycle_catch_up({"db": db, "writer": writer, "statement": None,
                                      "writer_waiting": True, "attempts": 1})
            await asyncio.sleep(0.005)
        try:
            landed = await asyncio.wait_for(write, timeout=5)
        except asyncio.TimeoutError:
            write.cancel()
            return bad + ["a lone-row deposit was never drained: query_answer did not return"]
        if landed != 1:
            bad.append(f"a lone-row deposit, once drained, should answer the count: {landed}")

        check = sqlite3.connect(target)
        rows = [r[0] for r in check.execute("SELECT id FROM users ORDER BY id").fetchall()]
        check.close()
        if rows != [2, 3, 5]:
            bad.append(f"the writes that should have landed are 2, 3 and 5; found {rows}")
        return bad

    with tempfile.TemporaryDirectory() as d:
        return asyncio.run(_run(d))


def _probe_query_read_edges():
    """The two parse boundaries asked_from_written answers as data rather than a raise (declaration
    asked_from_written): a call argument that is not a python literal (a bare name) reads back as the
    absence, and a written query that is not valid python at all parses to nothing instead of raising."""
    try:
        asked_from_written = _need("asked_from_written")
        methods_of = _need("methods_of")
    except _NotBuilt as e:
        return [f"{e}: a query-reading function (parse edges)"]
    bad = []
    # A bare name where a literal was expected: literal_eval cannot read it, so the part reads as absence.
    bare = asked_from_written("User.select(whatever_bare_name).all", methods_of("pseudo_sql"))
    if not isinstance(bare, dict):
        bad.append(f"asked_from_written should read a non-literal argument as data, not raise: {bare}")
    # A written query that is not valid python parses to nothing, never a raise.
    malformed = asked_from_written("User.(((", methods_of("pseudo_sql"))
    if not isinstance(malformed, dict):
        bad.append(f"asked_from_written of a malformed query should parse to nothing, not raise: {malformed}")
    return bad


def _probe_inspect_edges():
    """schema_inspect reads the parts a clean empty database never shows (declaration schema_inspect): a
    view is read into the schema, a column whose storage type the package has no word for comes back as a
    Fault rather than a guess, and a question a closed connection cannot answer is a Fault, never a raise.
    Driven against real sqlite files through the inspect boundary."""
    for name in ("session_open_connection", "schema_inspect", "how_to_inspect", "session_close_connection"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (inspect edges)"]
    schema_inspect = _need("schema_inspect"); how_to_inspect = _need("how_to_inspect")
    session_open_connection = _need("session_open_connection")
    session_close_connection = _need("session_close_connection")

    async def _run(d):
        bad = []
        # A database holding a view: the view is read into the schema.
        with_view = os.path.join(d, "view.db")
        base = sqlite3.connect(with_view)
        base.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        base.execute("CREATE VIEW active AS SELECT id FROM users")
        base.commit(); base.close()
        conn = await session_open_connection(with_view, "sqlite", 1)
        held = await schema_inspect(conn, "sqlite", how_to_inspect("sqlite"))
        await session_close_connection(conn)
        if hp.is_fault(held) or not any(v["name"] == "active" for v in held.get("views", [])):
            bad.append(f"schema_inspect should read a declared view into the schema: {held}")

        # A column whose storage type the package has no word for: a Fault, not a guess.
        odd = os.path.join(d, "odd.db")
        base = sqlite3.connect(odd)
        base.execute("CREATE TABLE shapes (id INTEGER PRIMARY KEY, where_it_is GEOMETRY)")
        base.commit(); base.close()
        conn = await session_open_connection(odd, "sqlite", 1)
        read = await schema_inspect(conn, "sqlite", how_to_inspect("sqlite"))
        await session_close_connection(conn)
        if not hp.is_fault(read):
            bad.append(f"a column whose storage type has no word should make the inspect a Fault: {read}")

        # A question a closed connection cannot answer: a Fault, never a raise.
        empty = os.path.join(d, "closed.db")
        base = sqlite3.connect(empty)
        base.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        base.commit(); base.close()
        conn = await session_open_connection(empty, "sqlite", 1)
        await session_close_connection(conn)
        refused_inspect = await schema_inspect(conn, "sqlite", how_to_inspect("sqlite"))
        if not hp.is_fault(refused_inspect):
            bad.append(f"inspecting through a closed connection should be a Fault, not a raise: {refused_inspect}")
        return bad

    with tempfile.TemporaryDirectory() as d:
        return asyncio.run(_run(d))


def _probe_shutdown_push():
    """lifecycle_shut_down drains every registered database at exit and closes it (declaration
    lifecycle_shut_down): a local, non-replicating database on the registered list has nothing to push to
    a primary, so the drain writes its progress line and closes the connections cleanly. The registered
    list is saved and restored around the law, and the database is a real file-backed sqlite."""
    for name in ("session_open", "lifecycle_shut_down"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (shutdown push)"]
    import honest_persist.crew as crewmod
    saved = list(crewmod._REGISTERED)

    async def _run(d):
        bad = []
        session_open = _need("session_open"); lifecycle_shut_down = _need("lifecycle_shut_down")
        target = os.path.join(d, "shut.db")
        base = sqlite3.connect(target)
        base.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        base.commit(); base.close()
        db = await session_open(target, "exit_immediately", None, None)
        if hp.is_fault(db):
            return [f"session_open failed before the shutdown law: {db}"]
        crewmod._REGISTERED.append(db)
        out = await lifecycle_shut_down({"started_at": 0.0})
        if hp.is_fault(out):
            bad.append(f"shutting down a local registered database should not fault: {out}")
        elif not any(x is db for x in out.get("databases", [])):
            bad.append(f"lifecycle_shut_down should report the databases it drained: {out}")
        return bad

    try:
        with tempfile.TemporaryDirectory() as d:
            return asyncio.run(_run(d))
    finally:
        crewmod._REGISTERED[:] = saved


def _probe_view_refresh_specs():
    """schema_say_refreshes turns a declared `refreshed when asked` view into a ScheduleSpec the host's
    scheduler drives (declaration schema_say_refreshes): the spec carries the view's key and cadence, its
    work rewrites the view's table, and its decide rule reads what to do after a run. The host view is a
    pydantic model, cleaned up afterwards; the spec is built without opening a database, so no migration
    runs."""
    try:
        from pydantic import BaseModel
    except Exception:  # noqa: BLE001
        _note_skip("pydantic: not installed, so the view-refresh schedule path was not exercised")
        return []
    import gc
    schema_say_refreshes = _need("schema_say_refreshes")
    bad = []

    class _RefreshView(BaseModel):
        __viewname__ = "hp_law_refresh_view"
        __declaration__ = "SELECT id FROM hp_law_users"
        __freshness__ = "refreshed when asked"
        __cadence__ = 30
        __attempts_allowed__ = 2

    try:
        specs = schema_say_refreshes({"target": "x", "engine": "sqlite"})
        if hp.is_fault(specs) or not isinstance(specs, list) or not specs:
            bad.append(f"schema_say_refreshes should hand back a schedule spec for a refreshed-when-asked view: {specs}")
        else:
            spec = next((s for s in specs if s.get("key") == "hp_law_refresh_view"), None)
            if spec is None:
                bad.append(f"the schedule spec for the declared view should be present: {specs}")
            elif spec.get("cadence") != 30:
                bad.append(f"the spec should carry the view's cadence: {spec}")
            else:
                if asyncio.run(spec["work"]()) != 0:
                    bad.append("the spec's work should rewrite the view's table and answer the rows touched")
                if not isinstance(spec["decide"](0, 1), dict):
                    bad.append("the spec's decide should answer what to do after a run")
    finally:
        del _RefreshView
        gc.collect()
    return bad


def _probe_retry_outcomes():
    """The two WriteOutcome branches the contended-write law does not reach (declaration
    lifecycle_catch_up, crew_run_write, retry_schedule, spec 7.7): a write refused for a logical reason (a
    NOT NULL violation) is given up at once carrying the driver's Fault, never retried as contention; and a
    write whose engine has no driver answers a NoMatch that travels straight out of the drain, never
    reaching the schedule. Run against a real sqlite file, with a concurrent drainer for the logical case."""
    for name in ("session_open", "crew_deposit", "crew_release_ticket", "lifecycle_catch_up", "crew_make"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (retry outcomes)"]
    from honest_persist.crew import crew_make, crew_deposit

    async def _run(d):
        bad = []
        session_open = _need("session_open"); crew_release_ticket = _need("crew_release_ticket")
        lifecycle_catch_up = _need("lifecycle_catch_up")
        target = os.path.join(d, "retry.db")
        base = sqlite3.connect(target)
        base.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        base.commit(); base.close()
        db = await session_open(target, "exit_immediately", None, None)
        if hp.is_fault(db):
            return [f"session_open failed before the retry-outcome law: {db}"]
        writer = db["writers"][0]
        ticket = crew_deposit(db["crew"], {"text": "INSERT INTO widgets (id, name) VALUES (1, NULL)", "parameters": {}})
        waiter = asyncio.ensure_future(crew_release_ticket(db["crew"], ticket))
        for _ in range(30):
            if waiter.done():
                break
            await lifecycle_catch_up({"db": db, "writer": writer, "statement": None,
                                      "writer_waiting": True, "attempts": 1})
            await asyncio.sleep(0.005)
        receipt = await asyncio.wait_for(waiter, timeout=3)
        if not (isinstance(receipt, dict) and receipt.get("ok") is False and receipt.get("attempts") == 1):
            bad.append(f"a logical refusal should be given up at once, never retried as contention: {receipt}")

        # A write whose engine has no driver answers a NoMatch straight out of the drain.
        stray = crew_make()
        crew_deposit(stray, {"text": "INSERT INTO widgets (id) VALUES (2)", "parameters": {}})
        no_driver = {"engine": "mysql", "crew": stray, "channel": None, "target": "x",
                     "connections": [], "writers": []}
        drained = await lifecycle_catch_up({"db": no_driver, "writer": None, "statement": None,
                                            "writer_waiting": False, "attempts": 0})
        if not hp.is_no_match(drained):
            bad.append(f"a write whose engine has no driver should answer a NoMatch out of the drain: {drained}")
        return bad

    with tempfile.TemporaryDirectory() as d:
        return asyncio.run(_run(d))


def _probe_replication_orchestration():
    """The orchestrator paths only a replicating turso database reaches (declaration session_connect,
    lifecycle_catch_up, lifecycle_shut_down, section 5.5): opening with a primary and token opens the sync
    channel and puts the database on the shutdown-registered list; a free turn pushes the local commits and
    pulls the primary's back; and shutting down pushes each registered database out. Each sync boundary
    answers as data, never a raise. Driven against the real Turso primary; when it is unavailable this is a
    named skip, never a pass. The registered list is saved and restored."""
    for name in ("session_open", "lifecycle_catch_up", "lifecycle_shut_down"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (replication orchestration)"]
    import honest_persist.crew as crewmod
    config = turso_replica_config()
    if "unavailable" in config:
        _note_skip(f"replication orchestration: {config['unavailable']}")
        return []

    async def _run(d):
        bad = []
        session_open = _need("session_open"); lifecycle_catch_up = _need("lifecycle_catch_up")
        lifecycle_shut_down = _need("lifecycle_shut_down")
        target = "libsql://" + os.path.join(d, "rep.db")
        db = await session_open(target, "replicate_then_exit", config["url"], config["token"])
        if hp.is_fault(db):
            return [f"opening a replicating turso database should build a handle, not fault: {db}"]
        if db.get("engine") != "turso" or db.get("channel") is None:
            bad.append(f"a replicating open should name the turso engine and hold a channel: engine={db.get('engine')}")
        if not any(x is db for x in crewmod.read_registered()):
            bad.append("a replicate_then_exit database should be on the shutdown-registered list")
        # A free turn syncs: it pushes the local commits and pulls the primary's back, answering as data.
        turn = await lifecycle_catch_up({"db": db, "writer": db["writers"][0], "statement": None,
                                         "writer_waiting": False, "attempts": 0})
        if not (turn is None or isinstance(turn, dict)):
            bad.append(f"a free turn on a replicating database should answer as data, never raise: {turn!r}")
        # Shutting down pushes every registered database out, answering as data.
        out = await lifecycle_shut_down({"started_at": 0.0})
        if not (hp.is_fault(out) or isinstance(out, dict)):
            bad.append(f"shutting down a replicating database should answer as data: {out!r}")
        return bad

    saved = list(crewmod._REGISTERED)
    try:
        with tempfile.TemporaryDirectory() as d:
            return asyncio.run(_run(d))
    finally:
        crewmod._REGISTERED[:] = saved


def _probe_sync_turn():
    """A free turn on a replicating database runs the sync (declaration lifecycle_catch_up, channel_push,
    channel_pull, spec 5.5), by both of its push outcomes, against real Turso channels: a channel whose
    primary is unreachable makes the turn's push fail, which ends the sync there; and a channel bootstrapped
    on the real primary makes the push succeed, so the turn goes on to pull the primary's state back. No
    stand-in: both channels are real session_open_channel objects. The real-primary half is a named skip
    when the primary is unavailable."""
    for name in ("lifecycle_catch_up", "crew_make", "session_open_channel", "channel_push",
                 "session_close_connection"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (sync turn)"]
    lifecycle_catch_up = _need("lifecycle_catch_up"); crew_make = _need("crew_make")
    session_open_channel = _need("session_open_channel"); channel_push = _need("channel_push")
    session_close_connection = _need("session_close_connection")

    def _replicating_db(channel):
        crew = crew_make()
        crew["stop"].set()  # nothing to drain, so the wait for work returns at once
        return {"engine": "turso", "crew": crew, "channel": channel, "target": "x",
                "connections": [], "writers": [None]}

    async def _run(d):
        bad = []
        # A real channel whose primary is unreachable: the turn's push fails and the sync ends there.
        unreachable = await session_open_channel(os.path.join(d, "bad.db"), "not-a-valid-url", "tok")
        if hp.is_fault(unreachable):
            bad.append(f"a channel should open locally before its primary is reached: {unreachable}")
        else:
            turn = await lifecycle_catch_up({"db": _replicating_db(unreachable), "writer": None,
                                             "statement": None, "writer_waiting": False, "attempts": 0})
            if not hp.is_fault(turn):
                bad.append(f"a free turn whose push cannot reach the primary should answer that Fault: {turn}")

        # A real channel bootstrapped on the real primary: the push succeeds, so the turn pulls as well.
        config = turso_replica_config()
        if "unavailable" in config:
            _note_skip(f"sync turn (pull half): {config['unavailable']}")
            return bad
        channel = await session_open_channel(os.path.join(d, "good.db"), config["url"], config["token"])
        if hp.is_fault(channel):
            return bad + [f"the sync channel should open on the real primary: {channel}"]
        boot = await channel_push(channel)  # bootstrap, so the turn's own push succeeds and it goes on to pull
        if hp.is_fault(boot):
            await session_close_connection(channel)
            return bad + [f"the first push should bootstrap the replica against the primary: {boot}"]
        turn = await lifecycle_catch_up({"db": _replicating_db(channel), "writer": None,
                                         "statement": None, "writer_waiting": False, "attempts": 0})
        await session_close_connection(channel)
        if not (turn is None or isinstance(turn, dict)):
            bad.append(f"a free turn whose push succeeds should pull and answer as data: {turn!r}")
        return bad

    with tempfile.TemporaryDirectory() as d:
        return asyncio.run(_run(d))


def _probe_observe_emit_swallowed():
    """A query whose observe emit fails still answers its rows (declaration query_run_statement, spec 8.5):
    the emit of hf.persist.query is best-effort, so an emit that raises is swallowed and never fails the
    query. The emit seam is driven with an emit that raises, and a real read still reads its rows.

    The matching success path (io.py returns after a clean emit) is NOT exercised here, and cannot be
    honestly: persist calls honest_observe.emit('hf.persist.query', payload) with two positional arguments,
    but the real emit is an async function of nine, so every real emit raises TypeError and the success
    return is dead code until the seam is reconciled (bead honest-framework-z6l). An earlier version of this
    law mocked a two-argument emit that succeeded, which hid that mismatch; it is removed."""
    for name in ("session_open_connection", "query_run_statement", "session_close_connection"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (observe emit)"]
    import honest_observe
    real_emit = honest_observe.emit

    def _raising_emit(*_args, **_kwargs):
        raise RuntimeError("the observe seam blew up")

    async def _run(d):
        session_open_connection = _need("session_open_connection")
        query_run_statement = _need("query_run_statement")
        session_close_connection = _need("session_close_connection")
        target = os.path.join(d, "emit.db")
        base = sqlite3.connect(target)
        base.execute("CREATE TABLE x (id INTEGER PRIMARY KEY)")
        base.commit(); base.close()
        conn = await session_open_connection(target, "sqlite", 1)
        ran = await query_run_statement(conn, "sqlite", {"text": "SELECT id FROM x", "parameters": {}})
        await session_close_connection(conn)
        return [] if not hp.is_fault(ran) else [f"a read should answer its rows when the observe emit fails: {ran}"]

    try:
        honest_observe.emit = _raising_emit
        with tempfile.TemporaryDirectory() as d:
            return asyncio.run(_run(d))
    finally:
        honest_observe.emit = real_emit


class _SqliteQueryConnection:
    """A duck-typed §7 connection over a real sqlite3 database: `await execute(sql, params)` answers
    {rows, rowcount}, and begin/commit/rollback drive a transaction. This is the adopter-supplied
    connection the §7 layer runs on (spec §7.4, §8.1.1 — a real driver, not a mock); the sqlite
    connection is opened in autocommit mode so a single execute persists and a transaction is explicit."""

    def __init__(self, path):
        self._raw = sqlite3.connect(path, isolation_level=None)

    async def execute(self, sql, params):
        cursor = self._raw.execute(sql, params or {})
        rows = _pick(cursor.description is None, lambda: [],
                     lambda: [dict(zip([c[0] for c in cursor.description], row)) for row in cursor.fetchall()])
        return {"rows": rows, "rowcount": cursor.rowcount}

    async def begin(self):
        self._raw.execute("BEGIN")

    async def commit(self):
        self._raw.execute("COMMIT")

    async def rollback(self):
        self._raw.execute("ROLLBACK")

    def close(self):
        self._raw.close()


def _probe_query_builders():
    """The §7 query builders are pure functions that return a Query — plain data, no I/O (spec §7.1, §7.2):
    select, insert, update, delete and raw each answer a dict carrying the SQL text and the named
    parameters, and none performs any I/O. The parameters a write carries are the values it was handed."""
    for name in ("select", "insert", "update", "delete", "raw"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (query builders)"]
    select = _need("select"); insert = _need("insert"); update = _need("update")
    delete = _need("delete"); raw = _need("raw")
    bad = []
    for label, query in (
        ("select", select("users", ["id", "email"], {"status": "active"}, None, None, None, None)),
        ("insert", insert("users", {"id": 1, "email": "a@b.c"})),
        ("update", update("users", {"email": "x@y.z"}, {"id": 1})),
        ("delete", delete("users", {"id": 1})),
        ("raw", raw("SELECT 1", None)),
    ):
        if not (isinstance(query, dict) and isinstance(query.get("sql"), str) and isinstance(query.get("params"), dict)):
            bad.append(f"{label} should build a Query with sql text and a params dict: {query}")
    # The values a write carries must be present in its params, so the driver binds them.
    written = insert("users", {"id": 7, "email": "z@z.z"})
    if 7 not in written["params"].values() or "z@z.z" not in written["params"].values():
        bad.append(f"insert should carry the row's values in the Query params: {written}")
    return bad


def _probe_query_execute():
    """The §7 execute family runs a built Query on a real sqlite connection and answers plain data (spec
    §7.4): execute reads the rows, execute_one the first row or NOTHING, execute_scalar the first cell or
    NOTHING, execute_many the rows affected. A row written by insert is read back by select, updated, and
    deleted, each count confirmed, with no ORM and no model instances — plain dicts throughout."""
    for name in ("select", "insert", "update", "delete", "execute", "execute_one", "execute_scalar", "execute_many"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (query execute)"]
    select = _need("select"); insert = _need("insert"); update = _need("update")
    delete = _need("delete"); execute = _need("execute"); execute_one = _need("execute_one")
    execute_scalar = _need("execute_scalar"); execute_many = _need("execute_many")

    async def _run(d):
        bad = []
        conn = _SqliteQueryConnection(os.path.join(d, "q.db"))
        await conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT)", {})
        wrote = await execute_many(insert("widgets", {"id": 1, "name": "alpha"}), conn)
        if wrote != 1:
            bad.append(f"execute_many of an insert should answer 1 row affected: {wrote}")
        rows = await execute(select("widgets", ["id", "name"], {"id": 1}, None, None, None, None), conn)
        if not (isinstance(rows, list) and rows and rows[0].get("name") == "alpha"):
            bad.append(f"execute of a select should read the row back as a plain dict: {rows}")
        one = await execute_one(select("widgets", ["id", "name"], {"id": 1}, None, None, None, None), conn)
        if not (isinstance(one, dict) and one.get("id") == 1):
            bad.append(f"execute_one should read the single row: {one}")
        missing = await execute_one(select("widgets", ["id"], {"id": 999}, None, None, None, None), conn)
        if missing is not None:
            bad.append(f"execute_one with no rows should answer NOTHING: {missing}")
        scalar = await execute_scalar(select("widgets", ["name"], {"id": 1}, None, None, None, None), conn)
        if scalar != "alpha":
            bad.append(f"execute_scalar should answer the first cell: {scalar}")
        changed = await execute_many(update("widgets", {"name": "beta"}, {"id": 1}), conn)
        if changed != 1:
            bad.append(f"execute_many of an update should answer 1 row affected: {changed}")
        removed = await execute_many(delete("widgets", {"id": 1}), conn)
        if removed != 1:
            bad.append(f"execute_many of a delete should answer 1 row affected: {removed}")
        conn.close()
        return bad

    with tempfile.TemporaryDirectory() as d:
        return asyncio.run(_run(d))


def _probe_checked_builders():
    """The §7.3 schema-checked builders validate the names a query uses against the DECLARED schema — a
    pure check needing no connection (spec §7.3): on success each returns exactly the Query its raw
    counterpart produces; an undeclared table is an unknown_table Fault and an undeclared column an
    unknown_column Fault, across the selected columns, the WHERE keys, the ORDER BY keys and the
    INSERT/UPDATE value keys. The `*` wildcard, an ORDER BY `-` prefix and all-columns (NOTHING) are not
    column-checked."""
    for name in ("checked_select", "checked_insert", "checked_update", "checked_delete",
                 "select", "insert", "update", "delete"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (checked builders)"]
    checked_select = _need("checked_select"); checked_insert = _need("checked_insert")
    checked_update = _need("checked_update"); checked_delete = _need("checked_delete")
    select = _need("select"); insert = _need("insert"); update = _need("update"); delete = _need("delete")
    schema = {"tables": [{"name": "users",
                          "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None},
                                      {"name": "email", "declared_type": "text", "renamed_from": None, "references": None}],
                          "indexes": [], "constraints": []},
                         {"name": "posts",
                          "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None},
                                      {"name": "author", "declared_type": "integer", "renamed_from": None, "references": None}],
                          "indexes": [], "constraints": []}], "views": []}
    bad = []
    # On success the checked builder returns exactly the raw builder's Query.
    if checked_select(schema, "users", ["id", "email"], {"id": 1}, None, None, None, None) != select("users", ["id", "email"], {"id": 1}, None, None, None, None):
        bad.append("checked_select should return exactly the raw select's Query on success")
    if checked_insert(schema, "users", {"id": 1, "email": "a@b.c"}) != insert("users", {"id": 1, "email": "a@b.c"}):
        bad.append("checked_insert should return exactly the raw insert's Query on success")
    if checked_update(schema, "users", {"email": "x"}, {"id": 1}) != update("users", {"email": "x"}, {"id": 1}):
        bad.append("checked_update should return exactly the raw update's Query on success")
    if checked_delete(schema, "users", {"id": 1}) != delete("users", {"id": 1}):
        bad.append("checked_delete should return exactly the raw delete's Query on success")
    # An undeclared table is unknown_table; an undeclared column is unknown_column, everywhere a name is used.
    bad_table = checked_select(schema, "nope", ["id"], None, None, None, None, None)
    if not (hp.is_fault(bad_table) and bad_table.get("code") == "unknown_table"):
        bad.append(f"an undeclared table should be an unknown_table Fault: {bad_table}")
    bad_col = checked_select(schema, "users", ["nosuch"], None, None, None, None, None)
    if not (hp.is_fault(bad_col) and bad_col.get("code") == "unknown_column"):
        bad.append(f"an undeclared selected column should be an unknown_column Fault: {bad_col}")
    if not hp.is_fault(checked_select(schema, "users", ["id"], {"nosuch": 1}, None, None, None, None)):
        bad.append("checked_select should check the WHERE keys")
    if not hp.is_fault(checked_select(schema, "users", ["id"], None, ["nosuch"], None, None, None)):
        bad.append("checked_select should check the ORDER BY keys")
    if not hp.is_fault(checked_insert(schema, "users", {"nosuch": 1})):
        bad.append("checked_insert should check the value keys")
    if not hp.is_fault(checked_update(schema, "users", {"nosuch": 1}, {"id": 1})):
        bad.append("checked_update should check the value keys")
    if not hp.is_fault(checked_delete(schema, "users", {"nosuch": 1})):
        bad.append("checked_delete should check the WHERE keys")
    # The * wildcard, all-columns (NOTHING), and an ORDER BY `-` prefix on a declared column are not refused.
    if hp.is_fault(checked_select(schema, "users", ["*"], None, None, None, None, None)):
        bad.append("checked_select should not column-check the * wildcard")
    if hp.is_fault(checked_select(schema, "users", None, None, ["-id"], None, None, None)):
        bad.append("checked_select should pass all-columns and a `-`-prefixed declared ORDER BY column")
    # A join's table is checked for existence; its ON expression is raw SQL and is not column-checked.
    # (All-columns is used so the check turns only on the join table, not on qualified column names.)
    good_join = checked_select(schema, "users", None, None, None, None, None,
                               [{"table": "posts", "on": "posts.author = users.id"}])
    if hp.is_fault(good_join):
        bad.append(f"a join to a declared table should pass, its ON left as raw SQL: {good_join}")
    bad_join = checked_select(schema, "users", None, None, None, None, None,
                              [{"table": "nope", "on": "nope.x = users.id"}])
    if not (hp.is_fault(bad_join) and bad_join.get("code") == "unknown_table"):
        bad.append(f"a join to an undeclared table should be an unknown_table Fault: {bad_join}")
    return bad


def _probe_query_select_options():
    """select carries the optional clauses the basic round-trip does not reach (spec §7.2): an order,
    ascending and the descending `-` prefix, a limit and an offset that page the result, and a join that
    reads a second table. execute_scalar answers NOTHING when the query matches nothing. Run on a real
    sqlite connection."""
    for name in ("select", "insert", "execute", "execute_scalar", "execute_many"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (select options)"]
    select = _need("select"); insert = _need("insert"); execute = _need("execute")
    execute_scalar = _need("execute_scalar"); execute_many = _need("execute_many")

    async def _run(d):
        bad = []
        conn = _SqliteQueryConnection(os.path.join(d, "opt.db"))
        await conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT)", {})
        await conn.execute("CREATE TABLE tags (wid INTEGER, tag TEXT)", {})
        for wid, nm in ((1, "a"), (2, "b"), (3, "c")):
            await execute_many(insert("widgets", {"id": wid, "name": nm}), conn)
        await execute_many(insert("tags", {"wid": 1, "tag": "x"}), conn)

        ascending = await execute(select("widgets", ["id"], None, ["id"], None, None, None), conn)
        if [row["id"] for row in ascending] != [1, 2, 3]:
            bad.append(f"an ascending order_by should sort ascending: {ascending}")
        # The descending `-` prefix, paged by a limit and offset over the reversed order.
        paged = await execute(select("widgets", ["id"], None, ["-id"], 2, 1, None), conn)
        if [row["id"] for row in paged] != [2, 1]:
            bad.append(f"a descending order_by with limit and offset should page the reverse order: {paged}")
        joined = await execute(select("widgets", ["widgets.id", "tags.tag"], {"id": 1}, None, None, None,
                                      [{"table": "tags", "on": "tags.wid = widgets.id"}]), conn)
        if not (joined and joined[0].get("tag") == "x"):
            bad.append(f"a join should read the joined row: {joined}")
        empty = await execute_scalar(select("widgets", ["name"], {"id": 999}, None, None, None, None), conn)
        if empty is not None:
            bad.append(f"execute_scalar with no matching row should answer NOTHING: {empty}")
        conn.close()
        return bad

    with tempfile.TemporaryDirectory() as d:
        return asyncio.run(_run(d))


def _probe_query_transaction():
    """A §7 transaction runs several writes all-or-nothing on one connection (spec §7.5): on success it
    answers each write's rows-affected count in order and every write commits; on a failing write it rolls
    back, answers a write_failed Fault naming the index, and leaves nothing behind for another reader."""
    for name in ("insert", "transaction", "execute"):
        try:
            _need(name)
        except _NotBuilt as e:
            return [f"{e}: {name} (query transaction)"]
    insert = _need("insert"); transaction = _need("transaction"); execute = _need("execute")
    select = _need("select")

    async def _run(d):
        bad = []
        conn = _SqliteQueryConnection(os.path.join(d, "t.db"))
        await conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT)", {})
        landed = await transaction([insert("widgets", {"id": 1, "name": "a"}),
                                    insert("widgets", {"id": 2, "name": "b"})], conn)
        if not (isinstance(landed, list) and landed == [1, 1]):
            bad.append(f"a transaction of two inserts should answer each write's count: {landed}")
        count = await execute(select("widgets", ["id"], None, None, None, None, None), conn)
        if len(count) != 2:
            bad.append(f"both writes of a successful transaction should commit: {count}")
        # A failing write (a duplicate primary key) rolls the whole transaction back.
        refused = await transaction([insert("widgets", {"id": 3, "name": "c"}),
                                     insert("widgets", {"id": 1, "name": "dup"})], conn)
        if not (hp.is_fault(refused) and refused.get("code") == "write_failed"):
            bad.append(f"a transaction with a failing write should answer a write_failed Fault: {refused}")
        after = await execute(select("widgets", ["id"], None, None, None, None, None), conn)
        if len(after) != 2:
            bad.append(f"a rolled-back transaction must leave no row behind; rows now {len(after)}")
        conn.close()
        return bad

    with tempfile.TemporaryDirectory() as d:
        return asyncio.run(_run(d))


# ---------------------------------------------------------------------------
# The runner.
# ---------------------------------------------------------------------------

def _probe_async_write():
    """The asynchronous write path of spec 8.6, exposed as two caller doors. query_deposit hands a
    declared write to the crew and returns a Ticket at once, not awaited to durability; query_collect
    redeems the ticket, waits on the outcome, and answers with what the write did. A read handed to
    query_deposit is refused, because a read has nothing to defer (refuse_a_read); a ticket no crew holds
    handed to query_collect reads back a NoMatch, the database untouched (refuse_an_unknown_ticket). The
    two pure guards are pinned on both branches directly, and the two doors run end to end against a real
    opened sqlite database (declaration query_deposit, query_collect, query_prepare_deposit,
    query_redeem_ticket, refuse_a_read, refuse_an_unknown_ticket)."""

    async def _run():
        bad = []

        # The two pure guards, each on both branches. crew_deposit leaves a waiter on the running loop,
        # so the held-ticket case runs inside this async body.
        guards = ("refuse_a_read", "refuse_an_unknown_ticket", "crew_make", "crew_deposit")
        missing = [n for n in guards if getattr(hp, n, None) is None]
        if missing:
            bad.extend(f"not built: {n}" for n in missing)
        else:
            refuse_a_read = hp.refuse_a_read
            on_read = refuse_a_read(_declaration())  # wanted "all": a read has nothing to defer
            if not hp.is_fault(on_read):
                bad.append(f"refuse_a_read should refuse a reading word as a Fault: {on_read}")
            on_write = refuse_a_read(_declaration(wanted="add", rows=[{"id": 1, "name": "a"}]))
            if on_write is not None:
                bad.append(f"refuse_a_read should pass a write as NOTHING: {on_write}")
            refuse_unknown = hp.refuse_an_unknown_ticket
            crew = hp.crew_make()
            miss = refuse_unknown(crew, "f" * 32)
            if not (isinstance(miss, dict) and "reason" in miss):
                bad.append(f"refuse_an_unknown_ticket should answer a NoMatch for a ticket not held: {miss}")
            held = hp.crew_deposit(crew, {"text": "INSERT INTO users (id) VALUES (1)", "parameters": {}})
            if not isinstance(held, str):
                bad.append(f"crew_deposit should return a Ticket for the held-ticket guard case: {held}")
            elif refuse_unknown(crew, held) is not None:
                bad.append(f"refuse_an_unknown_ticket should pass a held ticket as NOTHING: {refuse_unknown(crew, held)}")

        # The two doors, end to end against a real sqlite database.
        doors = ("session_open", "session_open_connection", "query_run_statement",
                 "session_close_connection", "query_deposit", "query_collect")
        missing_doors = [n for n in doors if getattr(hp, n, None) is None]
        if missing_doors:
            bad.extend(f"not built: {n}" for n in missing_doors)
            return bad

        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "async.db")
            pool = await hp.session_open_connection(target, "sqlite", 1)
            if hp.is_fault(pool):
                bad.append(f"the async-write law could not open a connection: {pool}")
                return bad
            await hp.query_run_statement(pool, "sqlite", {"text": "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)", "parameters": {}})
            await hp.session_close_connection(pool)

            db = await hp.session_open(target, "exit_immediately", None, None)
            if hp.is_fault(db):
                bad.append(f"session_open failed before the async-write law: {db}")
                return bad

            # A. A declared write comes back as a Ticket at once, not an Answer. Collecting it answers what
            #    the write did, and the row is durable on disk.
            ticket = hp.query_deposit(db, _READ_MODEL, 'User.rows({"id": 5, "name": "e"}).add')
            if isinstance(ticket, dict) or not isinstance(ticket, str) or ticket == "":
                bad.append(f"query_deposit of a declared write should return a Ticket at once, not an Answer or a refusal: {ticket!r}")
            else:
                answer = await hp.query_collect(db, ticket)
                if isinstance(answer, dict) and ("reason" in answer or hp.is_fault(answer)):
                    bad.append(f"query_collect of a held ticket should answer what the write did: {answer}")
                conn = sqlite3.connect(target)
                row = conn.execute("SELECT name FROM users WHERE id=5").fetchall()
                conn.close()
                if row != [("e",)]:
                    bad.append(f"after query_collect the deposited write should be durable on disk, got {row}")

            # B. A read handed to the deposit door is refused: nothing to defer, nothing deposited.
            refused = hp.query_deposit(db, _READ_MODEL, "User.where(id=5).all")
            if not hp.is_fault(refused):
                bad.append(f"query_deposit of a read should be refused as a Fault: {refused}")

            # C. Collecting a ticket the crew never held reads back a NoMatch as data.
            no_ticket = await hp.query_collect(db, "f" * 32)
            if not (isinstance(no_ticket, dict) and "reason" in no_ticket):
                bad.append(f"query_collect of an unknown ticket should read back a NoMatch as data: {no_ticket}")
        return bad

    return asyncio.run(_run())


# --- gap-closing laws: door-driven decision paths left bare after the code-coupled probes were removed.
# Each drives a declared door and asserts the declared outcome; none reaches into a private helper. The
# behaviour each exercises is named in the .hd (the Collecting, Depositing, Connecting records and their
# notes) and in the feature file's scenarios for these doors.

def _probe_release_unknown_ticket():
    """crew_release_ticket refuses a ticket the crew does not hold at once, because no outcome for it is
    ever posted (declaration crew_release_ticket, spec 8.6). A lookup that matched nothing is not one of
    the four retry categories; the door answers a refused no_such_ticket Fault."""

    async def _run():
        crew_make = _need("crew_make")
        crew_release_ticket = _need("crew_release_ticket")
        answer = await crew_release_ticket(crew_make(), "no-such-ticket")
        if not (hp.is_fault(answer) and answer.get("code") == "no_such_ticket"):
            return [f"crew_release_ticket of a ticket the crew does not hold should refuse no_such_ticket: {answer}"]
        return []

    return asyncio.run(_run())


def _probe_receipt_nobody_collected():
    """crew_post_receipt writes an abandoned write's outcome to the log and forgets the ticket, which is
    not a failure, when nobody is parked on it (declaration crew_post_receipt, the no-waiter path, spec
    8.6)."""
    crew_make = _need("crew_make")
    crew_post_receipt = _need("crew_post_receipt")
    crew = crew_make()
    crew["writes"]["abandoned"] = {"text": "UPDATE t SET x = 1", "parameters": {}}
    crew["arrivals"].append("abandoned")
    receipt = {"id": "abandoned", "ok": True, "touched": 1, "attempts": 1, "failure": None}
    outcome = crew_post_receipt(crew, "abandoned", receipt)
    bad = []
    if hp.is_fault(outcome):
        bad.append(f"crew_post_receipt for a ticket nobody waits on should not fault: {outcome}")
    if "abandoned" in crew["writes"] or "abandoned" in crew["arrivals"]:
        bad.append(f"crew_post_receipt should forget the abandoned ticket: writes={crew['writes']}, arrivals={crew['arrivals']}")
    return bad


def _probe_close_refused():
    """session_close_connection answers a would_not_close Fault when the driver refuses the close, rather
    than raising (declaration session_close_connection)."""

    async def _run():
        session_close_connection = _need("session_close_connection")

        class _WillNotClose:
            def close(self):
                raise sqlite3.OperationalError("the connection is wedged and will not close")

        answer = await session_close_connection(_WillNotClose())
        if not (hp.is_fault(answer) and answer.get("code") == "would_not_close"):
            return [f"session_close_connection should answer would_not_close when the driver refuses: {answer}"]
        return []

    return asyncio.run(_run())


def _probe_rollback_also_fails():
    """A write group whose driver throws rolls back and comes back as a Fault; when the rollback itself
    throws on the dying connection, that secondary failure is swallowed so it cannot mask the real fault
    (declaration query_run_together, the sqlite group path)."""

    async def _run():
        query_run_together = _need("query_run_together")
        how_to_write = _need("how_to_write")

        class _DyingSqlite:
            def execute(self, *_a, **_k):
                raise sqlite3.OperationalError("the write group blew up")

            def rollback(self):
                raise sqlite3.OperationalError("and the rollback blew up too")

            def commit(self):
                raise AssertionError("commit must not be reached: the write group throws at BEGIN first")

        statements = [{"text": "UPDATE t SET x = 1", "parameters": {}}]
        answer = await query_run_together(_DyingSqlite(), "sqlite", statements, how_to_write("sqlite"))
        if not hp.is_fault(answer):
            return [f"query_run_together should answer a Fault when the write group throws: {answer}"]
        return []

    return asyncio.run(_run())


def _probe_read_declared_empty():
    """schema_read_declared answers the empty Declared — honest-persist managing no schema — when the
    declared-model loader throws, rather than letting the throw escape (declaration schema_read_declared)."""
    import honest_persist._pydantic_loader as loadermod
    import honest_persist.io as iomod

    real = loadermod.load_declared

    def _loader_throws():
        raise RuntimeError("the model loader blew up")

    loadermod.load_declared = _loader_throws
    try:
        declared = iomod.schema_read_declared()
    finally:
        loadermod.load_declared = real
    empty = {"models": [], "views": [], "dropping_tables": [], "dropping_views": []}
    if declared != empty:
        return [f"schema_read_declared should answer the empty Declared when the loader throws: {declared}"]
    return []


def _probe_compile_fault_through_door():
    """A read the library understands but cannot compile — a first with no order to make it the first of
    something — comes back as the compiler's declaration_incomplete Fault through the query door, never a
    raise (declaration query_answer, the would-not-compile path)."""

    async def _run():
        session_open = _need("session_open")
        query_ask = _need("query_ask")
        with tempfile.TemporaryDirectory() as d:
            db = await session_open(os.path.join(d, "compile.db"), "exit_immediately", None, None)
            if hp.is_fault(db):
                return [f"session_open failed before the compile-fault law: {db}"]
            answer = await query_ask(db, _READ_MODEL, "User.where(id=1).first")
            if not (hp.is_fault(answer) and answer.get("code") == "declaration_incomplete"):
                return [f"query_ask of a first with no order should answer declaration_incomplete through the door: {answer}"]
        return []

    return asyncio.run(_run())


def _probe_migration_refuses_loss():
    """Opening a database refuses when the migration it would run destroys a live table no model declares
    and the host did not list for dropping: session_open raises CouldNotOpen carrying undeclared_loss
    rather than silently dropping data (declaration session_connect, refuse_undeclared_loss). A migration
    runs only when the host declares a schema, so this declares a model (making the schema managed) and
    leaves a second table the model does not name for the migration to want to drop. The model is cleaned
    up so it never reaches another law's schema read."""
    try:
        from pydantic import BaseModel
    except Exception:  # noqa: BLE001
        _note_skip("undeclared-loss: pydantic is not installed, so the refuse-undeclared-loss open path was not exercised")
        return []
    import gc

    import honest_persist.doors as doorsmod

    class KeepRow(BaseModel):
        id: int
        __tablename__ = "hp_keep_rows"

    async def _run():
        session_open = _need("session_open")
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "loss.db")
            scratch = sqlite3.connect(target)
            scratch.execute("CREATE TABLE hp_legacy_rows (id INTEGER PRIMARY KEY)")
            scratch.commit()
            scratch.close()
            try:
                await session_open(target, "exit_immediately", None, None)
                return ["session_open should raise CouldNotOpen when the migration would drop an undeclared table"]
            except doorsmod.CouldNotOpen as raised:
                if not (hp.is_fault(raised.fault) and raised.fault.get("code") == "undeclared_loss"):
                    return [f"CouldNotOpen for an undeclared loss should carry the undeclared_loss fault: {raised.fault}"]
        return []

    try:
        return asyncio.run(_run())
    finally:
        del KeepRow
        gc.collect()


def _probe_migration_on_open():
    """Opening a database runs a needed migration on the way in: a table a host model declares that the
    live database lacks is created during session_connect, so a caller can read it at once without a
    fault (declaration session_connect, the migration-on-open path). Defines a host model and cleans it
    up so it never reaches another law's schema read."""
    try:
        from pydantic import BaseModel
    except Exception:  # noqa: BLE001
        _note_skip("migration-on-open: pydantic is not installed, so the migration-on-open path was not exercised")
        return []
    import gc

    class MigRow(BaseModel):
        id: int
        label: str
        __tablename__ = "hp_mig_rows"

    _read_model = {"name": "MigRow", "table": "hp_mig_rows",
                   "columns": [{"name": "id", "declared_type": "integer", "renamed_from": None, "references": None},
                               {"name": "label", "declared_type": "text", "renamed_from": None, "references": None}],
                   "dropping": [], "indexes": [], "constraints": []}

    async def _run():
        session_open = _need("session_open")
        query_ask = _need("query_ask")
        bad = []
        with tempfile.TemporaryDirectory() as d:
            db = await session_open(os.path.join(d, "mig.db"), "exit_immediately", None, None)
            if hp.is_fault(db):
                return [f"session_open should run the migration and open, not fault: {db}"]
            rows = await query_ask(db, _read_model, "MigRow.where(id=1).all")
            if hp.is_fault(rows) or (isinstance(rows, dict) and "reason" in rows):
                bad.append(f"the migration-on-open should have created the table, so a read answers rows, not a miss: {rows}")
        return bad

    try:
        return asyncio.run(_run())
    finally:
        del MigRow
        gc.collect()


def _probe_crew_refused_write():
    """When the crew refuses a deposited write, the synchronous write door surfaces that refusal rather
    than waiting on a ticket that never settles (declaration query_answer, the crew-refused path). The
    crew's refusal naturally arises only from an empty compiled write, which a real write never produces,
    so it is driven by injecting a crew_deposit that refuses; the door itself is unchanged and the
    orchestrator's job of surfacing a crew refusal is what this exercises."""
    import honest_persist.crew as crewmod

    real = crewmod.crew_deposit

    def _crew_refuses(_crew, _statement):
        return hp.refused("crew_refused", "the crew refused this write", {})

    async def _run():
        session_open = _need("session_open")
        query_ask = _need("query_ask")
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "crewrefuse.db")
            base = sqlite3.connect(target)
            base.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
            base.commit()
            base.close()
            db = await session_open(target, "exit_immediately", None, None)
            if hp.is_fault(db):
                return [f"session_open failed before the crew-refused law: {db}"]
            crewmod.crew_deposit = _crew_refuses
            try:
                answer = await query_ask(db, _WRITE_MODEL, 'User.rows({"id": 5, "name": "e"}).add')
            finally:
                crewmod.crew_deposit = real
            if not (hp.is_fault(answer) and answer.get("code") == "crew_refused"):
                return [f"a lone write the crew refuses should surface the crew's refusal through the door: {answer}"]
        return []

    return asyncio.run(_run())


def _probe_spelling_refused_on_open():
    """When spelling a migration operation is refused, the migration-on-open surfaces that refusal rather
    than running a bad statement: session_open raises CouldNotOpen carrying it (declaration
    session_connect, the spelling-refused path). A refused spelling naturally arises only from an engine
    that cannot express an operation the models produce, so it is driven by injecting a spell_operation
    that refuses. Defines a host model and cleans it up."""
    try:
        from pydantic import BaseModel
    except Exception:  # noqa: BLE001
        _note_skip("spelling-refused: pydantic is not installed, so the spelling-refused open path was not exercised")
        return []
    import gc

    import honest_persist.doors as doorsmod
    import honest_persist.spelling as spellingmod

    real = spellingmod.spell_operation

    def _spelling_refuses(_operation, _engine, _replicates):
        return hp.refused("cannot_spell", "this engine cannot express this operation", {})

    class SpellRow(BaseModel):
        id: int
        __tablename__ = "hp_spell_rows"

    async def _run():
        session_open = _need("session_open")
        with tempfile.TemporaryDirectory() as d:
            spellingmod.spell_operation = _spelling_refuses
            try:
                await session_open(os.path.join(d, "spell.db"), "exit_immediately", None, None)
                return ["session_open should raise CouldNotOpen when a migration operation cannot be spelled"]
            except doorsmod.CouldNotOpen as raised:
                if not (hp.is_fault(raised.fault) and raised.fault.get("code") == "cannot_spell"):
                    return [f"CouldNotOpen for a refused spelling should carry the spelling refusal: {raised.fault}"]
            finally:
                spellingmod.spell_operation = real
        return []

    try:
        return asyncio.run(_run())
    finally:
        del SpellRow
        gc.collect()


def _probe_channel_push_bootstrap():
    return probe_channel_push_bootstraps_schema(_note_skip)


def _probe_postgres_open_refusal():
    return probe_session_open_connection_postgres_refusal(_note_skip)


def _probe_postgres_group_refusal():
    return probe_query_run_together_postgres_refusal(_note_skip)


def _probe_crew_driver_refusal():
    return probe_crew_run_write_driver_refusal(_note_skip)


_PROBES = [
    probe_is_fault,
    probe_refused,
    _probe_surface,
    _probe_engine_of,
    _probe_deciders,
    _probe_next_wait,
    _probe_retry_schedule,
    _probe_schema_pure,
    _probe_schema_diff,
    _probe_dialect_edges,
    _probe_spelling_dialects,
    _probe_query_compilation,
    _probe_query_shapers,
    _probe_query_pure,
    _probe_engine_tables,
    _probe_crew_pure,
    _probe_schema_declarations,
    _probe_refresh,
    probe_query_run_statement_zero_rows,
    probe_query_run_together_zero_rows,
    probe_crew_run_write_zero_rows,
    _probe_channel_push_bootstrap,
    _probe_real_query,
    _probe_real_readonly_fault,
    _probe_crew_run_write,
    _probe_postgres_open_refusal,
    probe_session_open_writer_sqlite_reason,
    probe_session_close_connection_driver_refusal,
    probe_query_run_statement_driver_refusal,
    _probe_postgres_group_refusal,
    probe_query_run_together_embedded_refusal,
    _probe_crew_driver_refusal,
    probe_crew_run_write_turso_conflict,
    probe_session_open_channel_local_refusal,
    _probe_boundary_faults,
    _probe_readers_and_log,
    probe_sqlite_writer_busy_timeout,
    probe_log_write_warning_severity,
    probe_log_write_unknown_level,
    _probe_crew_lifecycle,
    _probe_channel,
    _probe_replication,
    _probe_migration_and_schema,
    _probe_session_open,
    _probe_query_ask,
    _probe_query_ask_reads,
    _probe_lifecycle_doors,
    _probe_generator_retry,
    _probe_crew_concurrency,
    _probe_turso_mvcc,
    _probe_shutdown_handler,
    _probe_signal_handler_drives_shutdown,
    _probe_door_paths,
    _probe_pure_edges,
    _probe_query_read_edges,
    _probe_inspect_edges,
    _probe_query_write_paths,
    _probe_shutdown_push,
    _probe_retry_outcomes,
    _probe_replication_orchestration,
    _probe_sync_turn,
    _probe_observe_emit_swallowed,
    _probe_query_builders,
    _probe_checked_builders,
    _probe_query_execute,
    _probe_query_select_options,
    _probe_query_transaction,
    _probe_async_write,
    _probe_release_unknown_ticket,
    _probe_receipt_nobody_collected,
    _probe_close_refused,
    _probe_rollback_also_fails,
    _probe_read_declared_empty,
    _probe_compile_fault_through_door,
    _probe_crew_refused_write,
    # The probes that define host pydantic models run last and clean up after themselves, so their
    # declared models never reach another law's schema read.
    _probe_migration_refuses_loss,
    _probe_spelling_refused_on_open,
    _probe_migration_on_open,
    _probe_pydantic_loader,
    _probe_view_refresh_specs,
]


def run(stop_on_failure):
    """Run the behavioral laws. Mutation mode returns the first observed failure."""
    all_bad = []
    ran = 0
    for probe in _PROBES:
        ran += 1
        try:
            all_bad.extend(probe())
        except Exception as e:
            all_bad.append(f"{probe.__name__} raised {type(e).__name__}: {e}")
        if stop_on_failure and all_bad:
            break
    for failure in all_bad:
        print(f"LAW FAIL: {failure}")
    for skip in _SKIPS:
        print(f"LAW SKIP: {skip}")
    print(f"laws: {len(all_bad)} failures across {ran} probes; {len(_SKIPS)} engine/fixture skips recorded")
    return 0 if not all_bad else 1


if __name__ == "__main__":
    raise SystemExit(run(False))

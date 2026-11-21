"""The output I/O boundaries, and the three low readers that touch the platform.

This is the pure core's only contact with the outside: it opens connections, runs statements, inspects a
live schema, reads the clock and the disk, writes the log, and pushes and pulls a replication channel.
Ported from declaro-persistum; the sqlite driver uses the standard library's own synchronous sqlite3
inside each async boundary (honest-persist depends on honest-type alone, not aiosqlite), and the
postgresql and turso rows import their optional drivers lazily. Binding reads the placeholder style off
the statement text: a `:name` statement binds the parameters mapping, a `?`/`$n` statement binds the
values positionally, which lets one boundary take both a compiler's statement and a hand-written one.
"""

import pathlib
import sqlite3
import time

from honest_persist._util import _pick, _read_or
from honest_persist.types import fault, is_fault, no_match, refused

NOTHING = None
_THREE_ENGINES = ("sqlite", "postgresql", "turso")


def _path_in(target):
    """Where the database lives on disk, out of the target the caller gave."""
    _head, separator, rest = target.partition("://")
    return _pick(separator == "://", lambda: rest.removeprefix("/"), lambda: target)


def _bind(statement):
    """The values to hand the driver, in the shape the statement's placeholders need: the parameters
    mapping for a `:name` statement, the values positionally for a `?`/`$n` statement."""
    params = statement["parameters"]
    text = statement["text"]
    named = bool(params) and all(f":{key}" in text for key in params)
    return _pick(named, lambda: params, lambda: list(params.values()))


# --- clock_read, copy_on_disk, log_write (declaration) -----------------------------------------------
def clock_read():
    """Ask the clock what time it is (declaration clock_read); monotonic, because every caller measures
    a duration and wall time runs backwards when a machine syncs."""
    return time.monotonic()


def copy_on_disk(target):
    """Whether a copy of the database is already there (declaration copy_on_disk): the calling program
    cannot know, so the library looks. It makes nothing and remembers nothing."""
    return pathlib.Path(_path_in(target)).is_file()


import logging  # noqa: E402

_LOG = logging.getLogger("honest_persist")
_NAMED_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING,
                 "error": logging.ERROR, "critical": logging.CRITICAL}
_LEVELS = {None: logging.INFO, **_NAMED_LEVELS}

_as_words = lambda facts: " ".join(f"{name}={value}" for name, value in facts.items())


def log_write(event):
    """Write one event where an operator reads it afterwards (declaration log_write); a failure never
    travels here. An event is facts, not a sentence: one dict whose values are a string, a number, a
    bool or nothing, so there is no exception in the vocabulary."""
    named = {"level": None, **event}["level"]
    recognised = named in _LEVELS
    _LOG.log(_LEVELS[_pick(recognised, lambda: named, lambda: "error")], _as_words(event))
    return NOTHING


# --- session_open_connection (declaration) -----------------------------------------------------------
_could_not_open = lambda target, said: refused(
    "could_not_reach",
    f"the database at {target} could not be opened. The driver said: {type(said).__name__}: {said}",
    {"target": target})


async def _no_engine_driver(*_args):
    """The no-match row for a per-engine driver dispatch (P16). Reached only if a driver dispatcher is
    entered with an engine word its table holds no row for, which the caller's `engine in <table>` guard
    prevents, so it is a program bug reported as a refused Fault value rather than a bare KeyError."""
    return refused("no_such_engine", "a driver dispatch was reached with an engine word it holds no row for", {})


def _open_sqlite(target, _connections):
    path = _path_in(target)
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode = WAL").fetchone()
    return conn


def _open_postgresql(target, connections):
    import asyncpg  # type: ignore[import-not-found]

    return asyncpg.create_pool(target, min_size=1, max_size=connections)


def _open_turso(target, _connections):
    import turso.aio  # type: ignore[import-not-found]

    return turso.aio.connect(_path_in(target))


_OPEN = {"sqlite": _open_sqlite, "postgresql": _open_postgresql, "turso": _open_turso}


async def _await_it(value):
    return await value


async def _keep_it(value):
    return value


_AWAITABLE = {True: _await_it, False: _keep_it}


async def _maybe_await(value):
    """A sqlite connection is a plain object; a pool or a turso connection is a coroutine or awaitable."""
    return await _AWAITABLE[hasattr(value, "__await__")](value)


_no_connection_permitted = lambda target, connections: refused(
    "no_connection_permitted",
    f"this database may hold {connections} connections, so there is none left to read "
    f"{target} on; state a bound of at least one", {"connections": connections})


async def session_open_connection(target, engine, connections):
    """Ask the driver for the connection reads run on (declaration session_open_connection). The engine
    is handed over, settled from the target before anything opened; a failure comes back as a value."""
    return await _PERMITS_ONE[connections >= 1](target, engine, connections)


async def _ask_driver(target, engine, connections):
    try:  # honest: ignore HC-P002: the connection boundary catches the driver's throw and returns it as a could_not_reach Fault value (P08)
        opened = _read_or(_OPEN, engine, lambda: None)(target, connections)
        return await _maybe_await(opened)
    except Exception as unreachable:  # noqa: BLE001
        return _could_not_open(target, unreachable)


async def _refuse_bound(target, _engine, connections):
    return _no_connection_permitted(target, connections)


_PERMITS_ONE = {True: _ask_driver, False: _refuse_bound}


# --- session_open_writer (declaration) ---------------------------------------------------------------
_open_sqlite_writer = lambda target: sqlite3.connect(_path_in(target), isolation_level=None, timeout=0)


def _open_postgresql_writer(target):
    import asyncpg  # type: ignore[import-not-found]

    return asyncpg.connect(target)


def _open_turso_writer(target):
    import turso.aio  # type: ignore[import-not-found]

    return turso.aio.connect(_path_in(target))


_OPEN_WRITER = {"sqlite": _open_sqlite_writer, "postgresql": _open_postgresql_writer, "turso": _open_turso_writer}


async def _prepare_as_opened(writer):
    """The default writer-prep (P16 no-match row by default): sqlite and postgresql writers are handed
    back exactly as opened, with no extra step."""
    return writer


async def _prepare_turso_writer(writer):
    """Turn MVCC on, once, before the turso writer is handed back: it runs PRAGMA journal_mode = 'mvcc'
    and reads the cursor, because an unread PRAGMA cursor does nothing on turso. Without it the writer's
    BEGIN CONCURRENT is refused outright. This is the write mode only, separate from master-to-slave
    replication, so it never touches the sync channel."""
    cursor = writer.cursor()
    await cursor.execute("PRAGMA journal_mode = 'mvcc'")
    await cursor.fetchone()
    return writer


_PREPARE_WRITER = {"turso": _prepare_turso_writer}


async def session_open_writer(target, engine):
    """Open one drainer's connection, held for its life (declaration session_open_writer). A turso writer
    also has MVCC turned on here, once, before it is handed back; sqlite and postgresql writers are
    returned as opened."""
    try:
        opened = _read_or(_OPEN_WRITER, engine, lambda: None)(target)
        writer = await _maybe_await(opened)
        return await _read_or(_PREPARE_WRITER, engine, lambda: _prepare_as_opened)(writer)
    except Exception as stopped:  # noqa: BLE001
        return refused("writer_would_not_open",
                       f"no drainer could be opened on the {engine} target {target}: "
                       f"{type(stopped).__name__}: {stopped}", {"engine": engine, "target": target})


# --- session_close_connection (declaration) ----------------------------------------------------------
async def session_close_connection(connection):
    """Close one connection (declaration session_close_connection). A connection already shut closes
    again quietly; a close the driver refuses comes back as a Fault."""
    try:
        await _maybe_await(connection.close())
    except Exception as said:  # noqa: BLE001
        return refused("would_not_close",
                       f"a connection would not close. The driver said: {type(said).__name__}: {said}", {})
    return NOTHING


# --- query_run_statement (declaration), the one I/O boundary spec 8.5 instruments --------------------
def _rows_from(cursor):
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


_refused_statement = lambda said: refused("statement_refused", f"the engine refused the statement: {said}", {})

_cursor_answer = lambda cursor: _pick(
    cursor.description is not None, lambda: _rows_from(cursor), lambda: max(int(cursor.rowcount), 0))


async def _on_sqlite_statement(connection, statement):
    try:  # honest: ignore HC-P002: the statement boundary catches the sqlite driver's throw and returns it as a statement_refused Fault value (P08)
        cursor = connection.execute(statement["text"], _bind(statement))
        answer = _cursor_answer(cursor)
        connection.commit()
        return answer
    except sqlite3.Error as said:
        return _refused_statement(said)


async def _on_postgresql_statement(connection, statement):
    import asyncpg  # type: ignore[import-not-found]

    try:  # honest: ignore HC-P002: the statement boundary catches the postgresql driver's throw and returns it as a statement_refused Fault value (P08)
        async with connection.acquire() as held:
            prepared = await held.prepare(statement["text"])
            return await _POSTGRESQL_ANSWER[prepared.get_attributes() != ()](held, prepared, statement)
    except asyncpg.PostgresError as said:
        return _refused_statement(said)


async def _postgresql_rows(_held, prepared, statement):
    return [dict(record) for record in await prepared.fetch(*list(statement["parameters"].values()))]


async def _postgresql_count(held, _prepared, statement):
    tag = await held.execute(statement["text"], *list(statement["parameters"].values()))
    counted = tag.rpartition(" ")[2]
    return int({True: counted, False: "0"}[counted.isdigit()])


_POSTGRESQL_ANSWER = {True: _postgresql_rows, False: _postgresql_count}


async def _on_turso_statement(connection, statement):
    import turso  # type: ignore[import-not-found]

    try:  # honest: ignore HC-P002: the statement boundary catches the turso driver's throw and returns it as a statement_refused Fault value (P08)
        cursor = connection.cursor()
        await cursor.execute(statement["text"], list(statement["parameters"].values()))
        answer = await _TURSO_ANSWER[cursor.description is not None](cursor)
        await connection.commit()
        return answer
    except turso.Error as said:
        return _refused_statement(said)


async def _turso_rows(cursor):
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in await cursor.fetchall()]


async def _turso_count(cursor):
    return max(int(cursor.rowcount), 0)


_TURSO_ANSWER = {True: _turso_rows, False: _turso_count}

_RUN_STATEMENT = {"sqlite": _on_sqlite_statement, "postgresql": _on_postgresql_statement, "turso": _on_turso_statement}

_no_statement_engine = lambda engine: refused(
    "no_such_engine",
    f"no engine here is called {engine!r}, so there is no driver to put this statement to",
    {"accepted": list(_THREE_ENGINES), "arrived": engine})


def _emit_query(connection, engine, statement, rows_or_count, nanoseconds):
    """Emit hf.persist.query through the honest-observe.emit seam (spec 8.5), best-effort: a failure to
    emit is swallowed and never fails the query, and it is a no-op when observe is off."""
    try:  # honest: ignore HC-P002: emitting through the honest-observe seam is best-effort (spec 8.5); a failure is a no-op and never fails the query, and it is a no-op when observe is off
        from honest_observe import emit

        emit("hf.persist.query", {"engine": engine, "sql_hash": hash(statement["text"]),
                                  "duration_ns": nanoseconds})
    except Exception:  # noqa: BLE001
        return NOTHING
    return NOTHING


async def query_run_statement(connection, engine, statement):
    """Run one statement on the connection it is handed (declaration query_run_statement), and answer the
    rows a read returned or the count a write touched. This is execute, the one I/O boundary spec 8.5
    instruments: after every statement it emits hf.persist.query through honest-observe.emit, best-effort
    and a no-op when observe is off."""
    began = time.monotonic_ns()
    answer = await _WHEN_STATEMENT_ENGINE[engine in _RUN_STATEMENT](connection, engine, statement)
    _emit_query(connection, engine, statement, answer, time.monotonic_ns() - began)
    return answer


async def _run_statement(connection, engine, statement):
    return await _read_or(_RUN_STATEMENT, engine, lambda: _no_engine_driver)(connection, statement)


async def _refuse_statement_engine(_connection, engine, _statement):
    return _no_statement_engine(engine)


_WHEN_STATEMENT_ENGINE = {True: _run_statement, False: _refuse_statement_engine}


# --- query_run_together (declaration) ----------------------------------------------------------------
def _rollback_quiet(connection):
    try:  # honest: ignore HC-P002: a rollback on a connection with nothing to roll back is a no-op, so the quiet boundary returns NOTHING either way (P08)
        connection.rollback()
    except sqlite3.Error:
        return NOTHING
    return NOTHING


async def _on_sqlite_together(writer, statements, _transacting):
    try:  # honest: ignore HC-P002: the group boundary catches the sqlite driver's throw, rolls back, and returns it as a group_refused Fault value (P08)
        writer.execute("BEGIN")
        counted = [max(int(writer.execute(one["text"], _bind(one)).rowcount), 0) for one in statements]
        writer.commit()
        return sum(counted)
    except sqlite3.Error as said:
        _rollback_quiet(writer)
        return refused("group_refused",
                       f"the engine refused one of the {len(statements)} statements this group asked to "
                       f"land together: {said}", {})


async def _on_postgresql_together(writer, statements, _transacting):
    import asyncpg  # type: ignore[import-not-found]

    try:  # honest: ignore HC-P002: the group boundary catches the postgresql driver's throw and returns it as a group_refused Fault value (P08)
        async with writer.acquire() as held, held.transaction():
            tags = [await held.execute(one["text"], *list(one["parameters"].values())) for one in statements]
        return sum(int({True: t.rpartition(" ")[2], False: "0"}[t.rpartition(" ")[2].isdigit()]) for t in tags)
    except asyncpg.PostgresError as said:
        return refused("group_refused", f"the engine refused one of the group: {said}", {})


async def _on_turso_together(writer, statements, _transacting):
    import turso  # type: ignore[import-not-found]

    async def _turso_touched(cursor, one):
        """Run one statement of a group on the open cursor and answer the rows it touched, never below zero."""
        await cursor.execute(one["text"], list(one["parameters"].values()))
        return max(int(cursor.rowcount), 0)

    try:  # honest: ignore HC-P002: the group boundary catches the turso driver's throw, rolls back, and returns it as a group_refused Fault value (P08)
        cursor = writer.cursor()
        await cursor.execute("BEGIN")
        counted = [await _turso_touched(cursor, one) for one in statements]
        await writer.commit()
        return sum(counted)
    except turso.Error as said:
        await writer.rollback()
        return refused("group_refused", f"the engine refused one of the group: {said}", {})


_RUN_TOGETHER = {"sqlite": _on_sqlite_together, "postgresql": _on_postgresql_together, "turso": _on_turso_together}


async def query_run_together(writer, engine, statements, transacting):
    """Run several writes as one transaction on one writer (declaration query_run_together), the only
    rollback there is; answer the rows affected or a Fault, rolling the whole transaction back."""
    return await _WHEN_TOGETHER_ENGINE[engine in _RUN_TOGETHER](writer, engine, statements, transacting)


async def _run_together(writer, engine, statements, transacting):
    return await _read_or(_RUN_TOGETHER, engine, lambda: _no_engine_driver)(writer, statements, transacting)


async def _refuse_together_engine(_writer, engine, statements, _transacting):
    return refused("no_such_engine",
                   f"no engine here is called {engine!r}, so there is no driver to put these "
                   f"{len(statements)} statements to", {"accepted": list(_THREE_ENGINES), "arrived": engine})


_WHEN_TOGETHER_ENGINE = {True: _run_together, False: _refuse_together_engine}


# --- crew_run_write (declaration crew_run_write, spec 7.7) -------------------------------------------
_as_driver_fault = lambda category, statement, said: fault(
    "write_" + category, f"the engine {category} the write {statement['text']!r}: {said}",
    category, [], {"driver": str(said)})

_commit_if = lambda writer, commits: _pick(commits, lambda: writer.commit(), lambda: NOTHING)


async def _on_sqlite_write(writer, statement, transacting):
    def _sqlite_kind(said):
        named = str(getattr(said, "sqlite_errorname", ""))
        lost = named.startswith("SQLITE_BUSY") or named.startswith("SQLITE_LOCKED")
        return _pick(lost, lambda: "conflict", lambda: "refused")

    try:  # honest: ignore HC-P002: the write boundary catches the sqlite driver's throw, rolls back, and returns it as a typed conflict-or-refused Fault value (P08, spec 7.7)
        writer.execute(transacting["begin"])
        cursor = writer.execute(statement["text"], _bind(statement))
        touched = max(int(cursor.rowcount), 0)
        _commit_if(writer, transacting["commits"])
        return touched
    except sqlite3.Error as said:
        _rollback_quiet(writer)
        return _as_driver_fault(_sqlite_kind(said), statement, said)


async def _on_postgresql_write(writer, statement, _transacting):
    import asyncpg  # type: ignore[import-not-found]

    try:  # honest: ignore HC-P002: the write boundary catches the postgresql driver's throw and returns it as a typed conflict-or-refused Fault value (P08, spec 7.7)
        async with writer.transaction():
            tag = await writer.execute(statement["text"], *list(statement["parameters"].values()))
        counted = tag.rpartition(" ")[2]
        return int({True: counted, False: "0"}[counted.isdigit()])
    except asyncpg.PostgresError as said:
        lost = isinstance(said, asyncpg.SerializationError | asyncpg.DeadlockDetectedError)
        return _as_driver_fault(_pick(lost, lambda: "conflict", lambda: "refused"), statement, said)


async def _on_turso_write(writer, statement, transacting):
    import turso  # type: ignore[import-not-found]

    try:  # honest: ignore HC-P002: the write boundary catches the turso driver's throw, rolls back, and returns it as a typed conflict-or-refused Fault value (P08, spec 7.7)
        cursor = writer.cursor()
        await cursor.execute(transacting["begin"])
        await cursor.execute(statement["text"], list(statement["parameters"].values()))
        touched = max(int(cursor.rowcount), 0)
        await _maybe_await(_commit_if(writer, transacting["commits"]))
        return touched
    except turso.Error as said:
        await writer.rollback()
        lost = "Write-write conflict" in str(said) or "SQLITE_BUSY" in str(said)
        return _as_driver_fault(_pick(lost, lambda: "conflict", lambda: "refused"), statement, said)


_RUN_WRITE = {"sqlite": _on_sqlite_write, "postgresql": _on_postgresql_write, "turso": _on_turso_write}


async def crew_run_write(writer, engine, statement, transacting):
    """Run one write the way the engine needs it (declaration crew_run_write), and answer a WriteOutcome:
    the rows it affected, or the driver's Fault when the write itself was refused. An engine with no
    driver row answers a NoMatch before any write is put to a driver, so the retry schedule never sees
    it: no retry reaches a missing driver row."""
    return await _WHEN_WRITE_ENGINE[engine in _RUN_WRITE](writer, engine, statement, transacting)


async def _run_write(writer, engine, statement, transacting):
    return await _read_or(_RUN_WRITE, engine, lambda: _no_engine_driver)(writer, statement, transacting)


async def _no_driver(_writer, engine, _statement, _transacting):
    return no_match("engines", [engine], list(_THREE_ENGINES), "no_row_for_the_key", f"engine {engine!r}")


_WHEN_WRITE_ENGINE = {True: _run_write, False: _no_driver}


# --- channel_push, channel_pull, session_open_channel (declaration) ----------------------------------
async def channel_push(channel):
    """Send local commits to the primary (declaration channel_push). On a new channel it is the first
    call: it proves the driver built its sync half, sends whatever is local, and on an empty copy brings
    the primary's whole schema down."""
    try:
        await channel.push()
    except Exception as said:  # noqa: BLE001
        return refused("push_refused", f"local commits could not be sent: {type(said).__name__}: {said}", {})
    return NOTHING


async def channel_pull(channel):
    """Bring down what the primary has and this copy does not (declaration channel_pull)."""
    try:
        await channel.pull()
    except Exception as said:  # noqa: BLE001
        return refused("pull_refused", f"nothing could be brought down: {type(said).__name__}: {said}", {})
    return NOTHING


async def session_open_channel(target, primary, token):
    """Open the one line to the primary, held for the life of the database (declaration
    session_open_channel). It makes the folder first, because the driver takes a path and will not make
    the directory around it."""
    path = _path_in(target)
    try:
        import turso.aio.sync  # type: ignore[import-not-found]

        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        return turso.aio.sync.connect(path, primary, auth_token=token, bootstrap_if_empty=True)
    except Exception as said:  # noqa: BLE001
        return refused("channel_would_not_open",
                       f"the channel for {path} could not be opened: {type(said).__name__}: {said}",
                       {"path": path, "primary": primary})


# --- schema_read_declared (declaration) --------------------------------------------------------------
def schema_read_declared():
    """Ask the code which models and views it declares (declaration schema_read_declared). The host
    declares its models by importing its own modules and calling honest-persist's `field` in their class
    bodies; this reads the live register. A host that declared no models answers an empty Declared, which
    is the honest answer when honest-persist is managing no schema."""
    return _read_declared_models()


def _read_declared_models():
    try:  # honest: ignore HC-P002: the declared-models reader catches the loader's throw and answers the empty Declared, the honest answer when honest-persist is managing no schema
        from honest_persist._pydantic_loader import load_declared

        return load_declared()
    except Exception:  # noqa: BLE001
        return {"models": [], "views": [], "dropping_tables": [], "dropping_views": []}


# --- schema_inspect (declaration) --------------------------------------------------------------------
from honest_persist._inspect import schema_inspect  # noqa: E402,F401

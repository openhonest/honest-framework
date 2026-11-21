"""A real PostgreSQL for the conformance suite (section 9.1).

The spec's testing rule is a real database with no mocks (spec section 8.6): the SQLite path already
runs against a real in-memory SQLite, and PostgreSQL must be no different. PostgreSQL has no
in-memory mode, so this fixture provisions a real server: it prefers one already running locally, and
if none is reachable it spins up a throwaway cluster with initdb + pg_ctl on a temporary datadir and
unix socket, tearing it down at exit. `postgres_connection()` returns a connection to a clean test
database adapted to persist's duck-typed boundary, or None when no PostgreSQL can be provisioned at
all (no server and no postgres binaries) — the one case where the PostgreSQL probes cannot run.

Conformance fixtures are not linted, so the psycopg adapter class lives here rather than in src.
"""

import atexit
import os
import re
import shutil
import subprocess
import tempfile

import psycopg
from psycopg.rows import dict_row

# Provisioning is done once per suite run and cached: {"admin_dsn": ...} once a server is found or a
# cluster is started, or {"unavailable": reason} when neither is possible.
_STATE = {}

# persist's queries use :name placeholders (SQLite pyformat); psycopg wants %(name)s.
_NAMED_PARAM = re.compile(r":(\w+)")


def _pg_binary(name):
    """The path to a PostgreSQL server binary, from PATH or a known install location, or None."""
    found = shutil.which(name)
    if found:
        return found
    bases = ("/opt/homebrew/opt/postgresql@17/bin", "/opt/homebrew/bin", "/usr/local/bin",
             "/usr/lib/postgresql/17/bin", "/usr/lib/postgresql/16/bin", "/usr/bin")
    for base in bases:
        candidate = os.path.join(base, name)
        if os.path.exists(candidate):
            return candidate
    return None


def _running_server_dsn():
    """An admin DSN for a PostgreSQL server already running locally, or None."""
    for dsn in ("dbname=postgres", "host=/tmp dbname=postgres", "host=localhost dbname=postgres"):
        try:
            psycopg.connect(dsn, connect_timeout=2).close()
            return dsn
        except Exception:
            continue
    return None


def _start_cluster():
    """Spin up a throwaway PostgreSQL cluster and return its admin DSN, or None if the binaries are
    not installed. The socket lives under /tmp so its path stays inside the 103-byte limit."""
    initdb, pg_ctl = _pg_binary("initdb"), _pg_binary("pg_ctl")
    if not initdb or not pg_ctl:
        return None
    datadir = tempfile.mkdtemp(prefix="hp_pgdata_")
    socket = tempfile.mkdtemp(prefix="hpg", dir="/tmp")
    subprocess.run([initdb, "-D", datadir, "--no-locale", "--encoding=UTF8", "-A", "trust"], check=True, capture_output=True)
    subprocess.run([pg_ctl, "-D", datadir, "-o", f"-k {socket} -h ''", "-l", os.path.join(datadir, "log"), "-w", "start"], check=True, capture_output=True)
    _STATE["cluster_dir"] = datadir
    _STATE["socket"] = socket
    return f"host={socket} dbname=postgres"


@atexit.register
def _teardown():
    """Stop and delete the throwaway cluster, if this run started one."""
    if "cluster_dir" in _STATE:
        pg_ctl = _pg_binary("pg_ctl")
        if pg_ctl:
            subprocess.run([pg_ctl, "-D", _STATE["cluster_dir"], "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(_STATE["cluster_dir"], ignore_errors=True)
        shutil.rmtree(_STATE.get("socket", ""), ignore_errors=True)


def _admin_dsn():
    """A DSN to a provisioned PostgreSQL server (running or throwaway), or None if none is possible."""
    if "admin_dsn" in _STATE:
        return _STATE["admin_dsn"]
    if "unavailable" in _STATE:
        return None
    dsn = _running_server_dsn() or _start_cluster()
    if dsn is None:
        _STATE["unavailable"] = "no running PostgreSQL and no postgres binaries"
        return None
    _STATE["admin_dsn"] = dsn
    return dsn


class PostgresConn:
    """A real psycopg connection adapted to persist's duck-typed boundary (section 7.4): async execute
    to {rows, rowcount} with dict rows. Autocommit, because apply issues DDL statement by statement and
    never opens a transaction on PostgreSQL (it has no reconstruction path). :name placeholders are
    translated to psycopg's %(name)s."""

    def __init__(self, dsn):
        self._conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)

    async def execute(self, sql, params=None):
        if params:
            cursor = self._conn.execute(_NAMED_PARAM.sub(r"%(\1)s", sql), params)
        else:
            cursor = self._conn.execute(sql)
        rows = cursor.fetchall() if cursor.description else []
        return {"rows": rows, "rowcount": cursor.rowcount}

    # Manual transaction control in autocommit mode, so the transaction() path can be exercised.
    async def begin(self):
        self._conn.execute("BEGIN")

    async def commit(self):
        self._conn.execute("COMMIT")

    async def rollback(self):
        self._conn.execute("ROLLBACK")

    def close(self):
        self._conn.close()


def postgres_connection():
    """A connection to a clean, empty PostgreSQL test database, or None when no PostgreSQL is available
    at all. A dedicated database is dropped and recreated so a developer's own data is never touched."""
    dsn = _admin_dsn()
    if dsn is None:
        return None
    # A per-process database name so parallel test runners (e.g. the mutation gate's workers) never
    # collide on the same DROP/CREATE against a shared server.
    name = f"honest_persist_conformance_{os.getpid()}"
    admin = psycopg.connect(dsn, autocommit=True)
    admin.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
    admin.execute(f"CREATE DATABASE {name}")
    admin.close()
    return PostgresConn(dsn.replace("dbname=postgres", f"dbname={name}"))


# A per-call counter so each postgres_target() gets its own clean database within one process.
_TARGET_COUNT = {"n": 0}


def _host_of(dsn):
    """The host= value out of a libpq keyword DSN, or None for the default socket."""
    for field in dsn.split():
        if field.startswith("host="):
            return field[len("host="):]
    return None


def _asyncpg_url(name, dsn):
    """A postgresql:// URL asyncpg accepts for the database `name`, carrying the admin DSN's host so a
    throwaway cluster on a unix socket is reached as well as a default local server."""
    host = _host_of(dsn)
    if host is None:
        return f"postgresql:///{name}"
    if host.startswith("/"):
        return f"postgresql:///{name}?host={host}"
    return f"postgresql://{host}/{name}"


def postgres_target():
    """A real PostgreSQL target string persist's own opener (asyncpg) connects to, naming a clean, empty
    test database, or None when no PostgreSQL is available. This is what exercises persist's postgresql
    driver rows against a real server: the laws hand it to session_open_connection / session_open_writer
    exactly as a caller would, rather than a pre-built adapter. The database is dropped and recreated so a
    developer's own data is never touched, and dropped again at process exit."""
    dsn = _admin_dsn()
    if dsn is None:
        return None
    _TARGET_COUNT["n"] += 1
    name = f"honest_persist_target_{os.getpid()}_{_TARGET_COUNT['n']}"
    admin = psycopg.connect(dsn, autocommit=True)
    admin.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
    admin.execute(f"CREATE DATABASE {name}")
    admin.close()
    _STATE.setdefault("targets", []).append(name)
    return _asyncpg_url(name, dsn)


@atexit.register
def _drop_targets():
    """Drop every test database postgres_target() created in this process."""
    dsn = _STATE.get("admin_dsn")
    if dsn is None:
        return
    admin = psycopg.connect(dsn, autocommit=True)
    for name in _STATE.get("targets", []):
        admin.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
    admin.close()

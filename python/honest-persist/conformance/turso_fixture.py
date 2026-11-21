"""A real Turso (pyturso) connection for the conformance suite (section 9.1).

Turso is a ground-up, SQLite-compatible rewrite still in beta, so this adapter does not assume it is
1:1 with SQLite — it handles the differences that surfaced against the real engine (verified July 2026
against pyturso and the project's COMPAT.md):

  - Rows come back as tuples, not dict rows, so they are zipped with the cursor description here.
  - pyturso auto-opens a transaction like sqlite3, so the connection is put in autocommit
    (isolation_level=None) for the reconstruction's explicit BEGIN/COMMIT to run as issued.
  - PRAGMA foreign_key_check is unsupported, so the reconstruction's foreign-key verification (section
    5.5) is done here by an explicit orphan query per declared foreign key instead.

Turso is in-process and in-memory, so no server is needed. Conformance fixtures are not linted.
"""

try:
    import turso
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


class TursoConn:
    """A real pyturso connection adapted to persist's duck-typed boundary (section 7.4): async execute
    to {rows, rowcount} with dict rows, plus the reconstruction lifecycle (section 5.5). Because Turso
    has no PRAGMA foreign_key_check, verify_foreign_keys checks each declared foreign key for orphan
    child rows directly."""

    def __init__(self):
        self._conn = turso.connect(":memory:", isolation_level=None)

    async def execute(self, sql, params=None):
        cursor = self._conn.cursor()
        cursor.execute(sql, params) if params else cursor.execute(sql)
        columns = [description[0] for description in (cursor.description or [])]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()] if columns else []
        return {"rows": rows, "rowcount": cursor.rowcount}

    async def begin(self):
        self._conn.cursor().execute("BEGIN")

    async def commit(self):
        self._conn.cursor().execute("COMMIT")

    async def rollback(self):
        self._conn.cursor().execute("ROLLBACK")

    async def disable_foreign_keys(self):
        self._conn.cursor().execute("PRAGMA foreign_keys = OFF")

    async def enable_foreign_keys(self):
        self._conn.cursor().execute("PRAGMA foreign_keys = ON")

    async def verify_foreign_keys(self):
        # Turso has no PRAGMA foreign_key_check (unlike SQLite), so find orphan child rows for each
        # declared foreign key by hand — a child value that points at no parent row.
        violations = []
        tables = await self.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
        for table_row in tables["rows"]:
            table = table_row["name"]
            foreign_keys = await self.execute("PRAGMA foreign_key_list(" + table + ")")
            for fk in foreign_keys["rows"]:
                orphan = await self.execute(
                    f"SELECT 1 FROM {table} WHERE {fk['from']} IS NOT NULL AND NOT EXISTS "
                    f"(SELECT 1 FROM {fk['table']} WHERE {fk['table']}.{fk['to']} = {table}.{fk['from']}) LIMIT 1"
                )
                if orphan["rows"]:
                    violations.append({"table": table, "column": fk["from"]})
        return violations

    def close(self):
        self._conn.close()


def turso_connection():
    """A real in-memory Turso connection, or None when pyturso is not installed."""
    return TursoConn() if _AVAILABLE else None


# --- the real cloud primary, for the replication round trip (section 5.5, declaration channel_push) ---
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402

_TEST_DATABASE = "honest-persist-test"


class TursoKeyMissing(Exception):
    """Raised when TURSO_KEY is nowhere to be found. The replication law tests a real primary, so a
    missing platform token is a loud failure, never a silent skip."""


def _turso_platform_key():
    """The Turso platform API token (TURSO_KEY), from the environment or ~/dev/.env, raising if neither
    holds it. The value is never printed and never returned to a caller — only used to drive the CLI."""
    key = os.environ.get("TURSO_KEY")
    if key:
        return key
    env_path = os.path.expanduser("~/dev/.env")
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped.startswith("TURSO_KEY="):
                    return stripped[len("TURSO_KEY="):].strip().strip('"').strip("'")
    raise TursoKeyMissing(
        "TURSO_KEY is set in neither the environment nor ~/dev/.env; the replication law needs the "
        "Turso platform token to reach the real primary and will not silently skip")


def _turso_binary():
    """The turso CLI path, from PATH or the default install location, or None when it is not installed."""
    return shutil.which("turso") or (
        "/Users/adam/.turso/turso" if os.path.isfile("/Users/adam/.turso/turso") else None)


def _run_turso(binary, key, args):
    """Run the turso CLI with the platform key in the environment, returning its stdout. The key is passed
    only through TURSO_API_TOKEN in the child environment, never on the command line or in output."""
    env = dict(os.environ)
    env["TURSO_API_TOKEN"] = key
    done = subprocess.run([binary, *args], capture_output=True, text=True, env=env, check=True)
    return done.stdout.strip()


# Cached across the suite run: the resolved primary once reached, or a transient-network reason.
_PRIMARY = {}


def turso_replica_config():
    """The real Turso primary's `{url, token}` for the replication round trip, deriving both from
    TURSO_KEY by way of the turso CLI, or `{unavailable: reason}` only for a genuine transient network
    failure reaching the platform. A missing TURSO_KEY raises (TursoKeyMissing): the law is to test the
    real primary, not to skip it. The minted database token is a short-lived credential used to open the
    channel in-process; it is never printed. The turso CLI not being installed also raises, for the same
    reason a missing key does — the test cannot honestly run without it."""
    if "url" in _PRIMARY or "unavailable" in _PRIMARY:
        return _PRIMARY
    key = _turso_platform_key()
    binary = _turso_binary()
    if binary is None:
        raise TursoKeyMissing(
            "the turso CLI is not installed (no `turso` on PATH and none at ~/.turso/turso); the "
            "replication law needs it to reach the real primary")
    try:
        url = _run_turso(binary, key, ["db", "show", _TEST_DATABASE, "--url"])
        token = _run_turso(binary, key, ["db", "tokens", "create", _TEST_DATABASE])
    except subprocess.CalledProcessError as failed:
        # Distinguish a transient network failure (tolerated, recorded) from a real misconfiguration by
        # the CLI's own words; a network reach failure is the one case the law may record and move past.
        said = (failed.stderr or "").lower()
        transient = "network" in said or "timeout" in said or "connection" in said or "dns" in said
        if transient:
            _PRIMARY["unavailable"] = f"transient network failure reaching the Turso platform: {said.strip()[:200]}"
            return _PRIMARY
        raise
    _PRIMARY["url"] = url
    _PRIMARY["token"] = token
    return _PRIMARY

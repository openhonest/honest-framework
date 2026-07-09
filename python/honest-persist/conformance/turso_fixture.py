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

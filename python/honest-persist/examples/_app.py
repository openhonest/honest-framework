"""Shared parts of the loader worked examples: a SQLite connection adapter and the todo demo.

Both pydantic_todo.py and django_todo.py build the same Schema from idiomatic models, then call
run_todo_demo with it. The demo is identical because honest-persist sees only the Schema dict — the
loader it came from leaves no trace. This file is adopter code, not framework code: it uses an
ordinary class for the connection adapter, exactly the kind of thing honest-check does not police
outside the framework's own source.
"""

import json
import sqlite3

from honest_persist import execute, insert, migrate, select, update


class SqliteConn:
    """A minimal async adapter over an in-memory sqlite3 database — the single I/O seam an adopter
    supplies (section 8.1.1). honest-persist imports no database driver; this connection is yours."""

    def __init__(self):
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row

    async def execute(self, sql, params=None):
        cursor = self._conn.execute(sql, params or {})
        return {"rows": [dict(row) for row in cursor.fetchall()], "rowcount": cursor.rowcount}


async def run_todo_demo(schema):
    """Migrate a loaded todo schema to SQLite and exercise it: add and complete todos through the
    pure query builders, then watch the enum foreign key refuse an undeclared status."""
    print("1. Schema loaded from the models:")
    print(json.dumps(schema, indent=2))

    conn = SqliteConn()
    await conn.execute("PRAGMA foreign_keys = ON")
    applied = await migrate(schema, conn, "sqlite")
    print(f"\n2. Migrated: {applied['ok']['operations_applied']} operations.")
    print("   The Literal/choices status compiled to the lookup table _hp_enum_todos_status,")
    print("   seeded with its allowed values and enforced by a foreign key.")

    for title in ("write the spec", "ship the loaders"):
        await execute(insert("todos", {"title": title, "status": "open"}), conn)
    await execute(update("todos", {"status": "done"}, {"title": "write the spec"}), conn)

    print("\n3. Todos after adding two and completing one:")
    for row in await execute(select("todos"), conn):
        print(f"   #{row['id']} [{row['status']}] {row['title']}")

    print("\n4. An undeclared status is refused by the enum's foreign key:")
    try:
        await execute(insert("todos", {"title": "broken", "status": "archived"}), conn)
        print("   ERROR: the undeclared status was accepted")
    except Exception as error:
        print(f"   rejected: {type(error).__name__}")

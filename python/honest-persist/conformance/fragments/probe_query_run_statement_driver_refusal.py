# scenario: query_run_statement runs one statement on the connection it is handed and emits an event
# inherits: hd=python/honest-persist/honest-persist.hd::query_run_statement -> feature=specs/features/honest-persist.feature::query_run_statement runs one statement on the connection it is handed and emits an event

import asyncio
import sqlite3

import honest_persist as hp


def probe_query_run_statement_driver_refusal():
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE widgets (id INTEGER)")
        statement = {"text": "SELECT unknown_column FROM widgets", "parameters": {}}
        result = asyncio.run(hp.query_run_statement(connection, "sqlite", statement))
        if not hp.is_fault(result) or result.get("code") != "statement_refused":
            return [f"expected the actual SQLite statement refusal, got {result!r}"]
        message = result["message"].casefold()
        if "statement" not in message or "unknown_column" not in message:
            return [f"the statement fault did not explain the refused unknown column: {result!r}"]
        return []
    finally:
        connection.close()

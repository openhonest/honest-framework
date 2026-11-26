# scenario: query_run_together runs several writes as one transaction
# inherits: hd=python/honest-persist/honest-persist.hd::query_run_together -> feature=specs/features/honest-persist.feature::query_run_together runs several writes as one transaction

import asyncio

import honest_persist as hp
from postgres_fixture import postgres_target


def probe_query_run_together_postgres_refusal(note_skip):
    target = postgres_target()
    if target is None:
        note_skip("PostgreSQL group refusal: private fixture server unavailable")
        return []

    async def run():
        writer = await asyncio.wait_for(hp.session_open_connection(target, "postgresql", 1), 3)
        if hp.is_fault(writer):
            return [f"could not open the private PostgreSQL database: {writer!r}"]
        try:
            build = {"text": "CREATE TABLE widgets (id INTEGER PRIMARY KEY, required_value TEXT NOT NULL)", "parameters": {}}
            no_op = {"text": "UPDATE widgets SET required_value = 'unused' WHERE id = 1", "parameters": {}}
            result = await hp.query_run_together(writer, "postgresql", [build, no_op], hp.how_to_write("postgresql"))
            if result != 0:
                return [f"DDL and an unmatched update in a PostgreSQL group should touch zero rows: {result!r}"]
            writes = [
                {"text": "INSERT INTO widgets VALUES (1, 'first')", "parameters": {}},
                {"text": "INSERT INTO widgets VALUES (2, NULL)", "parameters": {}},
            ]
            fault = await hp.query_run_together(writer, "postgresql", writes, hp.how_to_write("postgresql"))
            rows = await hp.query_run_statement(writer, "postgresql", {
                "text": "SELECT id FROM widgets", "parameters": {},
            })
            failures = []
            if not hp.is_fault(fault) or fault.get("code") != "group_refused":
                failures.append(f"expected the real PostgreSQL group refusal, got {fault!r}")
            elif "required_value" not in fault["message"].casefold():
                failures.append(f"the group fault did not identify the failed required-value write: {fault!r}")
            if rows != []:
                failures.append(f"the group failure did not roll back the earlier write: {rows!r}")
            return failures
        finally:
            await asyncio.wait_for(hp.session_close_connection(writer), 3)

    return asyncio.run(run())

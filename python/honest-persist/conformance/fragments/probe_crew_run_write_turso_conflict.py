# scenario: crew_run_write runs one write the way the engine needs it
# inherits: hd=python/honest-persist/honest-persist.hd::crew_run_write -> feature=specs/features/honest-persist.feature::crew_run_write runs one write the way the engine needs it

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import honest_persist as hp


def probe_crew_run_write_turso_conflict():
    async def run():
        with TemporaryDirectory() as directory:
            target = str(Path(directory) / "race.db")
            first = await hp.session_open_writer(target, "turso")
            if hp.is_fault(first):
                return [f"could not open Turso writer: {first!r}"]
            try:
                for text in (
                    "CREATE TABLE widgets (id INTEGER PRIMARY KEY, amount INTEGER)",
                    "INSERT INTO widgets VALUES (1, 0)",
                ):
                    built = await hp.query_run_statement(first, "turso", {"text": text, "parameters": {}})
                    if hp.is_fault(built):
                        return [f"could not set up the private Turso table: {built!r}"]
                second = await hp.session_open_writer(target, "turso")
                if hp.is_fault(second):
                    return [f"could not open competing Turso writer: {second!r}"]
                try:
                    cursor = first.cursor()
                    await cursor.execute("BEGIN CONCURRENT")
                    await cursor.execute("UPDATE widgets SET amount = 1 WHERE id = 1")
                    competing = {"text": "UPDATE widgets SET amount = 2 WHERE id = 1", "parameters": {}}
                    outcome = await asyncio.wait_for(
                        hp.crew_run_write(second, "turso", competing, hp.how_to_write("turso")), 3,
                    )
                    await first.commit()
                    rows = await hp.query_run_statement(second, "turso", {
                        "text": "SELECT amount FROM widgets WHERE id = 1", "parameters": {},
                    })
                    if not hp.is_fault(outcome) or outcome.get("category") != "conflict":
                        return [f"same-row competing Turso write should yield conflict, got {outcome!r}"]
                    if rows != [{"amount": 1}]:
                        return [f"the losing Turso write replaced the winning commit: {rows!r}"]
                    return []
                finally:
                    await hp.session_close_connection(second)
            finally:
                await hp.session_close_connection(first)

    return asyncio.run(run())

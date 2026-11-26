# scenario: crew_run_write runs one write the way the engine needs it
# inherits: hd=python/honest-persist/honest-persist.hd::crew_run_write -> feature=specs/features/honest-persist.feature::crew_run_write runs one write the way the engine needs it

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import honest_persist as hp


def probe_crew_run_write_zero_rows():
    """A real write matching no row returns exactly zero."""
    async def run():
        failures = []
        with TemporaryDirectory() as directory:
            for engine in ("sqlite", "turso"):
                target = str(Path(directory) / f"{engine}.db")
                writer = await hp.session_open_writer(target, engine)
                if hp.is_fault(writer):
                    failures.append(f"{engine}: could not open the real writer: {writer!r}")
                    continue
                try:
                    built = await hp.query_run_statement(writer, engine, {
                        "text": "CREATE TABLE widgets (id INTEGER PRIMARY KEY, value INTEGER)",
                        "parameters": {},
                    })
                    if hp.is_fault(built):
                        failures.append(f"{engine}: could not create widgets: {built!r}")
                        continue
                    statement = {"text": "UPDATE widgets SET value = 2 WHERE id = 1", "parameters": {}}
                    actual = await hp.crew_run_write(writer, engine, statement, hp.how_to_write(engine))
                    if actual != 0:
                        failures.append(f"{engine}: expected zero rows touched, got {actual!r}")
                    missed = await hp.crew_run_write(writer, "mysql", statement, hp.how_to_write(engine))
                    expected = {"table": "engines", "looked_for": ["mysql"], "reason": "no_row_for_the_key"}
                    if (
                        not hp.is_no_match(missed)
                        or {key: missed.get(key) for key in expected} != expected
                        or sorted(missed.get("rows", [])) != ["postgresql", "sqlite", "turso"]
                    ):
                        failures.append(f"unknown engine must report all three available driver rows: {missed!r}")
                finally:
                    await hp.session_close_connection(writer)
        return failures

    return asyncio.run(run())

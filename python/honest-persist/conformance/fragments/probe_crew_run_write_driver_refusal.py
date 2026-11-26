# scenario: crew_run_write runs one write the way the engine needs it
# inherits: hd=python/honest-persist/honest-persist.hd::crew_run_write -> feature=specs/features/honest-persist.feature::crew_run_write runs one write the way the engine needs it

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import honest_persist as hp
from postgres_fixture import postgres_target


def probe_crew_run_write_driver_refusal(note_skip):
    async def run():
        failures = []
        with TemporaryDirectory() as directory:
            engines = [(name, str(Path(directory) / f"{name}.db")) for name in ("sqlite", "turso")]
            postgresql = postgres_target()
            if postgresql is None:
                note_skip("PostgreSQL crew write refusal: private fixture server unavailable")
            else:
                engines.append(("postgresql", postgresql))
            for engine, target in engines:
                setup = await hp.session_open_connection(target, engine, 1)
                if hp.is_fault(setup):
                    failures.append(f"{engine}: could not open the private setup connection: {setup!r}")
                    continue
                try:
                    build = {"text": "CREATE TABLE widgets (id INTEGER PRIMARY KEY, required_value TEXT NOT NULL)", "parameters": {}}
                    built = await hp.query_run_statement(setup, engine, build)
                finally:
                    await hp.session_close_connection(setup)
                if hp.is_fault(built):
                    failures.append(f"{engine}: could not create the private widget table: {built!r}")
                    continue
                writer = await hp.session_open_writer(target, engine)
                if hp.is_fault(writer):
                    failures.append(f"{engine}: could not open a private writer: {writer!r}")
                    continue
                try:
                    statement = {"text": "INSERT INTO widgets VALUES (1, NULL)", "parameters": {}}
                    fault = await hp.crew_run_write(writer, engine, statement, hp.how_to_write(engine))
                    if not hp.is_fault(fault) or fault.get("category") != "refused":
                        failures.append(f"{engine}: NOT NULL rejection should be a logical refusal, got {fault!r}")
                    elif "write" not in fault["message"].casefold() or "required_value" not in fault["message"].casefold():
                        failures.append(f"{engine}: the refusal did not identify the write and required value: {fault!r}")
                finally:
                    await hp.session_close_connection(writer)
        return failures

    return asyncio.run(run())

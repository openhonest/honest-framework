# scenario: query_run_together runs several writes as one transaction
# inherits: hd=python/honest-persist/honest-persist.hd::query_run_together -> feature=specs/features/honest-persist.feature::query_run_together runs several writes as one transaction

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import honest_persist as hp


def probe_query_run_together_embedded_refusal():
    async def run():
        failures = []
        with TemporaryDirectory() as directory:
            for engine in ("sqlite", "turso"):
                target = str(Path(directory) / f"{engine}.db")
                writer = await hp.session_open_writer(target, engine)
                if hp.is_fault(writer):
                    failures.append(f"{engine}: could not open the private writer: {writer!r}")
                    continue
                try:
                    build = {"text": "CREATE TABLE widgets (id INTEGER PRIMARY KEY, required_value TEXT NOT NULL)", "parameters": {}}
                    if hp.is_fault(await hp.query_run_statement(writer, engine, build)):
                        failures.append(f"{engine}: could not create the private widget table")
                        continue
                    writes = [
                        {"text": "INSERT INTO widgets VALUES (1, 'first')", "parameters": {}},
                        {"text": "INSERT INTO widgets VALUES (2, NULL)", "parameters": {}},
                    ]
                    fault = await hp.query_run_together(writer, engine, writes, hp.how_to_write(engine))
                    rows = await hp.query_run_statement(writer, engine, {"text": "SELECT id FROM widgets", "parameters": {}})
                    if not hp.is_fault(fault) or fault.get("code") != "group_refused":
                        failures.append(f"{engine}: expected real group_refused, got {fault!r}")
                    elif not all(word in fault["message"].casefold() for word in ("group", "required_value")):
                        failures.append(f"{engine}: fault did not identify the group and failed required-value write: {fault!r}")
                    if rows != []:
                        failures.append(f"{engine}: group failure did not roll back the first write: {rows!r}")
                finally:
                    await hp.session_close_connection(writer)
        return failures

    return asyncio.run(run())

# scenario: query_run_together runs several writes as one transaction
# inherits: hd=python/honest-persist/honest-persist.hd::query_run_together -> feature=specs/features/honest-persist.feature::query_run_together runs several writes as one transaction

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import honest_persist as hp


def probe_query_run_together_zero_rows():
    """A real write matching no row returns exactly zero."""
    async def run():
        failures = []
        with TemporaryDirectory() as directory:
            for engine in ('sqlite', 'turso'):
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
                    second = {"text": "UPDATE widgets SET value = 3 WHERE id = 2", "parameters": {}}
                    actual = await hp.query_run_together(writer, engine, [statement, second], hp.how_to_write(engine))
                    if actual != 0:
                        failures.append(f"{engine}: expected zero rows touched, got {actual!r}")
                finally:
                    await hp.session_close_connection(writer)
        return failures

    return asyncio.run(run())

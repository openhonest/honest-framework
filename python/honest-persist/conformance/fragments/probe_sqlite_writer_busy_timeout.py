# scenario: session_open_writer opens a SQLite writer with no driver busy wait
# inherits: hd=python/honest-persist/honest-persist.hd::session_open_writer -> feature=specs/features/honest-persist.feature::session_open_writer opens a SQLite writer with no driver busy wait

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from honest_persist import is_fault, session_close_connection, session_open_writer


def probe_sqlite_writer_busy_timeout():
    async def check():
        with TemporaryDirectory() as directory:
            target = str(Path(directory) / "writer.sqlite")
            writer = await session_open_writer(target, "sqlite")
            if is_fault(writer):
                return [f"SQLite drainer writer failed to open: {writer!r}"]
            try:
                observed = writer.execute("PRAGMA busy_timeout").fetchone()
                return [] if observed == (0,) else [f"SQLite drainer busy wait was {observed!r}, expected (0,) milliseconds"]
            finally:
                await session_close_connection(writer)

    return asyncio.run(check())

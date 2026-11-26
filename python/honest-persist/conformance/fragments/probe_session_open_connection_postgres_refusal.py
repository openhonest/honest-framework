# scenario: session_open_connection asks the driver for a connection
# inherits: hd=python/honest-persist/honest-persist.hd::session_open_connection -> feature=specs/features/honest-persist.feature::session_open_connection asks the driver for a connection

import asyncio
from urllib.parse import urlsplit

import honest_persist as hp
from postgres_fixture import postgres_target


def probe_session_open_connection_postgres_refusal(note_skip):
    target = postgres_target()
    if target is None:
        note_skip("PostgreSQL open refusal: private fixture server unavailable")
        return []
    selected = urlsplit(target)
    missing = selected._replace(path=f"{selected.path}_uncreated").geturl()

    async def run():
        opened = await asyncio.wait_for(hp.session_open_connection(missing, "postgresql", 1), 3)
        if hp.is_fault(opened):
            return []
        await asyncio.wait_for(hp.session_close_connection(opened), 3)
        return ["the live PostgreSQL server refused the absent database; open should return a Fault"]

    return asyncio.run(run())

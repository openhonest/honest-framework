# scenario: channel_push sends local commits to the primary
# inherits: hd=python/honest-persist/honest-persist.hd::channel_push -> feature=specs/features/honest-persist.feature::channel_push sends local commits to the primary

import asyncio
import secrets
from pathlib import Path
from tempfile import TemporaryDirectory

import honest_persist as hp
import turso
from turso_fixture import turso_local_primary, turso_replica_config


async def _first_push_bootstrap(config):
    failures = []
    table = "hp_bootstrap_" + secrets.token_hex(8)
    with TemporaryDirectory() as directory:
        root = Path(directory)
        producer = await hp.session_open_channel(str(root / "producer.db"), config["url"], config["token"])
        if hp.is_fault(producer):
            return [f"could not open producer channel: {producer!r}"]
        published = False
        try:
            initial = await asyncio.wait_for(hp.channel_push(producer), 4)
            if hp.is_fault(initial):
                return [f"could not connect producer to the primary: {initial!r}"]
            cursor = producer.cursor()
            async with asyncio.timeout(4):
                await cursor.execute(f"CREATE TABLE {table} (marker TEXT NOT NULL)")
                await cursor.execute(f"INSERT INTO {table} VALUES ('producer-origin')")
                await producer.commit()
            pushed = await asyncio.wait_for(hp.channel_push(producer), 4)
            if hp.is_fault(pushed):
                return [f"producer could not publish its schema and marker: {pushed!r}"]
            published = True

            reader = await hp.session_open_channel(str(root / "reader.db"), config["url"], config["token"])
            if hp.is_fault(reader):
                return [f"could not open fresh reader channel: {reader!r}"]
            try:
                pushed = await asyncio.wait_for(hp.channel_push(reader), 4)
                if hp.is_fault(pushed):
                    return [f"first push on the fresh reader refused: {pushed!r}"]
                reader_cursor = reader.cursor()
                try:
                    async with asyncio.timeout(4):
                        await reader_cursor.execute(f"SELECT marker FROM {table}")
                        rows = await reader_cursor.fetchall()
                except turso.DatabaseError as error:
                    return [f"first push did not bring down the producer schema: {error}"]
                if rows != [("producer-origin",)]:
                    failures.append(f"first push did not bring down the producer row: {rows!r}")
            finally:
                await asyncio.wait_for(hp.session_close_connection(reader), 3)
        finally:
            try:
                if published:
                    cleanup = producer.cursor()
                    async with asyncio.timeout(4):
                        await cleanup.execute(f"DROP TABLE {table}")
                        await producer.commit()
                        removed = await hp.channel_push(producer)
                    if hp.is_fault(removed):
                        failures.append(f"could not drop the private producer table: {removed!r}")
            finally:
                closed = await asyncio.wait_for(hp.session_close_connection(producer), 3)
                if hp.is_fault(closed):
                    failures.append(f"could not close the producer channel: {closed!r}")
    return failures


def probe_channel_push_bootstraps_schema(note_skip):
    with turso_local_primary() as local:
        if local is not None:
            return asyncio.run(_first_push_bootstrap(local))
    config = turso_replica_config()
    if "unavailable" in config:
        note_skip(f"first-push bootstrap: {config['unavailable']}")
        return []
    return asyncio.run(_first_push_bootstrap(config))

# scenario: session_close_connection answers would_not_close when the driver refuses the close
# inherits: hd=python/honest-persist/honest-persist.hd::session_close_connection -> feature=specs/features/honest-persist.feature::session_close_connection answers would_not_close when the driver refuses the close

import asyncio
import sqlite3

import honest_persist as hp


def probe_session_close_connection_driver_refusal():
    connection = sqlite3.connect(":memory:")

    def close_on_worker():
        try:
            connection.close()
        except sqlite3.ProgrammingError as error:
            return str(error), asyncio.run(hp.session_close_connection(connection))
        return "", None

    async def close_from_another_thread():
        return await asyncio.to_thread(close_on_worker)

    try:
        driver_reason, result = asyncio.run(close_from_another_thread())
        if not driver_reason:
            return ["the real SQLite driver did not refuse the cross-thread close"]
        if not hp.is_fault(result) or result.get("code") != "would_not_close":
            return [f"expected the real SQLite close refusal as would_not_close, got {result!r}"]
        if driver_reason not in result["message"]:
            return [f"the close fault did not convey the SQLite driver reason: {result!r}"]
        return []
    finally:
        connection.close()

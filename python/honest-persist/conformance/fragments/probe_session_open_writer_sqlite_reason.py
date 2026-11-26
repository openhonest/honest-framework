# scenario: session_open_writer reports the SQLite driver reason for a missing parent directory
# inherits: hd=python/honest-persist/honest-persist.hd::session_open_writer -> feature=specs/features/honest-persist.feature::session_open_writer reports the SQLite driver reason for a missing parent directory

import asyncio
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

import honest_persist as hp


def probe_session_open_writer_sqlite_reason():
    with TemporaryDirectory() as directory:
        target = str(Path(directory) / "absent" / "test.db")
        try:
            connection = sqlite3.connect(target)
        except sqlite3.Error as error:
            driver_reason = str(error)
        else:
            connection.close()
            return ["expected the real SQLite driver to refuse an absent parent directory"]

        result = asyncio.run(hp.session_open_writer(target, "sqlite"))
        if not hp.is_fault(result) or result["code"] != "writer_would_not_open":
            return [f"expected writer_would_not_open for {target}, got {result!r}"]

        message = result["message"]
        failures = []
        if "sqlite" not in message.casefold() or target not in message:
            failures.append(f"writer fault did not identify SQLite and the requested target: {message!r}")
        if driver_reason.casefold() not in message.casefold():
            failures.append(f"writer fault omitted the SQLite reason {driver_reason!r}: {message!r}")
        return failures

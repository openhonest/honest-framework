# scenario: write_registered_type returns a refused insert reason without ending the transaction
# inherits: hd=python/honest-alerts/honest-alerts.hd::write_registered_type -> feature=specs/features/honest-alerts.feature::write_registered_type returns a refused insert reason without ending the transaction
import sqlite3

from honest_alerts import write_registered_type
from laws_write_registered_type import _fresh_conn


async def probe_write_registered_type_insert_refused():
    """Carry the driver's reason as data and leave the caller's transaction intact."""
    conn, table = _fresh_conn()
    registration = {"message_type": "approval.requested", "message_versions": ["v1"]}
    reason = "registry insert refused by SQLite"
    marker = ("system.marker", '["v1"]')
    failures = []
    try:
        conn.execute(
            f"CREATE TRIGGER deny_registration BEFORE INSERT ON {table} "
            f"WHEN new.message_type = 'approval.requested' BEGIN SELECT RAISE(ABORT, '{reason}'); END"
        )
        conn.execute("BEGIN")
        conn.execute(f"INSERT INTO {table} (message_type, message_versions) VALUES (?, ?)", marker)
        try:
            outcome = await write_registered_type(registration, conn)
        except sqlite3.IntegrityError as exc:
            failures.append(f"write_registered_type raised IntegrityError({str(exc)!r}), expected a refusal record")
        else:
            expected = {"ok": False, "reason": reason}
            if outcome != expected or outcome["ok"] is not False:
                failures.append(f"write_registered_type returned {outcome!r}, expected {expected!r}")

        rows = conn.execute(f"SELECT message_type, message_versions FROM {table}").fetchall()
        if not conn.in_transaction or rows != [marker]:
            failures.append(
                f"writer left transaction open={conn.in_transaction!r} with rows {rows!r}; "
                f"expected an open transaction containing only caller marker {marker!r}"
            )
        conn.rollback()
        rows_after_caller_rollback = conn.execute(f"SELECT * FROM {table}").fetchall()
        if rows_after_caller_rollback:
            failures.append(f"caller rollback left committed registry rows {rows_after_caller_rollback!r}")
    finally:
        conn.close()
    return failures

# scenario: run_register_message_type returns an actionable fault when the store write fails
# inherits: hd=python/honest-alerts/honest-alerts.hd::run_register_message_type -> feature=specs/features/honest-alerts.feature::run_register_message_type returns an actionable fault when the store write fails
from honest_alerts import run_register_message_type
from honest_type import is_fault
from laws_run_register_message_type import _APPROVAL, _TABLE, _VERSIONS, _open_conn_with_table


_DRIVER_REASON = "Alert law denied registration"


async def probe_run_register_message_type_write_failed():
    """Return an actionable registration fault without changing the stored rows."""
    conn = _open_conn_with_table()
    try:
        conn.execute(
            f"INSERT INTO {_TABLE} (message_type, message_versions) VALUES (?, ?)",
            ("system.existing", '["v1"]'),
        )
        conn.execute(
            f"CREATE TRIGGER deny_register BEFORE INSERT ON {_TABLE} "
            f"BEGIN SELECT RAISE(ABORT, '{_DRIVER_REASON}'); END"
        )
        conn.commit()
        before = conn.execute(f"SELECT * FROM {_TABLE}").fetchall()
        result = await run_register_message_type(_APPROVAL, _VERSIONS, {}, conn)
        after = conn.execute(f"SELECT * FROM {_TABLE}").fetchall()
    finally:
        conn.close()

    failures = []
    if not is_fault(result) or result.get("code") != "registration_write_failed" or result.get("category") != "server":
        failures.append(f"blocked registration returned {result!r}, expected a registration_write_failed server Fault")
    else:
        detail = result.get("detail")
        if not isinstance(detail, dict) or detail.get("message_type") != _APPROVAL or detail.get("reason") != _DRIVER_REASON:
            failures.append(
                f"registration Fault detail was {detail!r}, expected message_type={_APPROVAL!r} "
                f"and the driver reason {_DRIVER_REASON!r}"
            )
        message = result.get("message")
        if not isinstance(message, str) or not any(word in message.lower() for word in ("registration", "register")):
            failures.append(f"registration Fault must explain the failed registration write, got {message!r}")
        elif not any(
            action in message.lower()
            for action in ("retry", "check", "restore", "repair", "inspect", "verify", "reconnect", "contact", "try again")
        ):
            failures.append(f"registration Fault must offer a next action, got {message!r}")
    if after != before:
        failures.append(f"failed registration changed the store from {before!r} to {after!r}")
    return failures

# scenario: run_send returns an actionable fault when the event append rolls back
# inherits: hd=python/honest-alerts/honest-alerts.hd::run_send -> feature=specs/features/honest-alerts.feature::run_send returns an actionable fault when the event append rolls back
import asyncio

import honest_observe as HO

from honest_alerts import run_send
from honest_type import is_fault
from laws_run_send import _GIVEN, _alert_sent_rows, _conn_append_blocked, _delivery_rows


def probe_run_send_append_failed():
    """Return an actionable append fault and close the rolled-back transaction."""
    conn = _conn_append_blocked()
    attempted_ids = []
    try:
        conn.create_function("record_failed_aggregate_id", 1, attempted_ids.append)
        table = HO.event_log_schema()["table"]
        conn.execute("DROP TRIGGER block_event_log_insert")
        conn.execute(
            f"CREATE TRIGGER block_event_log_insert BEFORE INSERT ON {table} "
            "BEGIN SELECT record_failed_aggregate_id(NEW.aggregate_id); "
            "SELECT RAISE(ABORT, 'event-log append blocked'); END"
        )
        conn.commit()
        result = asyncio.run(run_send(**_GIVEN, conn=conn))
        deliveries = _delivery_rows(conn)
        sent = _alert_sent_rows(conn)
        in_transaction = conn.in_transaction
    finally:
        conn.close()

    failures = []
    if not is_fault(result) or result.get("code") != "append_failed" or result.get("category") != "server":
        failures.append(f"run_send returned {result!r}, expected an append_failed server Fault")
    else:
        detail = result.get("detail")
        if (
            not isinstance(detail, dict)
            or len(attempted_ids) != 1
            or not attempted_ids[0]
            or detail.get("message_id") != attempted_ids[0]
        ):
            failures.append(f"append_failed detail {detail!r} must echo the attempted aggregate ID {attempted_ids!r}")
        message = result.get("message")
        if not isinstance(message, str) or "append" not in message.lower() or not any(
            phrase in message.lower() for phrase in ("rolled back", "rolled-back", "rollback")
        ):
            failures.append(f"run_send Fault must explain the failed append and rollback, got {message!r}")
        elif not any(
            action in message.lower()
            for action in ("retry", "resend", "check", "restore", "repair", "inspect", "verify", "reconnect", "contact", "try again")
        ):
            failures.append(f"run_send Fault must offer a next action after rollback, got {message!r}")

    if deliveries != ("rows", 0) or sent != ("rows", 0) or in_transaction:
        failures.append(
            f"failed send left deliveries={deliveries!r}, sent events={sent!r}, "
            f"open transaction={in_transaction!r}; expected an empty, closed transaction"
        )
    return failures

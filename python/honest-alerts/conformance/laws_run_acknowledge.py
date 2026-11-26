# scenario: run_acknowledge
# inherits: hd=python/honest-alerts/honest-alerts.hd::run_acknowledge -> feature=specs/features/honest-alerts.feature::run_acknowledge
"""RED probe for honest-alerts.run_acknowledge — the acknowledge orchestrator (honest-alerts.hd,
feature scenario run_acknowledge; sections 9.1, 10, 4.1, 6b).

run_acknowledge is the single mutator of the acknowledgment event. It hands message_id, actor_ref,
reply_payload, session and acknowledged_at to build_ack_event (the pure AckPayload assembler), then
emits alert.acknowledged through the emit seam with the message_id as aggregate_id, so the event folds
under the same aggregate as alert.sent and feeds the mailbox projection that terminates the message.
On a clean emit it returns an AckResult; on a failed append it returns a Fault built via alerts_fault
with code ack_append_failed, category server (section 6b).

This is a boundary orchestrator, so the honest test asserts the effect it records, against a REAL
in-memory sqlite event log driven through the REAL honest-observe emit boundary (the dependency at the
integration boundary) — never a mock of our own code, and no data-holding stand-in for conn. The log
table is created from honest-observe's own declared event_log_schema() manifest, so the probe reads the
module's declared columns (event_type, aggregate_id, payload) rather than hardcoding them.

run_acknowledge is awaited (emit is I/O), so it is driven with asyncio.run.

honest-alerts has no rebuilt code yet, so importing run_acknowledge fails — the expected red. When the
import resolves, a stub returning {} / None and writing nothing fails the literal cases below: no
alert.acknowledged row lands under aggregate_id = message_id, no AckResult comes back, and a stub that
never surfaces ack_append_failed/server on a broken log fails the failed-append case.
"""

import asyncio
import sqlite3

import honest_observe as HO
from honest_type import is_fault

from honest_alerts import build_ack_event, emit, run_acknowledge


def _live_conn():
    """A real in-memory sqlite event log: the integration boundary, not a mock. The honest_event_log
    table is created from honest-observe's own event_log_schema() manifest — the one declared shape
    honest-persist's migration would use — so the probe never hardcodes the coder's columns. A clean
    emit through the real honest-observe emit seam lands a row here."""
    conn = sqlite3.connect(":memory:")
    manifest = HO.event_log_schema()
    table = manifest["table"]
    columns = ", ".join(f"{col} TEXT" for col in manifest["columns"])
    conn.execute(f"CREATE TABLE {table} ({columns})")
    conn.commit()
    return conn


def _broken_conn():
    """A readable SQLite log whose trigger genuinely rejects a new acknowledgment."""
    conn = _live_conn()
    table = HO.event_log_schema()["table"]
    conn.execute(
        f"INSERT INTO {table} (event_type, aggregate_id, payload) VALUES (?, ?, ?)",
        ("alert.sent", "old-message", "{}"),
    )
    conn.execute(
        f"CREATE TRIGGER deny_ack_insert BEFORE INSERT ON {table} "
        "BEGIN SELECT RAISE(ABORT, 'Alert law denied ack append'); END"
    )
    conn.commit()
    return conn


def _rows(conn):
    """Every event in the real log, as (event_type, aggregate_id, payload) tuples."""
    table = HO.event_log_schema()["table"]
    return conn.execute(
        f"SELECT event_type, aggregate_id, payload FROM {table}"
    ).fetchall()


# The acking actor: pure identity (ActorRef), a specific user by id, carrying no session. Every field
# explicit; absence (not tenant-scoped) is NOTHING -> None, written out, never defaulted.
_ACTOR = {"type": "user", "id": "actor-77", "tenant_id": None}

# context is the current manifest emit extracts the auth and meta partitions from.
_CONTEXT = {
    "auth": {"caller_id": "actor-77", "session_id": "sess-9"},
    "meta": {"release": "r1"},
}

# The clean-emit cases the scenario fixes. One session-scoped ack (session carried as data) and the
# explicit absence case (session NOTHING -> None, the ack that did not come in under a DOM session).
# Each pins the recorded effect: exactly one alert.acknowledged event under aggregate_id = message_id.
_CLEAN_CASES = [
    {
        "message_id": "msg-ack-1",
        "actor_ref": _ACTOR,
        "reply_payload": {"choice": "approve"},
        "session": "sess-9",
        "acknowledged_at": 1_700_000_000,
    },
    {
        # the explicit absence case: session NOTHING (the ack came in under no DOM session)
        "message_id": "msg-ack-2",
        "actor_ref": _ACTOR,
        "reply_payload": {},
        "session": None,
        "acknowledged_at": 1_700_000_500,
    },
]


def probe_run_acknowledge():
    """On a clean emit run_acknowledge records exactly one alert.acknowledged event under
    aggregate_id = message_id and returns an AckResult carrying that message_id; on a failed append it
    returns a Fault with code ack_append_failed and category server, never raising."""
    bad = []

    # --- the clean-emit cases: AckResult out, exactly one row in, under the message_id aggregate ---
    for case in _CLEAN_CASES:
        conn = _live_conn()
        out = asyncio.run(
            run_acknowledge(
                case["message_id"],
                case["actor_ref"],
                case["reply_payload"],
                case["session"],
                case["acknowledged_at"],
                _CONTEXT,
                conn,
            )
        )

        # The return is AckResult on a clean emit, never a Fault.
        if is_fault(out):
            bad.append(
                f"run_acknowledge({case['message_id']!r}) returned a Fault on a clean emit: {out!r}"
            )
        else:
            if out.get("message_id") != case["message_id"]:
                bad.append(
                    f"AckResult.message_id must echo the acknowledged message: "
                    f"got {out.get('message_id')!r}, expected {case['message_id']!r}"
                )
            if out.get("acknowledged") is not True:
                bad.append(
                    f"AckResult.acknowledged must be True on a recorded ack: "
                    f"got {out.get('acknowledged')!r}"
                )

        # The recorded effect: exactly one alert.acknowledged event, aggregate_id = message_id.
        rows = _rows(conn)
        ack_rows = [r for r in rows if r[0] == "alert.acknowledged"]
        if len(ack_rows) != 1:
            bad.append(
                f"run_acknowledge({case['message_id']!r}) must emit exactly one alert.acknowledged "
                f"event; the log holds {[r[0] for r in rows]!r}"
            )
            continue
        _event_type, aggregate_id, payload = ack_rows[0]
        if aggregate_id != case["message_id"]:
            bad.append(
                f"alert.acknowledged must fold under aggregate_id = message_id: "
                f"got aggregate_id {aggregate_id!r}, expected {case['message_id']!r}"
            )
        # The AckPayload build_ack_event assembled reached emit: it carries the message_id so the
        # mailbox projection can match acks to their message, and the acknowledged_at passed in at the
        # boundary (payload is stored as JSON text on the real log).
        text = payload or ""
        if case["message_id"] not in text:
            bad.append(
                f"the alert.acknowledged payload must carry message_id {case['message_id']!r}: "
                f"got {payload!r}"
            )
        if str(case["acknowledged_at"]) not in text:
            bad.append(
                f"the alert.acknowledged payload must carry the passed-in acknowledged_at "
                f"{case['acknowledged_at']!r}: got {payload!r}"
            )

    # --- the failed-append case: a broken log must come back as ack_append_failed / server ---
    broken = _broken_conn()
    before = _rows(broken)
    failed = asyncio.run(
        run_acknowledge(
            "msg-ack-fail",
            _ACTOR,
            {"choice": "approve"},
            "sess-9",
            1_700_001_000,
            _CONTEXT,
            broken,
        )
    )
    after = _rows(broken)
    broken.close()
    if after != before:
        bad.append(f"failed acknowledgment changed the log from {before!r} to {after!r}")
    if not is_fault(failed):
        bad.append(
            f"a failed alert.acknowledged append must return a Fault, never an AckResult: got {failed!r}"
        )
    else:
        if failed.get("code") != "ack_append_failed":
            bad.append(
                f"a failed append must carry code ack_append_failed: got {failed.get('code')!r}"
            )
        if failed.get("category") != "server":
            bad.append(
                f"a failed append is a server fault (section 6b): got category "
                f"{failed.get('category')!r}"
            )
        message = failed.get("message")
        if not isinstance(message, str) or "append" not in message.lower():
            bad.append(f"a failed acknowledgment must explain the append failure, got {message!r}")
        elif not any(word in message.lower() for word in ("retry", "check", "restore", "repair", "inspect", "verify", "reconnect", "contact", "try again")):
            bad.append(f"a failed acknowledgment must offer a next action, got {message!r}")

    return bad



async def _fault_detail_for_real_append_failure(conn, message_id):
    """Compare an acknowledge failure with the lower-level seam's actual Fault."""
    session = "sess-9"
    reply = {"choice": "approve"}
    acknowledged_at = 1_700_001_000
    payload = build_ack_event(message_id, _ACTOR, reply, session, acknowledged_at)
    appended = await emit("alert.acknowledged", "alert", message_id, payload, _CONTEXT, "1", conn)
    actual = await run_acknowledge(message_id, _ACTOR, reply, session, acknowledged_at, _CONTEXT, conn)
    if not is_fault(appended) or not appended.get("code"):
        return [f"acknowledgment fixture expected an actual emit Fault, got {appended!r}"]
    if not is_fault(actual) or actual.get("code") != "ack_append_failed" or actual.get("category") != "server":
        return [f"acknowledge returned {actual!r}, expected an ack_append_failed server Fault"]
    detail = actual.get("detail")
    if not isinstance(detail, dict) or detail.get("message_id") != message_id or detail.get("observe") != appended["code"]:
        return [f"acknowledge detail {detail!r} must carry {message_id!r} and underlying code {appended['code']!r}"]
    return []


def probe_run_acknowledge_carries_wrapped_fault_details():
    """Both a refused insert and a raised append supply the actual wrapped code."""
    failures = []
    refused = _broken_conn()
    missing = sqlite3.connect(":memory:")
    try:
        failures.extend(asyncio.run(_fault_detail_for_real_append_failure(refused, "msg-ack-refused")))
        failures.extend(asyncio.run(_fault_detail_for_real_append_failure(missing, "msg-ack-missing")))
    finally:
        refused.close()
        missing.close()
    return failures


def run():
    failures = probe_run_acknowledge() + probe_run_acknowledge_carries_wrapped_fault_details()
    for message in failures:
        print(f"FAIL run_acknowledge: {message}")
    print(
        f"run_acknowledge probe: {'PASS' if not failures else str(len(failures)) + ' failed'}"
    )
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)

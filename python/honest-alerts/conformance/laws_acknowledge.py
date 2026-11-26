# scenario: acknowledge
"""Red test for the `acknowledge` scenario of honest-alerts (specs/features/honest-alerts.feature).

The scenario: `acknowledge` is the acknowledge door that records a recipient acted on a message so the
message can terminate. The world calls it, nothing inside the module does; it hands its input to
run_acknowledge and returns what that returns. It returns AckResult on success or a Fault, never raises,
the Fault returning as a bare union arm (AckResult | Fault).

This probe drives the REAL async `acknowledge` door end to end against a REAL in-memory sqlite event log
built from honest-observe's own declared schema manifest -- the integration boundary the emit path
writes through, not a mock of our own code and not a bespoke conn class. It pins the two things the
scenario fixes for a clean acknowledge:

  1. the returned value is an AckResult (not a Fault) whose `message_id` echoes the input message_id and
     whose `acknowledged` is True -- the AckResult success shape (honest-alerts.hd AckResult: "the
     message that was acknowledged and that the acknowledgment was recorded");
  2. the door actually recorded the acknowledgment -- exactly one `alert.acknowledged` event is appended
     to the log under the message_id as aggregate_id (scenario: "records that a recipient acted on a
     message so the message can terminate"; a boundary is tested by the effect it records).

Two cases, both required:
  - a present-session ack (session is a real SessionId str); and
  - the explicit absence case the scenario names -- session is NOTHING (Python None), the ack that did
    not come in under a DOM session (the waiter view).
The session value does not change whether the acknowledgment is recorded or what AckResult comes back
(it only rides onto the event as data for later termination scope, which build_ack_event / is_terminated
own). So both cases must still return an echoing AckResult with acknowledged True and record exactly one
alert.acknowledged event.

A Fault here is a bare union arm recognized by honest_type.is_fault off the reserved is_err tag; there
is no ok/err envelope. Every field of every input is stated in full, with absence written out as None.
"""

import asyncio
import sqlite3

import honest_observe as HO
from honest_type import is_fault

from honest_alerts import acknowledge


def _conn():
    """A real in-memory sqlite event log, created from honest-observe's own declared schema manifest:
    the integration boundary acknowledge's emit path writes through. Real I/O at the DB boundary, never
    a mock of our own code and never a bespoke conn class."""
    conn = sqlite3.connect(":memory:")
    manifest = HO.event_log_schema()
    table = manifest["table"]
    columns = ", ".join(f"{col} TEXT" for col in manifest["columns"])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns})")
    conn.commit()
    return conn


def _ack_event_count(conn, message_id):
    """How many alert.acknowledged events the log holds under this message_id as aggregate_id."""
    table = HO.event_log_schema()["table"]
    row = conn.execute(
        f"SELECT count(*) FROM {table} WHERE event_type = ? AND aggregate_id = ?",
        ("alert.acknowledged", message_id),
    ).fetchone()
    return int(row[0])


# A plain actor record (ActorRef): pure identity, carries no session. Every field explicit, tenant_id
# absent written out as None.
_ACTOR = {"type": "dom", "id": "actor-7", "tenant_id": None}

# The current manifest the door passes through emit; stated in full, not defaulted.
_CONTEXT = {"auth": {"caller_id": "u1", "session_id": "s1"}, "meta": {"release": "r1"}}

# Each case states its input in full and the AckResult the door must return. acknowledged_at is the
# epoch-seconds moment read at the boundary and passed in; session is a present SessionId or NOTHING.
_CASES = [
    {
        "given": {
            "message_id": "msg-ack-1",
            "actor_ref": _ACTOR,
            "reply_payload": {"choice": "yes"},
            "session": "sess-abc",
            "acknowledged_at": 1_700_000_000,
            "context": _CONTEXT,
        },
        "expect": {"message_id": "msg-ack-1", "acknowledged": True},
    },
    {
        # The explicit absence case the scenario names: session is NOTHING (None) -- the ack did not come
        # in under a DOM session. It is still recorded and still returns an echoing AckResult.
        "given": {
            "message_id": "msg-ack-2",
            "actor_ref": _ACTOR,
            "reply_payload": {},
            "session": None,
            "acknowledged_at": 1_700_000_001,
            "context": _CONTEXT,
        },
        "expect": {"message_id": "msg-ack-2", "acknowledged": True},
    },
]


def _law_acknowledge():
    """acknowledge records the acknowledgment and returns an AckResult echoing the message_id with
    acknowledged True -- for a present session and for the NOTHING (waiter) session alike."""
    bad = []
    for case in _CASES:
        given = case["given"]
        want = case["expect"]
        conn = _conn()
        got = asyncio.run(acknowledge(conn=conn, **given))

        if is_fault(got):
            bad.append(
                f"acknowledge({given}) -> Fault {got}, expected AckResult {want} on a clean ack"
            )
            continue

        got_id = got.get("message_id") if isinstance(got, dict) else None
        got_ack = got.get("acknowledged") if isinstance(got, dict) else None
        if got_id != want["message_id"] or got_ack != want["acknowledged"]:
            bad.append(
                f"acknowledge({given}) -> message_id={got_id!r} acknowledged={got_ack!r}, "
                f"expected message_id={want['message_id']!r} acknowledged={want['acknowledged']!r}"
            )

        recorded = _ack_event_count(conn, given["message_id"])
        if recorded != 1:
            bad.append(
                f"acknowledge({given}) must record exactly one alert.acknowledged event under "
                f"aggregate_id {given['message_id']!r}: log held {recorded}"
            )
    return bad


def run(_suite_path=None):
    bad = _law_acknowledge()
    for line in bad:
        print(line)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(run())

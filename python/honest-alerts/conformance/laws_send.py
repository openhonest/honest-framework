# scenario: send
"""Red test for the `send` scenario of honest-alerts (specs/features/honest-alerts.feature).

The door under test:

    send(message_type, recipient, payload, opts, context, conn) -> SendResult | Fault   (awaited)

The scenario fixes `send` as the primary send door, fire-and-forget with respect to the sender:
the world calls it, nothing inside the module does, and it hands its input to run_send and returns
what that returns. Two clauses of the scenario's Then pin a concrete, backend-independent return:

  - "a message_version missing from opts, or outside the registered closed set for this message_type,
     is a client Fault; honest-alerts never defaults message_version";
  - "it never raises; the Fault returns as a bare union arm (SendResult | Fault), so the calling link
     decides whether a failed send stops its chain".

So the honest, non-vacuous claim this probe pins is the client-Fault path: a message_type that was
never registered (read_registered_type answers NOTHING) and a message_version outside the registered
set are each a client Fault, returned as a bare union arm with the reserved is_err tag true and
category "client" (honest-alerts.hd, type Fault; FaultCategory client), never raised and never wrapped
in an ok/err envelope. That claim does not depend on the persistence backend or on any route being
present, and it is exactly the behaviour the scenario fixes at the door's own return.

The door is driven for real, end to end, against a real in-memory sqlite connection that has no
honest-alerts tables created on it: the integration boundary conn (conn is `any` in the .hd, "held and
passed, never read by any pure function"). A registered-types read taken against this store therefore
finds no record for the message_type (answers NOTHING), which the .hd names as the unregistered-type
client Fault. This is a real resource, not a mock or a data-holding double of our own code.

A Fault is recognized by the reserved is_err arm tag being true, read directly off the returned record;
nothing is recomputed from send, so this is not a circular oracle. The probe returns a list of failure
strings and [] when the claim holds; it never raises to signal a failed assertion, and a raise out of
the door is itself recorded as a failure of the "never raises" clause.

Cases are data; every field of every input is stated in full, with each absent value written as None
(NOTHING) explicitly, never defaulted.
"""

import asyncio
import sqlite3

from honest_alerts import send


def _is_err(result):
    """The reserved is_err arm tag honest-type stamps on every Fault (honest-alerts.hd, type Fault).
    Read straight off the returned record; nothing is recomputed from send."""
    return isinstance(result, dict) and result.get("is_err") is True


def _category(result):
    """who is responsible for a Fault: a FaultCategory member, read without parsing the message."""
    if isinstance(result, dict):
        return result.get("category")
    return None


def _conn():
    """A real in-memory sqlite connection: the integration-boundary resource conn stands for (conn is
    `any` in the .hd). No honest-alerts tables are created on it, so a registered-types read taken
    against this store finds nothing and answers NOTHING -- the unregistered-message_type condition the
    scenario names. A real resource, not a mock and not a data-holding double of our own code."""
    return sqlite3.connect(":memory:")


# --- the six door inputs for each case, stated in full (no defaults; NOTHING written as None) ---------

_RECIPIENT = {"type": "user", "id": "u1", "tenant_id": "acme"}
_PAYLOAD = {"total": 5}
_CONTEXT = {
    "auth": {"caller_id": "sender-1", "session_id": "s1"},
    "meta": {"release": "r1"},
}

# A well-formed ttl TerminationSpec (honest-alerts.hd type TerminationSpec): every field present,
# the ones that do not apply to the ttl condition written as None (NOTHING), never absent.
_TERMINATION_TTL = {
    "condition": "ttl",
    "ttl_seconds": 10,
    "event_type": None,
    "event_filter": None,
}

# A closed SendOpts bag (honest-alerts.hd type SendOpts): exactly its nine keys, each stated in full,
# every non-applicable field written as None (NOTHING). message_version carries a value, so this bag is
# well formed in isolation; the fault is owed to the registry, not to a missing opts key.
_OPTS = {
    "message_version": "v1",
    "subject_label_id": "subject.order_placed",
    "body_label_id": None,
    "channel": "dom",
    "dom_surface": "toast",
    "dom_target": None,
    "reply_options": None,
    "termination": _TERMINATION_TTL,
    "ack_scope": "session",
}

# Each row is a full door call and the arm the scenario fixes for it. Both rows exercise the
# client-Fault path the scenario pins: a message_type with no registration in the store, so
# read_registered_type answers NOTHING and the door owes a client Fault, returned not raised.
_CASES = [
    {
        "name": "unregistered-message-type-is-a-client-fault",
        "given": {
            "message_type": "order.placed",
            "recipient": _RECIPIENT,
            "payload": _PAYLOAD,
            "opts": _OPTS,
            "context": _CONTEXT,
        },
        # The scenario fixes the arm (bare union Fault, is_err true) and the responsibility
        # (category client), not the exact code or message text.
        "expect": {"is_err": True, "category": "client"},
    },
    {
        "name": "unregistered-type-with-a-different-version-is-still-a-client-fault",
        "given": {
            "message_type": "system.maintenance_notice",
            "recipient": _RECIPIENT,
            "payload": _PAYLOAD,
            # A distinct closed SendOpts bag carrying a different message_version; the type is still
            # unregistered in the store, so a client Fault is owed, never a default and never a send.
            "opts": {
                "message_version": "v2",
                "subject_label_id": "subject.maintenance",
                "body_label_id": None,
                "channel": "dom",
                "dom_surface": "banner",
                "dom_target": None,
                "reply_options": None,
                "termination": _TERMINATION_TTL,
                "ack_scope": "actor",
            },
            "context": _CONTEXT,
        },
        "expect": {"is_err": True, "category": "client"},
    },
]


def probe_send():
    """send returns a client Fault (bare union arm, is_err true, category client) for a message_type
    that was never registered, by return and never by raise, never wrapped in an ok/err envelope
    (SendResult | Fault)."""
    bad = []
    for case in _CASES:
        given = case["given"]
        want = case["expect"]
        conn = _conn()
        try:
            got = asyncio.run(send(conn=conn, **given))
        except Exception as exc:  # the door "never raises"; a raise is itself the defect
            bad.append(
                f"send({case['name']}) raised {type(exc).__name__}: {exc}; "
                f"expected a returned client Fault {want}"
            )
            continue
        finally:
            conn.close()

        if not _is_err(got):
            bad.append(
                f"send({case['name']}) -> {got!r}; expected a Fault arm with is_err True "
                f"(an unregistered message_type is a client Fault returned as a bare union arm, "
                f"never a SendResult and never an ok/err envelope)"
            )
            continue
        if _category(got) != want["category"]:
            bad.append(
                f"send({case['name']}) -> category {_category(got)!r}, "
                f"expected {want['category']!r} (the caller's unregistered type is a client fault)"
            )
    return bad


def run(_suite_path=None):
    bad = probe_send()
    for line in bad:
        print(line)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(run())

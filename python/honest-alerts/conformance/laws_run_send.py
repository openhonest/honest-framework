# scenario: run_send
# inherits: hd=python/honest-alerts/honest-alerts.hd::run_send -> feature=specs/features/honest-alerts.feature::run_send
"""Red test for the run_send scenario of honest-alerts (specs/features/honest-alerts.feature).

The clauses under test are the one-transaction / rollback contract the scenario fixes:

  "it writes each Delivery in the plan through write_delivery and emits alert.sent through the emit
   seam with the Message as payload and the message_id as aggregate_id"
  "the delivery rows and the alert.sent append commit together or roll back together on one conn
   inside one transaction, because alert.sent is the read-path source of truth for the mailbox and
   must share the fate of the delivery rows"
  "a rolled-back transaction is returned as a Fault; under the declared fallback it writes the
   delivery rows first then appends alert.sent, never emit-first, and a failed append after the rows
   are written is never swallowed but returned as a surfaced Fault"

and (from the .hd run_send note) the exact failure the rolled-back append surfaces:
  "a Fault built via alerts_fault with code append_failed (category server, section 6b)".

THE REAL DB. conn is a standard DB-API connection (PEP 249) shared by the alerts-owned tables and
the honest-observe event log (honest-alerts.hd run_send / read_routes notes, section 6.1/10b). This
probe drives the REAL run_send against a REAL in-memory sqlite connection -- never a mock of our own
code -- built the way honest-observe's own laws build theirs (laws_ho.py _create_log): the four tables
are CREATEd from the modules' own declared manifests, so the probe never hardcodes the coder's
columns. honest-alerts.alert_tables_schema() gives the three alerts tables (alert_routes,
alert_deliveries, alert_registered_types); honest_observe.event_log_schema() gives honest_event_log.
All four live on the one conn, exactly as the one-transaction rule requires.

THE SEED. run_send reads the registered-types record (so order.placed must be registered with its
version set) and the routing table (so supervise finds at least one route, the unit-1 non-empty
assumption in the supervise scenario). Both are seeded as real rows on the same conn from the
manifest's declared column names, the JSON-text columns carrying the ChannelConfig list and the
version set as honest-persist would store them.

THE ASSERTIONS are made directly against the committed rows on the real conn -- SELECT counts, not
just the returned value -- so the one-transaction fate is observed, not inferred:
  * CLEAN: run_send returns a SendResult (not a Fault), AND alert_deliveries has the delivery row(s)
    for this message AND honest_event_log has the alert.sent row. Rows and append landed together.
  * FAILED APPEND: a real BEFORE INSERT trigger on honest_event_log ABORTs the alert.sent append, so
    the single transaction rolls back. run_send returns a Fault with code append_failed, category
    server; AND alert_deliveries has ZERO rows for this message AND honest_event_log has ZERO
    alert.sent rows. Rows and append rolled back together.

A failed query is never read as a success-looking 0: the committed-state reader returns a two-arm
outcome, ("rows", n) when the table was read and ("query_error", exc) when it was not, and the probe
surfaces a query error as a failed assertion, never as zero rows. The event-log table is present and
fully queryable on BOTH paths (only the append is blocked, by trigger), so both counts are honestly
observable.

A Fault is recognized by the reserved is_err tag being true (honest-alerts.hd type Fault; honest-type
section 13.2), read directly off the returned record -- never a raise, never an ok/err envelope, and
nothing recomputed from run_send, so there is no circular oracle. The rollback case pins the literal
non-trivial values code "append_failed" and category "server", so the probe is not vacuous.

The .hd signature is run_send(message_type, recipient, payload, opts, context, conn), awaited.
"""

import asyncio
import json
import sqlite3

import honest_observe as HO

from honest_alerts import alert_tables_schema, run_send


# ---------------------------------------------------------------------------------------------------
# Builders. No default kwargs: every field is passed explicitly at each call site, and an absent field
# is NOTHING (None) written out in full, per the SendOpts / ActorRef / TerminationSpec / ChannelConfig
# schemas (honest-alerts.hd). The builders take all their fields as required arguments for that reason.
# ---------------------------------------------------------------------------------------------------

def _actor(type_, id_, tenant_id):
    """A flat ActorRef (honest-alerts.hd type ActorRef): pure identity, no session."""
    return {"type": type_, "id": id_, "tenant_id": tenant_id}


def _termination_ttl(ttl_seconds):
    """A well-formed ttl TerminationSpec (honest-alerts.hd type TerminationSpec): the three
    non-applying fields are NOTHING (None) explicitly, never absent."""
    return {
        "condition": "ttl",
        "ttl_seconds": ttl_seconds,
        "event_type": None,
        "event_filter": None,
    }


def _opts(message_version, subject_label_id, body_label_id, channel, dom_surface,
          dom_target, reply_options, termination, ack_scope):
    """A closed SendOpts bag (honest-alerts.hd type SendOpts): exactly its nine keys, every one passed
    explicitly by the caller, absence written as NOTHING (None)."""
    return {
        "message_version": message_version,
        "subject_label_id": subject_label_id,
        "body_label_id": body_label_id,
        "channel": channel,
        "dom_surface": dom_surface,
        "dom_target": dom_target,
        "reply_options": reply_options,
        "termination": termination,
        "ack_scope": ack_scope,
    }


def _channel_config(channel, recipient_spec, template_id, delay_seconds):
    """One ChannelConfig (honest-alerts.hd type ChannelConfig): every field explicit, recipient_spec
    and template_id NOTHING (None) when absent so supervise falls back to the message recipient."""
    return {
        "channel": channel,
        "recipient_spec": recipient_spec,
        "template_id": template_id,
        "delay_seconds": delay_seconds,
    }


def _alert_route(route_id, message_type, sender_type, channels, escalation, priority):
    """One AlertRoute (honest-alerts.hd type AlertRoute): every field explicit, sender_type NOTHING to
    match any sender and escalation NOTHING for no escalation."""
    return {
        "route_id": route_id,
        "message_type": message_type,
        "sender_type": sender_type,
        "channels": channels,
        "escalation": escalation,
        "priority": priority,
    }


# ---------------------------------------------------------------------------------------------------
# The real DB-API connection: the four tables created from the modules' own declared manifests, on one
# conn. _table_manifest finds the named table's manifest in alert_tables_schema()'s list of three; the
# probe reads table name, columns and the JSON-text columns from the manifest rather than hardcoding
# them, so the seed cannot drift from the schema honest-persist's migration would build.
# ---------------------------------------------------------------------------------------------------

# Columns whose declared value is a JSON structure (a list or a map), stored as JSON text, per the
# alert_tables_schema note: AlertRoute.channels / .escalation and RegisteredType.message_versions.
_JSON_COLUMNS = {"channels", "escalation", "message_versions", "recipient"}


def _table_manifest(name):
    """The manifest for one alerts-owned table out of alert_tables_schema()'s three (honest-alerts.hd
    alert_tables_schema note): a record naming the table and its columns, read as data."""
    manifest = alert_tables_schema()
    tables = manifest["tables"] if isinstance(manifest, dict) and "tables" in manifest else manifest
    for table in tables:
        if table["table"] == name:
            return table
    raise LookupError(f"alert_tables_schema() declared no table named {name!r}: {manifest!r}")


def _create_from_manifest(conn, manifest):
    """CREATE one table from its declared manifest, every column TEXT (the laws_ho.py idiom)."""
    table = manifest["table"]
    columns = ", ".join(f"{col} TEXT" for col in manifest["columns"])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns})")


def _insert_row(conn, manifest, row):
    """Insert one seed row into a manifest table. Every declared column is written; a JSON-structured
    column is stored as JSON text, a scalar as its value, and a column the row does not name as NULL,
    so the row is complete and no implicit default fills a missing field."""
    table = manifest["table"]
    cols = manifest["columns"]
    values = []
    for col in cols:
        if col not in row:
            values.append(None)
        elif col in _JSON_COLUMNS:
            values.append(json.dumps(row[col]))
        else:
            value = row[col]
            values.append(value if isinstance(value, (str, type(None))) else str(value))
    placeholders = ", ".join("?" for _ in cols)
    conn.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})", values)


def _create_event_log(conn):
    """Create honest_event_log from honest-observe's declared manifest (laws_ho.py _create_log), so the
    alert.sent append lands in a real table with the one declared shape."""
    manifest = HO.event_log_schema()
    columns = ", ".join(f"{col} TEXT" for col in manifest["columns"])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {manifest['table']} ({columns})")


def _seed(conn):
    """Seed the one registered type and one matching route run_send needs to reach the write path: the
    registered record carrying order.placed with version v1 (so build_message accepts message_version
    v1), and one AlertRoute on order.placed with a single dom ChannelConfig (so supervise, under the
    unit-1 non-empty assumption, returns a one-Delivery plan)."""
    routes = _table_manifest("alert_routes")
    types = _table_manifest("alert_registered_types")
    _insert_row(conn, types, {"message_type": "order.placed", "message_versions": ["v1"]})
    _insert_row(conn, routes, _alert_route(
        route_id="r1",
        message_type="order.placed",
        sender_type=None,
        channels=[_channel_config(channel="dom", recipient_spec=None, template_id=None, delay_seconds=0)],
        escalation=None,
        priority=0,
    ))


def _base_conn():
    """A real in-memory sqlite connection carrying all four tables (three alerts + the event log) on
    one conn, seeded with the matching registered type and route. The clean and failed paths share this
    exact build; the only difference is the append-blocking trigger the failed path adds."""
    conn = sqlite3.connect(":memory:")
    _create_from_manifest(conn, _table_manifest("alert_routes"))
    _create_from_manifest(conn, _table_manifest("alert_deliveries"))
    _create_from_manifest(conn, _table_manifest("alert_registered_types"))
    _create_event_log(conn)
    _seed(conn)
    conn.commit()
    return conn


def _conn_clean():
    """The clean path: nothing blocks the append, so the delivery rows and the alert.sent append both
    commit on the one conn."""
    return _base_conn()


def _conn_append_blocked():
    """The failed-append path: a real BEFORE INSERT trigger on honest_event_log ABORTs every insert
    into it. The table is present and fully queryable (so the committed state is observable), but the
    alert.sent append run_send performs last cannot complete -- a broken dependency the caller cannot
    fix. Under the declared rows-first fallback the delivery rows are written first; when the append
    aborts the single transaction must roll them back, leaving no committed delivery row and no
    alert.sent row."""
    conn = _base_conn()
    table = HO.event_log_schema()["table"]
    conn.execute(
        f"CREATE TRIGGER block_event_log_insert BEFORE INSERT ON {table} "
        f"BEGIN SELECT RAISE(ABORT, 'event-log append blocked'); END"
    )
    conn.commit()
    return conn


# ---------------------------------------------------------------------------------------------------
# Reading the committed state honestly. Each reader returns a two-arm outcome distinguishing a real
# count from a query that errored: ("rows", n) when the table could be read, ("query_error", exc) when
# it could not. The probe NEVER collapses a query error into "0 committed" -- an unreadable table is a
# failed assertion, never evidence of a rolled-back write.
# ---------------------------------------------------------------------------------------------------

def _alert_sent_rows(conn):
    """The committed alert.sent rows on this conn, for this message's aggregate (the message_id run_send
    uses as aggregate_id). Both paths keep honest_event_log present and queryable, so the read returns
    ("rows", n); a read error returns ("query_error", exc) and is surfaced, never counted as zero."""
    table = HO.event_log_schema()["table"]
    try:
        row = conn.execute(
            f"SELECT count(*) FROM {table} WHERE event_type = ?", ("alert.sent",)
        ).fetchone()
    except Exception as exc:  # a failed read is surfaced, never reported as 0 committed rows
        return ("query_error", exc)
    return ("rows", int(row[0]))


def _delivery_rows(conn):
    """The committed alert_deliveries rows on this conn. Returns ("rows", n) when the table was read,
    ("query_error", exc) otherwise -- a failed read is a failed assertion, never zero committed rows."""
    table = _table_manifest("alert_deliveries")["table"]
    try:
        row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()
    except Exception as exc:
        return ("query_error", exc)
    return ("rows", int(row[0]))


# ---------------------------------------------------------------------------------------------------
# Reading the returned arm. The Fault is recognized by the reserved is_err tag being true, read
# directly off the value -- nothing is recomputed from run_send, so there is no circular oracle.
# ---------------------------------------------------------------------------------------------------

def _is_fault(value):
    """True when value is the Fault arm: a record carrying is_err set true (honest-alerts.hd Fault)."""
    if isinstance(value, dict):
        return value.get("is_err") is True
    return getattr(value, "is_err", None) is True


def _field(value, name):
    """Read one field off the returned record whether it is a dict (the canonical shape) or an
    attribute-carrying record, so the probe does not assume one container."""
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _run(given, conn):
    """Call the real run_send once, awaiting it (the .hd marks run_send awaited). Returns ('value', v),
    or ('raised', e) if it raised instead of returning -- a raise is itself a failure of the
    never-raises bare-union contract the scenario pins."""
    try:
        return ("value", asyncio.run(run_send(
            given["message_type"],
            given["recipient"],
            given["payload"],
            given["opts"],
            given["context"],
            conn,
        )))
    except Exception as exc:  # run_send must not raise; a raise breaks the bare-union contract
        return ("raised", exc)


# ---------------------------------------------------------------------------------------------------
# The cases are data. Each states its input in full and the arm plus the committed row counts its run
# must produce on the one real connection it is given. The rollback case pins the literal code and
# category; the clean case pins the atomic outcome (a SendResult, the delivery rows, the alert.sent
# row). The two counts on each path are what observe the one-transaction fate directly.
# ---------------------------------------------------------------------------------------------------

_GIVEN = {
    "message_type": "order.placed",
    "recipient": _actor("user", "u1", None),
    "payload": {"total": 5},
    "opts": _opts(
        message_version="v1",
        subject_label_id="subject.order_placed",
        body_label_id=None,
        channel="dom",
        dom_surface="toast",
        dom_target=None,
        reply_options=None,
        termination=_termination_ttl(10),
        ack_scope="session",
    ),
    "context": {
        "sender": _actor("user", "sender-1", None),
        "auth": {"caller_id": "sender-1", "session_id": "s1"},
        "meta": {"release": "r1"},
    },
}

_CASES = [
    {
        "name": "clean-path-commits-rows-and-alert_sent-together",
        "conn": _conn_clean,
        # Nothing blocks the append: run_send returns a SendResult (not a Fault), and both the delivery
        # row(s) and the alert.sent row are committed on the one conn -- rows and append landing
        # together, the atomic clean path.
        "expect_fault": False,
        "expect_code": None,
        "expect_category": None,
        "expect_delivery_rows": 1,
        "expect_alert_sent_rows": 1,
    },
    {
        "name": "rollback-on-failed-append-returns-append_failed-server",
        "conn": _conn_append_blocked,
        # The alert.sent append (the last step of the declared rows-first fallback) ABORTs at the real
        # SQLite boundary, so the one transaction rolls back: run_send returns the server Fault with the
        # exact code the .hd note / section 6b fix, and commits NO delivery row and NO alert.sent row --
        # facts read off present, queryable tables, never inferred from an error.
        "expect_fault": True,
        "expect_code": "append_failed",
        "expect_category": "server",
        "expect_delivery_rows": 0,
        "expect_alert_sent_rows": 0,
    },
]


def _assert_count(bad, case, label, reader, conn, expected):
    """Assert a committed-row count honestly: a query error is surfaced as a failed assertion for this
    case, never collapsed into zero committed rows."""
    outcome, detail = reader(conn)
    if outcome == "query_error":
        bad.append(
            f"run_send({case['name']}) could not read {label} to assert the committed state: "
            f"{type(detail).__name__}: {detail}. An unreadable table is a failed assertion, never "
            f"evidence of zero committed rows -- this case cannot be judged"
        )
    elif detail != expected:
        bad.append(
            f"run_send({case['name']}) committed {detail} {label} row(s), expected {expected}: the "
            f"alert.sent append and the delivery rows must share one fate -- committed together on the "
            f"clean path, rolled back together on the failed one"
        )


def probe_run_send():
    """run_send writes the delivery rows then appends alert.sent on the one conn: on a clean conn the
    rows and the alert.sent row land together and it returns a SendResult; on a conn whose append cannot
    complete it rolls back, commits neither the delivery rows nor the alert.sent row, and returns a
    server Fault code append_failed by return, never raising and never reporting a successful send. The
    committed state is read honestly: a failed read is surfaced as a failure, never dressed up as zero
    rows."""
    bad = []
    for case in _CASES:
        conn = case["conn"]()
        kind, result = _run(_GIVEN, conn)

        if kind == "raised":
            bad.append(
                f"run_send({case['name']}) raised {type(result).__name__}: {result}; run_send must "
                f"return by the bare union arm, never raise (a rolled-back transaction is a returned Fault)"
            )
            continue

        if case["expect_fault"]:
            if not _is_fault(result):
                bad.append(
                    f"run_send({case['name']}) -> {result!r}; expected a Fault arm (is_err true): a "
                    f"failed alert.sent append must be surfaced as a Fault by return, never swallowed"
                )
            else:
                code = _field(result, "code")
                category = _field(result, "category")
                if code != case["expect_code"]:
                    bad.append(
                        f"run_send({case['name']}) Fault code -> {code!r}, expected "
                        f"{case['expect_code']!r} (the rolled-back-append code fixed in section 6b)"
                    )
                if category != case["expect_category"]:
                    bad.append(
                        f"run_send({case['name']}) Fault category -> {category!r}, expected "
                        f"{case['expect_category']!r} (a broken dependency the caller cannot fix)"
                    )
                message = _field(result, "message")
                if not isinstance(message, str) or "append" not in message.lower():
                    bad.append(f"run_send Fault must explain the failed event append, got {message!r}")
                if conn.in_transaction:
                    bad.append("run_send left a transaction open after the failed append")
        else:
            if _is_fault(result):
                bad.append(
                    f"run_send({case['name']}) -> Fault {result!r}; expected a SendResult: the clean "
                    f"path commits the rows and the alert.sent append together and returns success"
                )
            else:
                delivered = _field(result, "delivered")
                if not isinstance(delivered, int) or delivered < 1:
                    bad.append(
                        f"run_send({case['name']}) SendResult.delivered -> {delivered!r}; expected a "
                        f"positive count of delivery records written on the clean path"
                    )

        if not case["expect_fault"]:
            event_log = HO.event_log_schema()["table"]
            rows = conn.execute(
                f"SELECT payload FROM {event_log} WHERE event_type = ?", ("alert.sent",)
            ).fetchall()
            for (payload_text,) in rows:
                payload = json.loads(payload_text)
                if payload.get("reply_required") is not False:
                    bad.append(f"alert.sent payload must carry reply_required False, got {payload!r}")

        _assert_count(bad, case, "alert_deliveries", _delivery_rows, conn, case["expect_delivery_rows"])
        _assert_count(bad, case, "alert.sent", _alert_sent_rows, conn, case["expect_alert_sent_rows"])
        conn.close()
    return bad


if __name__ == "__main__":
    failures = probe_run_send()
    for line in failures:
        print(line)
    raise SystemExit(1 if failures else 0)

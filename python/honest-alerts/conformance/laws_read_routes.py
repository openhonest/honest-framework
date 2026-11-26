# scenario: read_routes
"""Red test for the read_routes scenario of honest-alerts (specs/features/honest-alerts.feature).

The clause under test is the one the scenario fixes:

  "message_type is the message's dot-namespaced type; the read returns every AlertRoute whose
   message_type matches it or wildcard-matches it, which the pure supervisor then filters and sorts,
   so the match decision lives in the pure core, not the query"

and, from the Given, the read reaches the alert_routes table through the injected PEP 249 `conn`,
reading its table name and columns from alert_tables_schema()'s manifest rather than hardcoding them.

WHAT THE SCENARIO FIXES, AND WHAT IT DOES NOT. The clause ends "which the pure supervisor then
filters and sorts, so the match decision lives in the pure core, not the query." So the scenario
deliberately does NOT fix that read_routes filters at the query: the match/sort decision is pushed to
the pure supervisor. What it DOES fix is that a seeded AlertRoute that matches the given message_type
is returned, decoded from its stored columns back to the AlertRoute record (channels from JSON text,
escalation/sender_type NOTHING when the column is null, priority as int). That is the pinned,
non-trivial output this probe proves. Whether an unrelated route is also present is left to the pure
core and is NOT asserted here -- asserting its absence would contradict "not the query"; see GAPS.

THE REAL DB. conn is a standard DB-API connection (PEP 249). This probe drives the REAL read_routes
against a REAL in-memory sqlite connection -- never a mock of our own code -- built the way
honest-observe's own laws build theirs (laws_ho.py _create_log) and the way laws_run_send.py builds
the alerts tables: alert_routes is CREATEd from honest-alerts' OWN declared manifest
(alert_tables_schema()), so the probe never hardcodes the coder's column list. The JSON-structured
columns (channels, escalation) are stored as JSON text, as honest-persist would store them.

THE SEED. Three real AlertRoute rows are inserted on the one conn from the manifest's declared column
names:
  * one route whose message_type is exactly the message_type being read -- it MUST come back, and its
    fields MUST decode to what was seeded (channels as the ChannelConfig list, escalation NOTHING when
    the stored column is null, sender_type NOTHING when null, priority as an int, not the stored TEXT);
  * one wildcard route with a non-null sender restriction and escalation, and two ordered channels;
  * one route for a DIFFERENT message_type, present only to make the fixture realistic; the scenario
    leaves query-level filtering to the pure supervisor, so this row's presence or absence in the
    result is NOT asserted. The matching row's "it MUST come back, decoded in full" is what proves the
    probe is not vacuous: a stub returning [] would fail that case.

The probe returns a list of failure strings; empty means the behaviour holds. It never raises to
signal a failed assertion -- faults are data.
"""

import asyncio
import json
import sqlite3

from honest_alerts import alert_tables_schema, read_routes

# NOTHING is honest-alerts' absence sentinel (boundary.py NOTHING = None); the read returns NOTHING for
# a nullable column that stored NULL (sender_type, escalation).
NOTHING = None

# AlertRoute.channels and AlertRoute.escalation are JSON-structured columns, stored as JSON text
# exactly as the write boundary and honest-persist store them (alert_tables_schema note); every other
# column is a scalar.
_JSON_COLUMNS = {"channels", "escalation"}


def _table_manifest(name):
    """The manifest for one alerts-owned table out of alert_tables_schema()'s three (honest-alerts.hd
    alert_tables_schema note): a record naming the table and its columns, read as data. The read under
    test reads its table name and columns from here, so the probe builds the table from the same
    source -- the read and the fixture cannot drift."""
    for manifest in alert_tables_schema():
        if manifest["table"] == name:
            return manifest
    raise LookupError(f"alert_tables_schema() declared no table named {name!r}")


def _create_from_manifest(conn, manifest):
    """CREATE one table from its declared manifest, every column TEXT (the laws_ho.py idiom)."""
    table = manifest["table"]
    columns = ", ".join(f"{col} TEXT" for col in manifest["columns"])
    conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns})")


def _insert_row(conn, manifest, row):
    """Insert one seed route into the alert_routes table. Every declared column is written explicitly:
    a JSON-structured column as JSON text, a scalar as its value, and a column the row leaves absent as
    NULL -- the row is complete and no implicit default fills a missing field."""
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


def _channel_config(channel, recipient_spec, template_id, delay_seconds):
    """One ChannelConfig, every field explicit, the ordered list element of AlertRoute.channels."""
    return {
        "channel": channel,
        "recipient_spec": recipient_spec,
        "template_id": template_id,
        "delay_seconds": delay_seconds,
    }


# The exact-match route: its message_type equals the message_type being read. sender_type and
# escalation are stored NULL, so the decoded AlertRoute carries NOTHING in each. channels is one
# ChannelConfig; priority is stored as TEXT and must decode to the int 10.
_CHANNELS = [_channel_config("email", "ops@example.com", "tmpl_a", 0)]

_ROUTE_SEED = {
    "route_id": "r-match",
    "message_type": "order.placed",
    "sender_type": NOTHING,          # stored NULL -> decoded NOTHING
    "channels": _CHANNELS,           # JSON text -> decoded list
    "escalation": NOTHING,           # stored NULL -> decoded NOTHING
    "priority": 10,                  # stored TEXT -> decoded int
}

# A route for an unrelated message_type: not part of the answer for "order.placed".
_ROUTE_OTHER = {
    "route_id": "r-other",
    "message_type": "payment.captured",
    "sender_type": NOTHING,
    "channels": [_channel_config("sms", "+10000000000", "tmpl_b", 5)],
    "escalation": NOTHING,
    "priority": 20,
}

# A wildcard route also matches, with every nullable field populated and channels in declared order.
_ROUTE_WILDCARD = {
    "route_id": "r-wildcard",
    "message_type": "order.*",
    "sender_type": "user",
    "channels": [
        _channel_config("email", None, "wildcard_template", 8),
        _channel_config("dom", None, None, 0),
    ],
    "escalation": {
        "ttl_seconds": 90,
        "escalate_to": {"type": "user", "id": "operator", "tenant_id": None},
        "escalate_channel": "email",
        "escalation_message_type": "order.unacknowledged",
    },
    "priority": 31,
}

# The AlertRoute the read must produce for the exact-match seed, written out in full as a literal:
# this is the non-trivial expected output a stub cannot produce.
_EXPECTED_MATCH = {
    "route_id": "r-match",
    "message_type": "order.placed",
    "sender_type": NOTHING,
    "channels": _CHANNELS,
    "escalation": NOTHING,
    "priority": 10,
}

_CASES = [
    {
        "given": {"message_type": "order.placed"},
        "seed": [_ROUTE_SEED, _ROUTE_OTHER, _ROUTE_WILDCARD],
        # The exact-match route is returned and decoded in full. Query-level filtering of the
        # unrelated route is the pure supervisor's job (scenario: "not the query"), so it is unasserted.
        "expect_present": [_EXPECTED_MATCH, _ROUTE_WILDCARD],
    },
]


def _fresh_conn():
    """A real in-memory sqlite conn with alert_routes CREATEd from the declared manifest."""
    conn = sqlite3.connect(":memory:")
    _create_from_manifest(conn, _table_manifest("alert_routes"))
    return conn


def _route_id(route):
    """The route_id of a returned AlertRoute, whether it is a dict record or a mapping-like row."""
    return route["route_id"] if isinstance(route, dict) else route[0]


def probe_read_routes():
    """read_routes returns the matching AlertRoute, decoded from the alert_routes table it reads through
    the injected conn using the alert_tables_schema manifest: channels from JSON text, escalation and
    sender_type NOTHING when the stored column is null, priority as int."""
    bad = []
    for case in _CASES:
        conn = _fresh_conn()
        manifest = _table_manifest("alert_routes")
        for row in case["seed"]:
            _insert_row(conn, manifest, row)
        conn.commit()

        try:
            got = asyncio.run(read_routes(case["given"]["message_type"], conn))
        finally:
            conn.close()

        if not isinstance(got, list):
            bad.append(f"read_routes({case['given']}) -> {got!r}, expected a list of AlertRoute")
            continue

        returned_ids = [_route_id(r) for r in got]

        for expected in case["expect_present"]:
            matches = [r for r in got if _route_id(r) == expected["route_id"]]
            if not matches:
                bad.append(
                    f"read_routes({case['given']}) -> route_ids {returned_ids}, "
                    f"expected matching route {expected['route_id']!r} to be returned"
                )
                continue
            route = matches[0]
            if route != expected:
                bad.append(
                    f"read_routes({case['given']}) returned {route!r} for {expected['route_id']!r}, "
                    f"expected {expected!r}"
                )
    return bad

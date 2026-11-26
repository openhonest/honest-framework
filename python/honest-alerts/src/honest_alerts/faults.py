"""The single place honest-alerts assembles a fault, and the three alerts-owned table manifests."""

# inherits: hd=python/honest-alerts/honest-alerts-pure.hd::alerts_fault -> feature=specs/features/honest-alerts.feature::alerts_fault -> test=python/honest-alerts/conformance/laws_alerts_fault.py::probe_alerts_fault
# hd: alerts_fault
def alerts_fault(code, message, category, detail):
    """Build one honest-alerts Fault record from its parts (honest-errors sections 2, 3; honest-type
    section 13.2). code is the specific reason from the section 6b code space; message is the human
    sentence naming what went wrong and what to do instead; category is who is responsible, a
    FaultCategory member client or server; detail is the structured context a test reads without
    parsing the message. It sets the reserved is_err tag true and
    returns the Fault, carried by the return as a bare union arm, never raised and never wrapped in
    an ok/err envelope. results is [] because alerts_fault accumulates none. Pure: reads no world."""
    return {
        "is_err": True,
        "code": code,
        "message": message,
        "category": category,
        "results": [],
        "detail": detail,
    }


# The three alerts-owned honest-persist table manifests, section 10b. Each manifest names the table
# and its columns the way honest-observe's event_log_schema names its own, so the module's
# table-touching readers and writers read table name and columns from here rather than hardcoding
# them. Declared as module data, read once by alert_tables_schema.
_ALERT_TABLES = (
    {
        "table": "alert_routes",
        "columns": [
            "route_id",
            "message_type",
            "sender_type",
            "channels",
            "escalation",
            "priority",
        ],
        "indexes": [{"name": "ix_alert_routes_message_type", "columns": ["message_type"]}],
        "append_only": False,
    },
    {
        "table": "alert_deliveries",
        "columns": [
            "delivery_id",
            "message_id",
            "route_id",
            "channel",
            "recipient",
            "deliver_at",
            "status",
        ],
        "indexes": [
            {"name": "ix_alert_deliveries_status_deliver_at", "columns": ["status", "deliver_at"]},
            {"name": "ix_alert_deliveries_message_id", "columns": ["message_id"]},
        ],
        "append_only": False,
    },
    {
        "table": "alert_registered_types",
        "columns": ["message_type", "message_versions"],
        "indexes": [],
        "append_only": False,
    },
)


# hd: alert_tables_schema
def alert_tables_schema():
    """Return the three alerts-owned honest-persist table manifests as data: alert_routes (section
    5), alert_deliveries (section 6.2), alert_registered_types (section 3b), the honest-alerts twin
    of honest-observe's event_log_schema (honest-observe section 10). Each manifest names that
    table's columns and the indexes the module's reads need. Unlike the event log these tables are
    not append-only: deliveries move pending -> delivered/failed and a byte-identical re-registration
    is a no-op. Pure: the schema is fixed, so it returns the manifest as data, reads no world and
    takes no argument. Returned as the list of the three manifests, each a
    {table, columns, indexes, append_only} record, so a caller finds a table by its own `table`
    field exactly as honest-observe's manifest exposes it."""
    return [dict(table) for table in _ALERT_TABLES]

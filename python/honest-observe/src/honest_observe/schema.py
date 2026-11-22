"""The honest_event_log table manifest: the append-only event-log schema honest-persist enforces,
with update and delete rejected against the table (honest-observe.hd event_log_schema, section 10).

It names the envelope columns (section 2.1) and the indexes the common projection filters need -- by
event type, by aggregate, by timestamp, by aggregate-and-sequence -- so honest-persist's migration can
create the table from one declared shape. Pure: it returns the manifest as data, takes no argument
because the schema is fixed, and reads no world.
"""

# The envelope columns, in envelope order (section 2.1). Named once so the schema and every reader of
# it agree on the one declared shape rather than each hardcoding its own column list.
_COLUMNS = (
    "event_id",
    "event_type",
    "event_version",
    "timestamp",
    "sequence",
    "aggregate_type",
    "aggregate_id",
    "payload",
    "auth",
    "meta",
)

# The indexes the common projection filters need: by event type, by aggregate, by timestamp, and by
# aggregate-and-sequence (the per-aggregate order next_sequence reads).
_INDEXES = (
    {"name": "ix_event_log_event_type", "columns": ["event_type"]},
    {"name": "ix_event_log_aggregate", "columns": ["aggregate_type", "aggregate_id"]},
    {"name": "ix_event_log_timestamp", "columns": ["timestamp"]},
    {"name": "ix_event_log_aggregate_sequence", "columns": ["aggregate_id", "sequence"]},
)


def event_log_schema():
    """Return the honest_event_log table manifest as data: the table name, the envelope columns, the
    projection-filter indexes, and the append-only mark honest-persist reads to reject update and
    delete against the table (section 10). Pure: no world, no argument, no fault."""
    return {
        "table": "honest_event_log",
        "columns": list(_COLUMNS),
        "indexes": [dict(index) for index in _INDEXES],
        "append_only": True,
    }

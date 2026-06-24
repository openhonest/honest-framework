"""The event-log table (section 10): the honest_event_log definition as pure data.

The log lives in honest-persist as one append-only table, but its shape belongs to observe — it is
the envelope (section 2) given columns. So observe owns the definition and emits it as a persist
schema dict; honest-persist applies it and enforces the append-only rule. The dependency runs one way:
observe is stored by persist and never imports it, so the schema here is plain data persist consumes,
not a call into persist.

`event_log_schema` returns the persist `{table: Table}` schema — ten columns mirroring the envelope
(the seven framework fields NOT NULL, the JSON payload NOT NULL, the auth and meta partitions
nullable for a no-auth event) and the four indexes the common projections read by. `event_log_manifest`
wraps that schema with the append-only declaration persist reads to reject UPDATE and DELETE.
"""

# The ten columns, in envelope order. Strings are text; sequence is an integer; the JSON payload and
# the auth/meta partitions serialize to text. Only auth and meta are nullable (section 2.2).
_COLUMNS = {
    "event_id": {"type": "text", "primary_key": True, "nullable": False},
    "event_type": {"type": "text", "nullable": False},
    "event_version": {"type": "text", "nullable": False},
    "timestamp": {"type": "text", "nullable": False},
    "sequence": {"type": "integer", "nullable": False},
    "aggregate_type": {"type": "text", "nullable": False},
    "aggregate_id": {"type": "text", "nullable": False},
    "payload": {"type": "text", "nullable": False},
    "auth": {"type": "text", "nullable": True},
    "meta": {"type": "text", "nullable": True},
}

# The four indexes of section 10, each over the columns its projection pattern filters or orders by.
_INDEXES = {
    "idx_event_type": {"columns": ["event_type"]},
    "idx_aggregate": {"columns": ["aggregate_type", "aggregate_id"]},
    "idx_timestamp": {"columns": ["timestamp"]},
    "idx_sequence": {"columns": ["aggregate_id", "sequence"]},
}


def event_log_schema() -> dict:
    """The honest_event_log table as a honest-persist schema (section 10). Pure data: a fresh
    `{"honest_event_log": Table}` dict persist can diff and apply. observe never imports persist."""
    return {
        "honest_event_log": {
            "columns": {name: dict(column) for name, column in _COLUMNS.items()},
            "primary_key": ["event_id"],
            "indexes": {name: dict(index) for name, index in _INDEXES.items()},
        }
    }


def event_log_manifest() -> dict:
    """The append-only manifest for the event log (section 10): the table name, the append-only
    declaration persist reads to reject UPDATE and DELETE, and the embedded schema. Pure data."""
    return {"table": "honest_event_log", "append_only": True, "schema": event_log_schema()["honest_event_log"]}

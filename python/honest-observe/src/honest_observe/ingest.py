"""External source ingestion (section 8c): folding the outside world into the one log.

Events also arrive from systems honest-observe does not instrument — third-party webhooks, partner
systems, legacy services, IoT devices. They reach the one log through a declared ingestion contract:
a per-source translator converts a raw event into the canonical envelope (section 2) or returns a
rejection; rejections are data, not exceptions, and land in their own append-only log.

This module holds the rejection record (section 8c.5) and the honest_rejection_log table (section
8c.7). The record is pure assembly — the impure rejection_id and received_at are stamped at the ingest
boundary and passed in, exactly as the event envelope takes its id and timestamp. The table is pure
data observe owns and persist applies, the same one-way arrangement as the event log: observe is stored
by persist and never imports it. The ingest HTTP endpoint, the per-source auth, and the translators
themselves are the boundary's and the adopter's.
"""

# The seven rejection-record fields (section 8c.5), in record order; the two JSON partitions and every
# framework field are NOT NULL — a rejection always names its source, reason, and the raw event it kept.
_REJECTION_COLUMNS = {
    "rejection_id": {"type": "text", "primary_key": True, "nullable": False},
    "received_at": {"type": "text", "nullable": False},
    "source": {"type": "text", "nullable": False},
    "reason_code": {"type": "text", "nullable": False},
    "reason_detail": {"type": "text", "nullable": False},
    "raw_event": {"type": "text", "nullable": False},
    "translator_version": {"type": "text", "nullable": False},
}

# Indexes for the forensics the rejection log exists to answer: by source and reason ("every Stripe
# unrecognized-shape rejection"), and by arrival time ("in the last 24 hours").
_REJECTION_INDEXES = {
    "idx_source": {"columns": ["source"]},
    "idx_reason": {"columns": ["reason_code"]},
    "idx_received": {"columns": ["received_at"]},
}


def rejection(source, reason_code, reason_detail, raw_event, translator_version, rejection_id, received_at) -> dict:
    """A rejection record (section 8c.5): the raw event preserved verbatim for forensics, with the
    source, reason, and the translator version that failed it. Pure — rejection_id and received_at are
    stamped at the ingest boundary and passed in."""
    return {
        "rejection_id": rejection_id,
        "received_at": received_at,
        "source": source,
        "reason_code": reason_code,
        "reason_detail": reason_detail,
        "raw_event": raw_event,
        "translator_version": translator_version,
    }


def rejection_log_schema() -> dict:
    """The honest_rejection_log table as a honest-persist schema (section 8c.7). Pure data: a fresh
    one-table schema persist can diff and apply. observe never imports persist."""
    return {
        "honest_rejection_log": {
            "columns": {name: dict(column) for name, column in _REJECTION_COLUMNS.items()},
            "primary_key": ["rejection_id"],
            "indexes": {name: dict(index) for name, index in _REJECTION_INDEXES.items()},
        }
    }


def rejection_log_manifest() -> dict:
    """The append-only manifest for the rejection log (section 8c.7): the table name, the append-only
    declaration persist reads to reject UPDATE and DELETE, and the embedded schema. Pure data."""
    return {"table": "honest_rejection_log", "append_only": True, "schema": rejection_log_schema()["honest_rejection_log"]}

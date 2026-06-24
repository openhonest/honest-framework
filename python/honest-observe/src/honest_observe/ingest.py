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


def identity_claimed(canonical_id, external_system, external_id, evidence, asserted_by) -> dict:
    """The identity.claimed event (section 8c.3): an append-only claim that an external system's id maps
    to a canonical id, with the evidence for the mapping and who asserted it. Pure — claims are events,
    so identity resolution is itself answered by reading the log."""
    return {
        "event_type": "identity.claimed",
        "payload": {"canonical_id": canonical_id, "external_system": external_system, "external_id": external_id, "evidence": evidence, "asserted_by": asserted_by},
    }


def identity_unknown(external_id, source) -> dict:
    """The identity.unknown event (section 8c.3): a translator met an external id it could not resolve.
    Pure. A background link attempts resolution and emits new claims."""
    return {"event_type": "identity.unknown", "payload": {"external_id": external_id, "source": source}}


def fold_identity_claims(events) -> dict:
    """The identity-binding projection (section 8c.3): fold identity.claimed events into a lookup keyed
    by external system then external id, returning {bindings, conflicts}. A repeated claim to the same
    canonical id is harmless; a claim to a different canonical id for an already-bound external id is a
    conflict recorded for human adjudication, never a silent overwrite. Pure.

    The spec's conceptual key is (external_system, external_id); it is encoded here as a nested mapping
    so the result stays plain JSON-serializable data."""
    bindings = {}
    conflicts = []
    for event in (e for e in events if e["event_type"] == "identity.claimed"):
        payload = event["payload"]
        system, external_id, canonical_id = payload["external_system"], payload["external_id"], payload["canonical_id"]
        existing = bindings.get(system, {}).get(external_id)
        if existing is not None and existing != canonical_id:
            conflicts.append({"external_system": system, "external_id": external_id, "existing": existing, "claimed": canonical_id})
        else:
            bindings.setdefault(system, {})[external_id] = canonical_id
    return {"bindings": bindings, "conflicts": conflicts}


def resolve_identity(external_id, source, bindings):
    """Resolve an external id to its canonical id (section 8c.3): look it up in the bindings under its
    source. None when the source or the id is not bound. Pure."""
    return bindings.get(source, {}).get(external_id)

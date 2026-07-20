"""Evidence assembly and the reproducibility hash (spec §3). Assembling the items from the world —
reading observe's log, running blame, loading config — is boundary I/O and lives at the edge; these
functions receive items already read and stay pure."""

import hashlib
import json


def evidence_hash(items):
    """A pure, order-independent, change-sensitive digest of the evidence items (§3). The same set of
    items in any order yields the same hash; any change to an item changes it. The hash is the key
    that proves the same evidence set was searched when an attestation is re-verified."""
    canonical = json.dumps(sorted(json.dumps(item, sort_keys=True) for item in items))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evidence_set(items):
    """Assemble a bounded evidence set and stamp its reproducibility hash (§3)."""
    return {"items": list(items), "hash": evidence_hash(items)}

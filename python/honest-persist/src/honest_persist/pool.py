"""The pool layer's routing decision (section 8.1): which pool a manifest targets.

Pools are an internal concern — the caller never receives, manages, or closes one. It sends a
manifest, and persist routes the operation to the right pool by the manifest's routing keys. This
module is the pure part of that: resolving a manifest to a pool selector. Creating, caching, and
tearing down the actual connection pools, and the lifecycle treatment (section 8.2), are the I/O
pool registry that sits on top. The routing keys must be bounded Set recognizers in the application
vocabulary (section 8.4, enforced structurally by honest-check HC-P013), so a manifest cannot carry
an arbitrary database identifier — but that is a lint-time guarantee, not this function's job.
"""

from honest_type import err, ok

from honest_persist.instrument import pool_fault

# Section 8.2: how persist treats a database on first contact and at startup.
POOL_LIFECYCLES = frozenset({"persistent", "ephemeral", "on_demand"})


def resolve_pool_key(manifest):
    """Resolve a manifest to its pool selector (section 8.1). Pure: a `db_id` selects a registered
    database, a `tenant_id` a per-tenant one, an optional `credential` a variant, and `db_lifecycle`
    the treatment (default `persistent`). Returns ok(selector) or err(unknown_database) when the
    manifest names no database. The registry lookup and pool creation are the I/O layer's job."""
    db_id = manifest.get("db_id")
    tenant_id = manifest.get("tenant_id")
    if db_id is None and tenant_id is None:
        return err(pool_fault("unknown_database", "manifest carries neither db_id nor tenant_id"))
    return ok(
        {
            "database": db_id if db_id is not None else tenant_id,
            "kind": "db_id" if db_id is not None else "tenant_id",
            "credential": manifest.get("credential"),
            "lifecycle": manifest.get("db_lifecycle", "persistent"),
        }
    )

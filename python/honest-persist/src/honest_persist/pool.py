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

from honest_persist.apply import apply
from honest_persist.instrument import pool_fault
from honest_persist.instrumented import emit_pool_event
from honest_persist.schema import diff

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


def empty_pool_registry():
    """An empty pool registry (section 8.1): the cache of pools persist has created, as a value.
    Pools are an internal concern, so the cache is threaded through `get_pool`, never hidden state."""
    return {}


def _pool_key(selector):
    """The cache key for a pool selector (section 8.1): one pool per (database, credential variant)."""
    return selector["database"] + ":" + (selector["credential"] or "")


async def get_pool(registry, manifest, connect, now, emit=None):
    """Route a manifest to a connection, creating and caching a pool on first contact and reusing it
    after (section 8.1). The routing is pure (resolve_pool_key); the one I/O seam is the injected
    `connect`, which the adopter supplies for their driver. Each cache entry records the connection,
    its lifecycle, and the time `now` it was last used (the caller reads the clock; this stays a
    value), so an on_demand pool can later be reaped (section 8.2). On first contact it emits a
    `created` pool event through the injected `emit` (section 8.8). Returns (result, registry):
    ok(connection) or err(unknown_database) when the manifest names no database; the returned
    registry carries the newly created or touched pool, keeping the cache a threaded value."""
    routed = resolve_pool_key(manifest)
    if "err" in routed:
        return routed, registry
    selector = routed["ok"]
    key = _pool_key(selector)
    if key in registry:
        entry = registry[key]
        return ok(entry["conn"]), {**registry, key: {**entry, "last_used": now}}
    connection = await connect(selector)
    entry = {"conn": connection, "lifecycle": selector["lifecycle"], "last_used": now}
    await emit_pool_event(emit, selector["database"], "created", 1, 1, 0, None, None, None)
    return ok(connection), {**registry, key: entry}


def is_idle(last_used_ns, now_ns, threshold_ms):
    """True when a pool has been idle longer than the threshold (section 8.2). Pure."""
    return (now_ns - last_used_ns) > threshold_ms * 1_000_000


async def reap_idle(registry, now_ns, threshold_ms, close, emit=None):
    """Close and evict the on_demand pools idle past the threshold (section 8.2); persistent and
    ephemeral pools are never reaped. `close` is the injected I/O that closes each connection, and a
    `closed` pool event is emitted for each through the injected `emit` (section 8.8). Returns the
    registry with the reaped pools removed — the cache stays a threaded value."""
    kept = {}
    for key, entry in registry.items():
        if entry["lifecycle"] == "on_demand" and is_idle(entry["last_used"], now_ns, threshold_ms):
            await close(entry["conn"])
            await emit_pool_event(emit, key.split(":", 1)[0], "closed", 1, 0, 0, None, None, None)
        else:
            kept[key] = entry
    return kept


def new_pool(connections):
    """A pool of connections, held as a value (section 8.1): the idle connections and how many are in
    use. Pure."""
    return {"size": len(connections), "idle": list(connections), "active": 0}


def acquire_connection(pool):
    """Take an idle connection from the pool (section 8.1). Returns (result, pool): ok(connection)
    with the connection moved to active, or err(pool_exhausted) when every connection is in use, the
    pool unchanged. Pure."""
    if not pool["idle"]:
        return err(pool_fault("pool_exhausted", "every connection in the pool is in use")), pool
    connection = pool["idle"][0]
    return ok(connection), {"size": pool["size"], "idle": pool["idle"][1:], "active": pool["active"] + 1}


def release_connection(pool, connection):
    """Return a connection to the pool's idle set (section 8.1). Returns the new pool. Pure."""
    return {"size": pool["size"], "idle": [*pool["idle"], connection], "active": pool["active"] - 1}


async def lease_connection(pool, db_id, emit):
    """Acquire a connection, emitting a pool `exhausted` event when every connection is in use
    (section 8.8). Returns (result, pool). The acquire is pure; the one I/O is the injected emit."""
    result, pool = acquire_connection(pool)
    if "err" in result:
        await emit_pool_event(emit, db_id, "exhausted", pool["size"], pool["active"], 1, None, "pool_exhausted", None)
    return result, pool


async def open_pool(db_id, connect, size, emit):
    """Open a pool of `size` connections through the injected `connect`, emitting a `created` event
    (section 8.1, 8.8). I/O."""
    connections = []
    for _ in range(size):
        connections.append(await connect({"database": db_id}))
    pool = new_pool(connections)
    await emit_pool_event(emit, db_id, "created", size, 0, 0, None, None, None)
    return pool


async def close_pool(pool, db_id, close, emit):
    """Close every idle connection in the pool through the injected `close`, emitting a `closed`
    event (section 8.8). I/O."""
    for connection in pool["idle"]:
        await close(connection)
    await emit_pool_event(emit, db_id, "closed", pool["size"], pool["active"], 0, None, None, None)
    return pool


async def recreate_ephemeral(config, connect, dialect, now):
    """Recreate the schema of each ephemeral database at server startup, in configuration order
    (section 8.2): connect, apply the target schema to the fresh database, and cache the pool. The
    data does not survive a restart — the schema is rebuilt from the configuration each time, which
    is what makes ephemeral databases right for test, scratch, and session-scoped storage. The
    selection and ordering are pure; the connect and apply are I/O. Returns the pool registry holding
    the recreated ephemeral pools."""
    registry = empty_pool_registry()
    for database in config:
        if database.get("db_lifecycle") != "ephemeral":
            continue
        manifest = {"db_id": database["db_id"], "db_lifecycle": "ephemeral"}
        result, registry = await get_pool(registry, manifest, connect, now)
        await apply(diff({}, database["schema"]), database["schema"], result["ok"], dialect)
    return registry

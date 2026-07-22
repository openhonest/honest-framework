"""The instrumented query boundary (section 8.5): run a query and emit `hf.persist.query`.

This is the I/O boundary that wraps the pure query execution with observability. `execute()` is
already an I/O boundary; emitting an event from it is the same pattern as any other boundary calling
`emit` — and, like every honest-framework instrumentation, the emit is *injected*, never imported,
so persist stays one-way decoupled from honest-observe (persist -> observe, never the reverse). The
emit never blocks the query result and its failure is swallowed; a query that fails still emits, with
the fault code, then re-raises so the outer boundary can turn it into output. When no emit is wired
in, instrumentation is skipped entirely — zero overhead when disabled.

This whole file is the boundary: it reads the clock, catches at the I/O edge, classifies the
exception that names the fault, and logs a swallowed emit failure to stderr. Those are exactly the
behaviours the linter forbids in pure business logic, so HC-P004/HC-P002/HC-P005 are disabled here.
"""

# honest: disable HC-P004, HC-P002, HC-P005: this module is the instrumented database boundary: it executes queries, reports driver errors as fault values, and guards primitive shapes

import sys
import time

from honest_persist.execute import execute
from honest_persist.instrument import build_pool_event, build_query_event, extract_table


async def _safe_emit(emit, aggregate_id, payload):
    """Emit one hf.persist.query through the injected emit (section 8.5). A failure in emit is logged
    to stderr and swallowed — it must never cause a query to fail. I/O."""
    try:
        await emit("hf.persist.query", "persist", aggregate_id, payload)
    except Exception as exc:
        print(f"honest-persist: query event emit failed: {exc}", file=sys.stderr)


async def emit_pool_event(emit, db_id, event, pool_size, active, waiting, duration_ns, fault_code, message):
    """Emit one hf.persist.pool through the injected emit on a pool lifecycle transition (section
    8.8) — created, exhausted, retry, closed, or error — so pool health is in the same queryable log.
    Swallows a failing emit, and is a no-op when no emit is wired in. I/O."""
    if emit is None:
        return
    payload = build_pool_event(db_id, event, pool_size, active, waiting, duration_ns, fault_code, message)
    try:
        await emit("hf.persist.pool", "pool", db_id, payload)
    except Exception as exc:
        print(f"honest-persist: pool event emit failed: {exc}", file=sys.stderr)


async def instrumented_execute(query, conn, emit, db_id, op, request_id, development_mode):
    """Run a query and emit hf.persist.query through the injected emit (section 8.5). A query that
    fails still emits (with the fault code) and re-raises; a failing emit never breaks the query. When
    emit is None the instrumentation is skipped entirely. I/O."""
    if emit is None:
        return await execute(query, conn)
    table = extract_table(query["sql"])
    aggregate_id = db_id + ":" + table
    start = time.perf_counter_ns()
    try:
        result = await execute(query, conn)
    except Exception as exc:
        duration = time.perf_counter_ns() - start
        fault = type(exc).__name__
        await _safe_emit(emit, aggregate_id, build_query_event(db_id, table, op, 0, duration, query["sql"], request_id, fault, development_mode))
        raise
    duration = time.perf_counter_ns() - start
    await _safe_emit(emit, aggregate_id, build_query_event(db_id, table, op, len(result), duration, query["sql"], request_id, None, development_mode))
    return result

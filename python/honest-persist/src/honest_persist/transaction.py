"""Transactions (section 7.5): several writes as one all-or-nothing step.

The I/O boundary that groups writes so a half-applied change is never seen. Async, like
execute (section 7.4); the connection is the same duck-typed collaborator with three more
awaited methods — `begin()`, `commit()`, `rollback()`. On any write failure the transaction
rolls back and returns a typed fault carrying the failing index; otherwise every write commits
together.

Catching is sanctioned here, exactly as in apply (section 5.2): a transaction cannot roll back
without seeing the failure, so this one boundary function turns a driver error into a fault. The
catch rule (HC-P002) is therefore disabled for this file alone; everywhere else faults flow as
data. The boundary also reads the clock to time the transaction and logs a swallowed instrumentation
failure to stderr (req 14), so HC-P004 is disabled here too — both are boundary behaviours.
"""

# honest: disable HC-P004, HC-P002: this module is the database boundary: it opens transactions and turns driver errors into fault values

import sys
import time

from honest_type import err, fault, ok

from honest_persist.execute import execute_many
from honest_persist.instrument import build_transaction_event


async def _emit_transaction(emit, db_id, write_count, outcome, failed_at, duration_ns, request_id):
    """Emit one hf.persist.transaction through the injected emit (req 14, section 8), keyed by the db.
    A failure in emit is logged to stderr and swallowed — instrumentation must never break a
    transaction. No-op when no emit is wired in. I/O."""
    if emit is None:
        return
    payload = build_transaction_event(db_id, write_count, outcome, failed_at, duration_ns, request_id)
    try:
        await emit("hf.persist.transaction", "transaction", db_id, payload)
    except Exception as exc:
        print(f"honest-persist: transaction event emit failed: {exc}", file=sys.stderr)


async def transaction(writes, conn, emit=None, db_id="", request_id=None):
    """Run `writes` as one all-or-nothing transaction (section 7.5). I/O. Returns
    ok({results: [rows_affected, ...]}) on commit, or err(fault 'write_failed') with the failing
    write's index after rolling back. Emits one hf.persist.transaction through the injected emit (req
    14): `ok` on commit, `constraint_violation` with the failing index on rollback; a failing emit
    never breaks the transaction, and no event is emitted when no emit is wired in."""
    start = time.perf_counter_ns()
    await conn.begin()
    results = []
    for index, write in enumerate(writes):
        try:
            results.append(await execute_many(write, conn))
        except Exception as exc:
            await conn.rollback()
            await _emit_transaction(emit, db_id, len(writes), "constraint_violation", index, time.perf_counter_ns() - start, request_id)
            return err(fault("write_failed", str(exc), "server", {"failed_at": index}))
    await conn.commit()
    await _emit_transaction(emit, db_id, len(writes), "ok", None, time.perf_counter_ns() - start, request_id)
    return ok({"results": results})

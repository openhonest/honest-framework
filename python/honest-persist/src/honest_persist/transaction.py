"""Transactions (section 7.5): several writes as one all-or-nothing step.

The I/O boundary that groups writes so a half-applied change is never seen. Async, like
execute (section 7.4); the connection is the same duck-typed collaborator with three more
awaited methods — `begin()`, `commit()`, `rollback()`. On any write failure the transaction
rolls back and returns a typed fault carrying the failing index; otherwise every write commits
together.

Catching is sanctioned here, exactly as in apply (section 5.2): a transaction cannot roll back
without seeing the failure, so this one boundary function turns a driver error into a fault. The
catch rule (HC-P002) is therefore disabled for this file alone; everywhere else faults flow as
data.
"""

# honest: disable HC-P002

from honest_type import err, fault, ok

from honest_persist.execute import execute_many


async def transaction(writes, conn):
    """Run `writes` as one all-or-nothing transaction (section 7.5). I/O. Returns
    ok({results: [rows_affected, ...]}) on commit, or err(fault 'write_failed') with the failing
    write's index after rolling back."""
    await conn.begin()
    results = []
    for index, write in enumerate(writes):
        try:
            results.append(await execute_many(write, conn))
        except Exception as exc:
            await conn.rollback()
            return err(fault("write_failed", str(exc), "server", {"failed_at": index}))
    await conn.commit()
    return ok({"results": results})

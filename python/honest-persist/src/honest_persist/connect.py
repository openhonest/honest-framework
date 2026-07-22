"""Resilient connection establishment (section 8.8, 8.3): connect with retry on transient failure.

The pool layer's one place that turns a driver connection error into control flow. A connection
attempt can fail two ways: transiently, where the database is momentarily unreachable and a retry
may succeed (`unresolvable_dsn`), or fatally, where the database refused the credential and no
number of retries will help (`credential_rejected`). This boundary catches the driver error,
consults the injected pure `classify` for the fault code and the pure `should_retry` decision
(section 8.2 of pool.py), and either retries after emitting a `retry` event and sleeping the
backoff, or gives up after emitting an `error` event and returning a typed fault.

Catching is sanctioned here, exactly as in transaction (section 7.5) and apply (section 5.2): the
retry loop cannot decide whether to retry without seeing the failure, so this one boundary function
turns a driver error into a fault. The catch rule (HC-P002) is therefore disabled for this file
alone; everywhere else faults flow as data. The clock is not read here — the backoff is computed
purely from the attempt number and the wait is the injected `sleep` — so no I/O directive is needed.
"""

# honest: disable HC-P002: the connection boundary reports a failed connect as a fault value rather than raising

from honest_type import err, ok

from honest_persist.instrument import pool_fault
from honest_persist.instrumented import emit_pool_event
from honest_persist.pool import new_pool, should_retry
from honest_persist.queue import backoff_delay


async def connect_with_retry(selector, connect, classify, retries, base_ms, sleep, emit):
    """Establish a connection through the injected `connect`, retrying transient failures with
    exponential backoff (section 8.8). On each failed attempt the injected pure `classify` maps the
    driver error to a fault code, and `should_retry` decides: a transient fault (unresolvable_dsn)
    emits a `retry` event, sleeps `backoff_delay(attempt, base_ms)` through the injected `sleep`, and
    tries again; a fatal one (credential_rejected) or a run out of attempts emits an `error` event and
    returns the typed fault. Returns ok(connection) or err(fault). I/O."""
    db_id = selector["database"]
    attempt = 0
    while True:
        try:
            return ok(await connect(selector))
        except Exception as exc:
            code = classify(exc)
            if should_retry(attempt, retries, code):
                await emit_pool_event(emit, db_id, "retry", 0, 0, 0, None, code, str(exc))
                attempt = attempt + 1
                await sleep(backoff_delay(attempt, base_ms))
            else:
                await emit_pool_event(emit, db_id, "error", 0, 0, 0, None, code, str(exc))
                return err(pool_fault(code, str(exc)))


async def open_pool(db_id, connect, classify, close, size, retries, base_ms, sleep, emit):
    """Open a pool of `size` connections, each established resiliently through `connect_with_retry`
    (section 8.1, 8.8). A `created` event fires once every connection is open. If any connection
    cannot be established, the connections already opened are closed through the injected `close` so
    none leak, and the establishment fault is returned. Returns ok(pool) or err(fault). I/O."""
    opened = []
    for _ in range(size):
        result = await connect_with_retry({"database": db_id}, connect, classify, retries, base_ms, sleep, emit)
        if "err" in result:
            for connection in opened:
                await close(connection)
            return result
        opened.append(result["ok"])
    pool = new_pool(opened)
    await emit_pool_event(emit, db_id, "created", size, 0, 0, None, None, None)
    return ok(pool)

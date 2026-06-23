"""The write-queue supervisor and its durability (section 8.6): the I/O that keeps the optimistic
write queue durable across restarts and drains it with retry until it succeeds or stalls.

queue.py holds the pure core (the queue as a value, its JSONL form, the backoff schedule, the stall
limit). This file is the boundary on top: writing and reading the JSONL file so pending writes survive
a restart, and the supervised drain that retries and — once the queue has been failing past the limit
— emits hf.persist.queue_stalled and raises the fault, so a write is never silently discarded. The
background loop itself is a thin caller: retry `supervise_drain`, sleeping `backoff_delay` between
attempts, until it drains or raises. Reading and writing the file, catching at the drain boundary, and
logging a swallowed emit are boundary behaviours, so HC-P004/P002 are disabled file-wide here.
"""

# honest: disable HC-P004, HC-P002

import sys
from pathlib import Path

from honest_persist.queue import backoff_delay, drain_queue, enqueue_write, is_stalled, queue_from_jsonl, queue_to_jsonl


def save_queue(queue, path):
    """Persist the write queue to its JSONL file (section 8.6), so pending writes survive a restart.
    I/O."""
    Path(path).write_text(queue_to_jsonl(queue), encoding="utf-8")


def load_queue(path):
    """Load the write queue from its JSONL file (section 8.6), or an empty queue when the file does
    not exist. I/O."""
    file = Path(path)
    if not file.exists():
        return []
    return queue_from_jsonl(file.read_text(encoding="utf-8"))


async def _emit_queue_stalled(emit, queue_depth, stalled_for_ns):
    """Emit hf.persist.queue_stalled through the injected emit (section 8.6); swallows a failing emit
    and is a no-op when no emit is wired in, so it never blocks the fault from being raised. I/O."""
    if emit is None:
        return
    payload = {"queue_depth": queue_depth, "stalled_for_ns": stalled_for_ns, "fault_code": "queue_stalled"}
    try:
        await emit("hf.persist.queue_stalled", "persist", "write_queue", payload)
    except Exception as exc:
        print(f"honest-persist: queue_stalled emit failed: {exc}", file=sys.stderr)


async def supervise_drain(queue, conn, execute, primary_key, now_ns, first_failure_ns, emit):
    """One supervised drain attempt (section 8.6): try to drain the queue; on success it is cleared
    and the failure clock reset; on failure the queue is kept and the failure clock starts, and once
    it has been failing past the limit a hf.persist.queue_stalled event is emitted and the fault
    raised — writes are never silently discarded. Returns (queue, first_failure_ns, drained). I/O."""
    try:
        drained = await drain_queue(queue, conn, execute, primary_key)
    except Exception:
        started = now_ns if first_failure_ns is None else first_failure_ns
        if is_stalled(started, now_ns):
            await _emit_queue_stalled(emit, len(queue), now_ns - started)
            raise
        return queue, started, False
    return drained, None, True


def enqueue_durable(queue, op, table, row, path):
    """Append a pending write and persist the queue to its JSONL file (section 8.6), so the write
    survives a restart before it has reached the backend. Returns the new queue. I/O."""
    new_queue = enqueue_write(queue, op, table, row)
    save_queue(new_queue, path)
    return new_queue


async def run_drain_loop(queue, conn, execute, primary_key, base_ms, now, sleep, emit):
    """Drain the queue in the background, retrying a failing backend with exponential backoff until it
    drains or stalls (section 8.6). `now` reads the clock and `sleep` waits, both injected so the loop
    is testable; supervise_drain raises once the queue has failed past the limit. Returns the drained
    (empty) queue. I/O."""
    first_failure = None
    attempt = 0
    while True:
        queue, first_failure, drained = await supervise_drain(queue, conn, execute, primary_key, now(), first_failure, emit)
        if drained:
            return queue
        attempt += 1
        await sleep(backoff_delay(attempt, base_ms))

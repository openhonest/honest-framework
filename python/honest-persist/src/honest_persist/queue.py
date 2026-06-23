"""The optimistic write queue (section 8.6): writes to a high-latency backend return immediately and
persist in the background, while reads stay transparent.

The queue is a value, threaded through like the pool registry — never hidden state. `enqueue_write`
appends a pending write; `merge_pending` folds the pending writes for a table into a SELECT result by
primary key, so a pending insert appears, a pending update overrides, and a pending delete vanishes,
all before the write has reached the backend; `drain_queue` persists the pending writes through an
injected `execute`. The background supervisor, JSONL durability, retry and backoff, and stall
detection are the I/O layer on top; everything here is the pure data core plus the one drain boundary,
so this file needs no linter directives.
"""

from honest_persist.query import delete, insert, update


def empty_write_queue():
    """An empty write queue (section 8.6): the pending writes, held as a value."""
    return []


def enqueue_write(queue, op, table, row):
    """Append a pending write to the queue (section 8.6). Returns a new queue; never mutates."""
    return [*queue, {"op": op, "table": table, "row": row}]


def merge_pending(rows, queue, table, primary_key):
    """Fold the queue's pending writes for `table` into a SELECT result, by primary key (section
    8.6): a pending insert or update sets the row, a pending delete removes it, so a write is visible
    in reads before it reaches the backend. Pure."""
    merged = {row[primary_key]: row for row in rows}
    for write in queue:
        if write["table"] != table:
            continue
        key = write["row"][primary_key]
        if write["op"] == "delete":
            merged.pop(key, None)
        else:
            merged[key] = write["row"]
    return list(merged.values())


def _insert_query(table, row, primary_key):
    return insert(table, row)


def _update_query(table, row, primary_key):
    values = {name: value for name, value in row.items() if name != primary_key}
    return update(table, values, {primary_key: row[primary_key]})


def _delete_query(table, row, primary_key):
    return delete(table, {primary_key: row[primary_key]})


# The Query a pending write becomes, by its op — a dispatch table, not a branch on the op value.
_WRITE_QUERY = {"insert": _insert_query, "update": _update_query, "delete": _delete_query}


def _write_query(write, primary_key):
    """The Query for one pending write (section 8.6): insert / update / delete by op."""
    return _WRITE_QUERY[write["op"]](write["table"], write["row"], primary_key)


async def drain_queue(queue, conn, execute, primary_key):
    """Persist each pending write to the backend through the injected `execute`, in order (section
    8.6). Returns the drained (empty) queue. I/O."""
    for write in queue:
        await execute(_write_query(write, primary_key), conn)
    return empty_write_queue()

"""Zero-downtime cutover (section 9.1): move a live database to a new home in reversible phases.

Cutover is an operational workflow, not a schema primitive: it composes the diff/apply and query
layers, it does not replace them. A move runs in four phases — bulk transfer (copy rows in
foreign-key order, resumable), mirror (dual-write to both until they converge), promote (switch reads
to the destination), and detach (stop writing the source). Each phase up to promotion is reversible.

The phases, their ordering, the read target of each, and the batch query are pure decisions; the bulk
copy and the mirror write are the only I/O, and they go through the ordinary query layer (section 7)
so the destination is never written by a path that bypasses the library. No catch lives here — a
failure propagates as it does from any boundary.
"""

from honest_persist.deps import topological_sort
from honest_persist.query import insert

# The cutover phases in order, and the next phase from each (detach is terminal) — section 9.1.
_CUTOVER_NEXT = {"bulk_transfer": "mirror", "mirror": "promote", "promote": "detach", "detach": "detach"}
# Which database reads go to in each phase: the source until promotion, the destination after.
_CUTOVER_READS = {"bulk_transfer": "source", "mirror": "source", "promote": "destination", "detach": "destination"}


def cutover_phases():
    """The ordered cutover phases (section 9.1): bulk transfer, mirror, promote, detach. Pure."""
    return ["bulk_transfer", "mirror", "promote", "detach"]


def cutover_advance(phase):
    """The next cutover phase after `phase` (section 9.1); detach is terminal and stays itself. Pure."""
    return _CUTOVER_NEXT[phase]


def cutover_read_target(phase):
    """Which database reads go to in a cutover phase (section 9.1): the source until promotion, the
    destination from promotion onward. Pure."""
    return _CUTOVER_READS[phase]


def cutover_plan(schema):
    """The tables in foreign-key order for bulk transfer (section 9.1): each table after every table
    it references, so foreign-key targets exist at the destination before their referrers. A cyclic
    reference graph falls back to the declared order. Pure."""
    names = list(schema)
    position = {name: index for index, name in enumerate(names)}
    deps = {}
    for index, name in enumerate(names):
        referenced = []
        for column in schema[name].get("columns", {}).values():
            reference = column.get("references")
            if reference:
                target = reference.rsplit(".", 1)[0]
                if target in position and target != name:
                    referenced.append(position[target])
        deps[index] = referenced
    order = topological_sort(names, deps)
    return names if order is None else [names[index] for index in order]


def copy_batch_query(table, primary_key, after, limit):
    """The query reading the next batch of rows to copy in a bulk transfer (section 9.1): the rows
    after the last-copied primary key, ordered by it and limited to the batch size, so the transfer
    is resumable from recorded progress. Pure."""
    if after is None:
        return {"sql": "SELECT * FROM " + table + " ORDER BY " + primary_key + " LIMIT :limit", "params": {"limit": limit}}
    return {
        "sql": "SELECT * FROM " + table + " WHERE " + primary_key + " > :after ORDER BY " + primary_key + " LIMIT :limit",
        "params": {"after": after, "limit": limit},
    }


async def bulk_copy_table(table, columns, primary_key, source, dest, batch_size):
    """Copy a table's rows from the source to the destination in primary-key batches (section 9.1),
    resumable from the last-copied key. The batch query and the row inserts are built by the pure
    query layer; the reads and writes are I/O. Returns the number of rows copied."""
    copied = 0
    after = None
    while True:
        query = copy_batch_query(table, primary_key, after, batch_size)
        rows = (await source.execute(query["sql"], query["params"]))["rows"]
        for row in rows:
            write = insert(table, {column: row[column] for column in columns})
            await dest.execute(write["sql"], write["params"])
        copied = copied + len(rows)
        if len(rows) < batch_size:
            return copied
        after = rows[-1][primary_key]


async def mirror_write(query, source, dest):
    """Dual-write a query to both the source and the destination during the mirror phase (section
    9.1), so the two converge while the cutover is still reversible. The writes are I/O through the
    ordinary query the caller already built. Returns the source and destination results."""
    return {
        "source": await source.execute(query["sql"], query["params"]),
        "destination": await dest.execute(query["sql"], query["params"]),
    }

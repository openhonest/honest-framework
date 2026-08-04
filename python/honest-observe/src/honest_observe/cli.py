"""The honest-observe CLI (section 9): read the event log and present it.

I/O lives only at the edges. `main` is the dispatch — it takes an injected log reader, clock, projection
registry, and emit, and returns the process exit code — so the whole of the tail/inspect/query behaviour
is exercised as data. The three command handlers are a dispatch table keyed by the subcommand argparse
already validated, never an if/elif chain. `read_event_log` reads the honest_event_log table (section 10)
through honest-persist, and `_entry` is the reusable production wiring: given a connection and a
projection registry, it materializes the log, reads the wall clock, and prints. Obtaining that connection
(the adopter injects the database driver, section 11) and building the registry from application code are
the adopter's integration seam, so `_entry` takes both as arguments.
"""

import argparse
import asyncio
import json

from honest_persist import execute, select

from honest_observe.devtools import (
    format_inspect,
    format_tail_line,
    parse_window,
    run_bucketed_projection,
    run_named_projection,
    since_cutoff,
    tail_matches,
)


def _cmd_tail(args, read, now, registry, emit) -> int:
    """`tail` (section 9.2): print each event that passes the filters as a structured line."""
    since = since_cutoff(now(), args.since) if args.since is not None else None
    for event in read():
        if tail_matches(event, args.source, args.event, args.chain, args.request, since):
            emit(format_tail_line(event))
    return 0


def _cmd_inspect(args, read, now, registry, emit) -> int:
    """`inspect <request_id>` (section 9.3): render one request's execution trace, or surface a client
    fault as data when no such request is in the log."""
    events = read()
    known = any(e.get("aggregate_type") == "request" and e.get("aggregate_id") == args.request_id for e in events)
    if not known:
        emit(f"No request '{args.request_id}' in the log")
        return 1
    emit(format_inspect(args.request_id, events))
    return 0


def _cmd_query(args, read, now, registry, emit) -> int:
    """`query <name>` (section 9.4): run a named projection over the (optionally --since-narrowed) log,
    bucketed by --bucket when given. An unknown projection name is a client fault surfaced as data."""
    events = read()
    if args.since is not None:
        cutoff = since_cutoff(now(), args.since)
        events = [e for e in events if e["timestamp"] >= cutoff]
    bucketed = args.bucket is not None
    result = (
        run_bucketed_projection(registry, args.name, events, parse_window(args.bucket))
        if bucketed
        else run_named_projection(registry, args.name, events)
    )
    if "err" in result:
        emit(result["err"]["message"])
        return 1
    lines = [f"{start} {state}" for start, state in result["ok"]] if bucketed else [str(result["ok"])]
    for line in lines:
        emit(line)
    return 0


# The subcommand dispatch (section 9): the table is the discriminant, resolved on the name argparse has
# already constrained to one of these three.
_COMMANDS = {"tail": _cmd_tail, "inspect": _cmd_inspect, "query": _cmd_query}


def _parser() -> argparse.ArgumentParser:
    """The argument grammar for the three commands (sections 9.2-9.4)."""
    parser = argparse.ArgumentParser(prog="honest-observe", description="Read the event log and present it (section 9).")
    sub = parser.add_subparsers(dest="command", required=True)

    tail = sub.add_parser("tail", help="stream the log as structured lines (section 9.2)")
    tail.add_argument("--source")
    tail.add_argument("--event")
    tail.add_argument("--chain")
    tail.add_argument("--request")
    tail.add_argument("--since")

    inspect = sub.add_parser("inspect", help="render one request's execution trace (section 9.3)")
    inspect.add_argument("request_id")

    query = sub.add_parser("query", help="run a named projection over the log (section 9.4)")
    query.add_argument("name")
    query.add_argument("--since")
    query.add_argument("--bucket")

    return parser


def main(argv, read, now, registry, emit) -> int:
    """Dispatch a CLI invocation (section 9) over an injected log reader, clock, projection registry, and
    emit. Returns the exit code: 0 on success, 1 when a client fault is surfaced as data."""
    args = _parser().parse_args(argv)
    return _COMMANDS[args.command](args, read, now, registry, emit)


def _deserialize(row: dict) -> dict:
    """One honest_event_log row (section 10) back into an event dict: the JSON text columns parsed, the
    nullable auth/meta dropped when absent."""
    event = {
        "event_type": row["event_type"],
        "event_version": row["event_version"],
        "timestamp": row["timestamp"],
        "sequence": row["sequence"],
        "aggregate_type": row["aggregate_type"],
        "aggregate_id": row["aggregate_id"],
        "event_id": row["event_id"],
        "payload": json.loads(row["payload"]),
    }
    for column in ("auth", "meta"):
        if row.get(column) is not None:
            event[column] = json.loads(row[column])
    return event


async def read_event_log(conn) -> list:
    """Read the whole honest_event_log (section 10) in log order through honest-persist. I/O: builds a
    pure select, runs it on the connection, and deserializes each row back into an event."""
    rows = await execute(select("honest_event_log", order_by=["sequence"]), conn)  # honest: ignore HC-ST001: the CLI's read boundary onto the honest-persist event log (section 10) — a select, not a domain-state mutation
    return [_deserialize(row) for row in rows]


def _now() -> str:
    """The wall clock as an ISO timestamp to millisecond precision (Z), matching the event log. I/O."""
    import datetime as dt

    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _entry(argv, conn, registry) -> int:
    """The reusable production entry (section 9): read the honest_event_log through the given connection,
    then run the CLI over it with the wall clock, the given projection registry, and stdout. The adopter
    supplies the connection (their injected database driver, section 11) and the registry (their
    application projections). I/O only."""
    events = asyncio.run(read_event_log(conn))
    return main(argv, lambda: events, _now, registry, print)

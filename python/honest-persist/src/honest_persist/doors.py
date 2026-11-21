"""The input I/O doors: the eight ways the world gets into honest-persist.

session_open opens a database (and is the one door that raises, so a server cannot start on a database
that would not open); query_ask answers a question; lifecycle_stop receives the shutdown signal;
lifecycle_turn runs one drainer's turn; migration_plan, schema_live and schema_declared answer the three
read-only questions; view_refreshes hands out what to schedule. Ported from declaro-persistum, adapted to
honest-persist's bare-union Fault and its NoMatch records.
"""

import os

from honest_persist._util import _pick, _read_or
from honest_persist.io import clock_read, log_write
from honest_persist.orchestrators import (
    lifecycle_catch_up,
    lifecycle_shut_down,
    migration_compare,
    query_answer,
    query_prepare_deposit,
    query_redeem_ticket,
    schema_read_live,
    schema_say_declared,
    schema_say_refreshes,
    session_connect,
)
from honest_persist.types import fault, is_fault, is_no_match, refused

NOTHING = None


# a piece the library read but refused, either a Fault or a NoMatch
_is_refusal = lambda piece: is_fault(piece) or is_no_match(piece)


# --- session_open: the one door that raises (declaration session_open) -------------------------------
class CouldNotOpen(Exception):
    """The one exception this package raises, and only this door raises it. It carries the Fault, and
    str() of it is what an operator reads in the log the platform keeps."""

    def __init__(self, failure):
        self.fault = failure
        super().__init__(_read_or(failure, "message", lambda: str(failure)))


_STATES = {"HONEST_PERSIST_CONNECTIONS": "connections_asked", "HONEST_PERSIST_CREW_SIZE": "crew_asked"}


_not_a_number = lambda name, written: refused(
    "env_not_a_number", f"{name} is set to {written!r}, which is not a whole number",
    {"name": name, "written": written})


# a whole number the env names, or a NoMatch when what is set is not a whole number
_as_count = lambda name, written: _pick(
    written.lstrip("-").isdigit(), lambda: int(written), lambda: _not_a_number(name, written))


_nothing_opened_yet = lambda target, shutdown, primary, token, machine: {
    "target": target, "shutdown": shutdown, "primary": primary, "token": token, **machine,
    "copy_was_here": False, "settings": {}, "permitted": 0, "crew_size": 0, "writers": [],
    "connections": [], "channel": NOTHING,
    "declared": {"models": [], "views": [], "dropping_tables": [], "dropping_views": []},
    "live": {"tables": [], "views": []}, "wanted_schema": {"tables": [], "views": []},
    "needs_migration": False, "migration": {"plan": {"operations": [], "destroys": []}, "applied": 0},
    "database": NOTHING,
}


async def session_open(target, shutdown, primary, token):
    """Open the database the target names, and hand back what every later call reads (declaration
    session_open). Anything that refused the open raises CouldNotOpen carrying the Fault, so a deployment
    cannot bring a server up on a database it never got; inside the package a failure is still a value."""
    def _read_count(name):
        written = os.environ.get(name)
        return _pick(written is None, lambda: NOTHING, lambda: _as_count(name, written))

    def _whatever_refused_it(opened):
        raise CouldNotOpen(opened)

    open_was_refused = {True: _whatever_refused_it, False: lambda opened: opened["database"]}

    async def _machine_wrong(_target, _shutdown, _primary, _token, _machine, refused_m):
        raise CouldNotOpen(refused_m[0])

    async def _go_and_open(target, shutdown, primary, token, machine, _refused):
        opened = await session_connect(_nothing_opened_yet(target, shutdown, primary, token, machine))
        return open_was_refused[_is_refusal(opened)](opened)

    made_sense = {True: _machine_wrong, False: _go_and_open}
    machine = {fills: _read_count(name) for name, fills in _STATES.items()}
    refused_m = list(filter(is_fault, machine.values()))
    return await made_sense[refused_m != []](target, shutdown, primary, token, machine, refused_m)


# --- query_ask (declaration query_ask) ---------------------------------------------------------------
_answering = lambda db, model, written: {
    "db": db, "model": model, "grammar": NOTHING, "written": written, "declaration": NOTHING,
    "statement": NOTHING, "ticket": "", "receipt": NOTHING, "rows": [], "answer": NOTHING}


_the_answer_inside = lambda answered: answered["answer"]


_the_refusal_itself = lambda answered: answered


_WHAT_CAME_BACK = {True: _the_refusal_itself, False: _the_answer_inside}


async def query_ask(db, model, written):
    """Take a question or a declared write, as the caller wrote it, and answer with rows, your own
    objects, a number, true or false, or NOTHING (declaration query_ask). Three return shapes: an Answer,
    a Fault whose category decides a retry, or a NoMatch the library could not read."""
    try:
        answered = await query_answer(_answering(db, model, written))
        return _WHAT_CAME_BACK[_is_refusal(answered)](answered)
    except Exception as raised:  # noqa: BLE001
        stopped = fault("question_raised", f"a question about {model['name']} raised: "
                        f"{type(raised).__name__}: {raised}", "refused", [], {})
        log_write({"event": "question_raised", "level": "error", "why": stopped["message"]})
        return stopped


# --- query_deposit, query_collect: the asynchronous write path (declaration, spec 8.6) --------------
# query_deposit is not awaited: the whole deposit path is synchronous, so it is a plain def (honest-check
# HC-R003 reads the declaration's non-awaited promise against the absence of `async def`). crew_deposit
# leaves a waiter and returns a ticket at once, running nothing, and the read → column-check → compile
# prefix is pure sync functions — nothing on this path awaits. An async host calls it without `await`,
# and crew_deposit's create_future finds the running loop the caller is already inside (spec 8.6).
_depositing = lambda db, model, written: {
    "db": db, "model": model, "written": written, "declaration": NOTHING,
    "statement": NOTHING, "ticket": ""}


_the_ticket_inside = lambda prepared: prepared["ticket"]


_the_deposit_refusal = lambda prepared: prepared


_WHAT_DEPOSIT_CAME_BACK = {True: _the_deposit_refusal, False: _the_ticket_inside}


def query_deposit(db, model, written):
    """Take a declared write, as the caller wrote it, hand it to the crew, and return a ticket at once — a
    claim on a write held as data, not a finished write (declaration query_deposit, spec 8.6). It runs the
    same read, column-check and compile query_ask runs, then refuse_a_read keeps it write-only; a write
    that cannot be read or compiled is refused here and nothing is handed to the crew. Three return
    shapes: the Ticket returned at once, a Fault the library read but refused, a NoMatch it could not
    read. It is not awaited: the deposit is synchronous, so the door returns the moment the crew takes the
    statement and leaves a waiter, without waiting on the write to run."""
    prepared = query_prepare_deposit(_depositing(db, model, written))
    return _WHAT_DEPOSIT_CAME_BACK[_is_refusal(prepared)](prepared)


_collecting = lambda db, ticket: {"db": db, "ticket": ticket, "receipt": NOTHING, "answer": NOTHING}


_the_collect_answer = lambda redeemed: redeemed["answer"]


_the_collect_refusal = lambda redeemed: redeemed


_WHAT_COLLECT_CAME_BACK = {True: _the_collect_refusal, False: _the_collect_answer}


async def query_collect(db, ticket):
    """Redeem a ticket query_deposit handed back and answer with what the write did: the same reply
    query_ask gives a synchronous write — a count — or a Fault (declaration query_collect, spec 8.6). It
    waits on the ticket's own outcome through the crew and shapes the receipt. Three return shapes: the
    Answer, the Fault the write ended on, and a NoMatch for a ticket no crew holds, refused before
    anything is awaited. Failure is per ticket: one ticket's Fault stands on its own."""
    redeemed = await query_redeem_ticket(_collecting(db, ticket))
    return _WHAT_COLLECT_CAME_BACK[_is_refusal(redeemed)](redeemed)


# --- lifecycle_stop, lifecycle_turn (declaration) ---------------------------------------------------
_shutdown_finished = lambda _answered: NOTHING


_shutdown_failed = lambda answered: answered


_SHUTDOWN_SAID = {False: _shutdown_finished, True: _shutdown_failed}


async def lifecycle_stop():
    """Receive the platform's shutdown signal and hand the shutdown off (declaration lifecycle_stop);
    answer NOTHING when the drain finished or a Fault when it could not."""
    try:
        answered = await lifecycle_shut_down({"databases": [], "started_at": clock_read(), "attempts": 0})
        return _SHUTDOWN_SAID[is_fault(answered)](answered)
    except Exception as raised:  # noqa: BLE001
        stopped = fault("shutdown_raised", f"shutting down raised: {type(raised).__name__}: {raised}",
                        "cut_short", [], {})
        log_write({"event": "shutdown_raised", "level": "error", "why": stopped["message"]})
        return stopped


_turn_worked = lambda _answered: NOTHING


_turn_stopped = lambda answered: answered


_TURN_SAID = {False: _turn_worked, True: _turn_stopped}


async def lifecycle_turn(draining):
    """One drainer's turn, which arrives because that drainer woke (declaration lifecycle_turn). Three
    return shapes: NOTHING means the turn did its work, a Fault means a driver answered badly, a NoMatch
    means no driver was asked because the engine word has no driver."""
    try:
        answered = await lifecycle_catch_up({"db": draining["db"], "writer": draining["writer"],
                                             "statement": NOTHING, "writer_waiting": False, "attempts": 0})
        return _TURN_SAID[_is_refusal(answered)](answered)
    except Exception as raised:  # noqa: BLE001
        stopped = fault("turn_raised", f"a turn on {draining['db']['target']} raised: "
                        f"{type(raised).__name__}: {raised}", "refused", [], {})
        log_write({"event": "turn_raised", "level": "error", "why": stopped["message"]})
        return stopped


# --- migration_plan, schema_live, schema_declared, view_refreshes (declaration) ---------------------
_nothing_worked_out_yet = lambda target: {
    "target": target, "connection": NOTHING,
    "declared": {"models": [], "views": [], "dropping_tables": [], "dropping_views": []},
    "live": {"tables": [], "views": []}, "wanted_schema": {"tables": [], "views": []},
    "needs_migration": False, "plan": {"operations": [], "destroys": []}}


_compared_refused = lambda compared: compared


_the_plan_in_it = lambda compared: compared["plan"]


_COMPARISON_REFUSED = {True: _compared_refused, False: _the_plan_in_it}


async def migration_plan(target):
    """Say what a migration would change, and change nothing (declaration migration_plan). A database
    already matching its models answers a plan with no operations; a failure comes back as a value."""
    compared = await migration_compare(_nothing_worked_out_yet(target))
    return _COMPARISON_REFUSED[_is_refusal(compared)](compared)


_nothing_read_yet = lambda target: {"target": target, "connection": NOTHING, "live": NOTHING}


_reading_refused = lambda looked: looked


_the_live_in_it = lambda looked: looked["live"]


_READING_REFUSED = {True: _reading_refused, False: _the_live_in_it}


async def schema_live(target):
    """Answer with what the database holds right now (declaration schema_live). A database holding
    nothing answers an empty schema; a failure comes back as a value."""
    looked = await schema_read_live(_nothing_read_yet(target))
    return _READING_REFUSED[_is_refusal(looked)](looked)


def schema_declared():
    """Answer with the models and views the host declared (declaration schema_declared). It touches no
    database, opens no connection, and is not awaited; schema_say_declared owns the sequence."""
    return schema_say_declared()


def view_refreshes(db):
    """Answer with one schedule declaration per view the host asked to have refreshed, and run none of
    them (declaration view_refreshes). A host that declared no such view gets an empty list; it is not
    awaited and opens nothing."""
    return schema_say_refreshes(db)

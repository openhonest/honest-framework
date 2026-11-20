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
    schema_read_live,
    schema_say_declared,
    schema_say_refreshes,
    session_connect,
)
from honest_persist.types import fault, is_fault, is_no_match, refused

NOTHING = None


def _is_refusal(piece):
    return is_fault(piece) or is_no_match(piece)


# --- session_open: the one door that raises (declaration session_open) -------------------------------
class CouldNotOpen(Exception):
    """The one exception this package raises, and only this door raises it. It carries the Fault, and
    str() of it is what an operator reads in the log the platform keeps."""

    def __init__(self, failure):
        self.fault = failure
        super().__init__(_read_or(failure, "message", lambda: str(failure)))


_STATES = {"HONEST_PERSIST_CONNECTIONS": "connections_asked", "HONEST_PERSIST_CREW_SIZE": "crew_asked"}


def _read_count(name):
    written = os.environ.get(name)
    return _pick(written is None, lambda: _nothing_set(), lambda: _as_count(name, written))


def _nothing_set():
    return NOTHING


def _as_count(name, written):
    return _pick(written.lstrip("-").isdigit(), lambda: int(written), lambda: _not_a_number(name, written))


def _not_a_number(name, written):
    return refused("env_not_a_number", f"{name} is set to {written!r}, which is not a whole number",
                   {"name": name, "written": written})


def _machine():
    return {fills: _read_count(name) for name, fills in _STATES.items()}


def _nothing_opened_yet(target, shutdown, primary, token, machine):
    return {
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
    machine = _machine()
    refused_m = list(filter(is_fault, machine.values()))
    return await _MACHINE_MADE_SENSE[refused_m != []](target, shutdown, primary, token, machine, refused_m)


async def _machine_wrong(_target, _shutdown, _primary, _token, _machine, refused_m):
    raise CouldNotOpen(refused_m[0])


async def _go_and_open(target, shutdown, primary, token, machine, _refused):
    opened = await session_connect(_nothing_opened_yet(target, shutdown, primary, token, machine))
    return _OPEN_WAS_REFUSED[_is_refusal(opened)](opened)


_MACHINE_MADE_SENSE = {True: _machine_wrong, False: _go_and_open}


def _whatever_refused_it(opened):
    raise CouldNotOpen(opened)


def _the_handle_in_it(opened):
    return opened["database"]


_OPEN_WAS_REFUSED = {True: _whatever_refused_it, False: _the_handle_in_it}


# --- query_ask (declaration query_ask) ---------------------------------------------------------------
def _answering(db, model, written):
    return {"db": db, "model": model, "grammar": NOTHING, "written": written, "declaration": NOTHING,
            "statement": NOTHING, "ticket": "", "receipt": NOTHING, "rows": [], "answer": NOTHING}


def _the_answer_inside(answered):
    return answered["answer"]


def _the_refusal_itself(answered):
    return answered


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


# --- lifecycle_stop, lifecycle_turn (declaration) ---------------------------------------------------
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


def _shutdown_finished(_answered):
    return NOTHING


def _shutdown_failed(answered):
    return answered


_SHUTDOWN_SAID = {False: _shutdown_finished, True: _shutdown_failed}


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


def _turn_worked(_answered):
    return NOTHING


def _turn_stopped(answered):
    return answered


_TURN_SAID = {False: _turn_worked, True: _turn_stopped}


# --- migration_plan, schema_live, schema_declared, view_refreshes (declaration) ---------------------
def _nothing_worked_out_yet(target):
    return {"target": target, "connection": NOTHING,
            "declared": {"models": [], "views": [], "dropping_tables": [], "dropping_views": []},
            "live": {"tables": [], "views": []}, "wanted_schema": {"tables": [], "views": []},
            "needs_migration": False, "plan": {"operations": [], "destroys": []}}


async def migration_plan(target):
    """Say what a migration would change, and change nothing (declaration migration_plan). A database
    already matching its models answers a plan with no operations; a failure comes back as a value."""
    compared = await migration_compare(_nothing_worked_out_yet(target))
    return _COMPARISON_REFUSED[_is_refusal(compared)](compared)


def _compared_refused(compared):
    return compared


def _the_plan_in_it(compared):
    return compared["plan"]


_COMPARISON_REFUSED = {True: _compared_refused, False: _the_plan_in_it}


def _nothing_read_yet(target):
    return {"target": target, "connection": NOTHING, "live": NOTHING}


async def schema_live(target):
    """Answer with what the database holds right now (declaration schema_live). A database holding
    nothing answers an empty schema; a failure comes back as a value."""
    looked = await schema_read_live(_nothing_read_yet(target))
    return _READING_REFUSED[_is_refusal(looked)](looked)


def _reading_refused(looked):
    return looked


def _the_live_in_it(looked):
    return looked["live"]


_READING_REFUSED = {True: _reading_refused, False: _the_live_in_it}


def schema_declared():
    """Answer with the models and views the host declared (declaration schema_declared). It touches no
    database, opens no connection, and is not awaited; schema_say_declared owns the sequence."""
    return schema_say_declared()


def view_refreshes(db):
    """Answer with one schedule declaration per view the host asked to have refreshed, and run none of
    them (declaration view_refreshes). A host that declared no such view gets an empty list; it is not
    awaited and opens nothing."""
    return schema_say_refreshes(db)

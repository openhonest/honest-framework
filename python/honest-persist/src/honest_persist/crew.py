"""The crew: N drainers over one room of waiting writes, and the shutdown handler and register.

A caller hands over a write and gets a ticket back at once; a crew of drainers empties the pile. Ported
from declaro-persistum, adapted to honest-persist's bare-union Fault. Nothing in a crew survives the
process: every write that matters has a caller holding a ticket for it, and the write-ahead log is the
queue.
"""

import asyncio
import signal
from uuid import uuid4

from honest_persist._util import _pick, _read_or
from honest_persist.io import log_write
from honest_persist.types import no_match, refused

NOTHING = None


def crew_make():
    """Build a crew with nobody in it yet, and the doorbell a drainer sleeps on (declaration crew_make).
    The two doorbells are not the same bell: `arrived` is rung by a deposit, `stop` is rung once."""
    return {"arrivals": [], "writes": {}, "waiting": {}, "arrived": asyncio.Event(),
            "stop": asyncio.Event(), "drainers": [], "size": 0}


# --- crew_deposit (declaration) ----------------------------------------------------------------------
def _take_a_ticket(crew, statement):
    ticket = uuid4().hex
    crew["arrivals"].append(ticket)
    crew["writes"][ticket] = statement
    crew["waiting"][ticket] = asyncio.get_running_loop().create_future()
    crew["arrived"].set()
    return ticket


def _refuse_empty_write(_crew, statement):
    return refused("empty_write",
                   f"you handed over a write whose text is {statement['text']!r}; there is nothing to "
                   f"run", {})


_DEPOSIT = {True: _take_a_ticket, False: _refuse_empty_write}


def crew_deposit(crew, statement):
    """Hand one write to the crew, leave a waiter, ring the doorbell and take a ticket (declaration
    crew_deposit). Returns at once, having run nothing; blank text is refused."""
    return _DEPOSIT[bool(statement["text"].strip())](crew, statement)


# --- crew_release_ticket (declaration) ---------------------------------------------------------------
async def _no_such_ticket(crew, ticket):
    return refused("no_such_ticket",
                   f"the crew holds no ticket {ticket!r}; it has {len(crew['waiting'])} outstanding", {})


async def _wait_for_the_outcome(crew, ticket):
    waiter = crew["waiting"][ticket]
    try:
        return await waiter
    finally:
        crew["waiting"].pop(ticket, None)


_CREW_KNOWS_IT = {True: _wait_for_the_outcome, False: _no_such_ticket}


async def crew_release_ticket(crew, ticket):
    """Await this caller's own waiter and take its ticket off the crew (declaration crew_release_ticket).
    A ticket the crew does not hold is refused at once, because no outcome for it is ever posted."""
    return await _CREW_KNOWS_IT[ticket in crew["waiting"]](crew, ticket)


# --- refuse_an_unknown_ticket (declaration, spec 8.6) ------------------------------------------------
def _tickets_held_by(crew):
    """Every ticket the crew is holding: the keys of the writes that arrived and the waiters parked on
    them. Only dict keys are read, never a Waiter handle, which is why this is pure."""
    return sorted(set(crew["writes"]) | set(crew["waiting"]))


def _crew_holds_it(_crew, _ticket):
    return NOTHING


def _crew_does_not_hold_it(crew, ticket):
    return no_match("tickets", [ticket], _tickets_held_by(crew), "no_row_for_the_key", ticket)


_CREW_HOLDS = {True: _crew_holds_it, False: _crew_does_not_hold_it}


def refuse_an_unknown_ticket(crew, ticket):
    """Refuse a ticket the crew is not holding, so the collect door waits on nothing it cannot answer
    (declaration refuse_an_unknown_ticket, spec 8.6). NOTHING when the crew holds it, a NoMatch naming
    the tickets table, the ticket looked for, and every ticket the crew does hold when it does not. The
    same unknown ticket misses identically, so it is never retryable."""
    return _CREW_HOLDS[ticket in crew["writes"] or ticket in crew["waiting"]](crew, ticket)


# --- crew_post_receipt (declaration) -----------------------------------------------------------------
def _forget(crew, ticket):
    crew["writes"].pop(ticket, None)
    crew["arrivals"] = list(filter(lambda held: held != ticket, crew["arrivals"]))
    return NOTHING


def _fill_it(crew, ticket, receipt):
    crew["waiting"][ticket].set_result(receipt)
    _forget(crew, ticket)
    return NOTHING


def _already_filled(_crew, ticket, _receipt):
    return refused("double_receipt",
                   f"an outcome has already been posted for ticket {ticket!r}; two drainers ran one "
                   f"write", {})


_WAITER_STILL_EMPTY = {False: _fill_it, True: _already_filled}


def _hand_it_to_the_waiter(crew, ticket, receipt):
    waiter = crew["waiting"][ticket]
    return _WAITER_STILL_EMPTY[waiter.done()](crew, ticket, receipt)


def _nobody_is_waiting(crew, ticket, receipt):
    log_write({"event": "receipt_nobody_collected", "ticket": ticket, "ok": receipt["ok"],
               "touched": receipt["touched"], "attempts": receipt["attempts"]})
    _forget(crew, ticket)
    return NOTHING


_A_CALLER_IS_WAITING = {True: _hand_it_to_the_waiter, False: _nobody_is_waiting}


def crew_post_receipt(crew, ticket, receipt):
    """Hand one write's outcome to whoever is waiting on its ticket (declaration crew_post_receipt). A
    ticket nobody holds has its outcome written to the log, which is not a failure."""
    return _A_CALLER_IS_WAITING[ticket in crew["waiting"]](crew, ticket, receipt)


# --- crew_start, crew_stop (declaration) -------------------------------------------------------------
_HOW_LONG_AN_IDLE_DRAINER_SLEEPS = 1.0


def _draining(db, writer):
    return {"db": db, "writer": writer, "stop": db["crew"]["stop"], "idle": _HOW_LONG_AN_IDLE_DRAINER_SLEEPS}


def _already_running(db, _turn):
    crew = db["crew"]
    return refused("crew_already_running",
                   f"this crew is already running {len(crew['drainers'])} drainers", {})


def _start_one_per_writer(db, turn):
    crew = db["crew"]
    crew["drainers"] = [asyncio.ensure_future(turn(_draining(db, writer))) for writer in db["writers"]]
    crew["size"] = len(crew["drainers"])
    return crew


_IS_ALREADY_RUNNING = {True: _already_running, False: _start_one_per_writer}


async def crew_start(db, turn):
    """Hand one drainer per writer to the runtime, each running the turn it was given, and keep them so
    they can be stopped (declaration crew_start)."""
    return _IS_ALREADY_RUNNING[db["crew"]["drainers"] != []](db, turn)


def _one_did_not_stop(said):
    return refused("drainer_would_not_stop",
                   f"{len(said)} of the crew's drainers did not stop cleanly: "
                   + "; ".join(f"{type(one).__name__}: {one}" for one in said), {})


def _all_stopped(_said):
    return NOTHING


_ANY_RAISED = {True: _one_did_not_stop, False: _all_stopped}


async def crew_stop(crew):
    """Stop every drainer and wait for each to put its connection down (declaration crew_stop)."""
    crew["stop"].set()
    ended = await asyncio.gather(*crew["drainers"], return_exceptions=True)
    crew["drainers"] = []
    said = list(filter(lambda one: isinstance(one, BaseException), ended))
    return _ANY_RAISED[said != []](said)


# --- crew_wait_for_work (declaration) ----------------------------------------------------------------
async def _there_is_work_already(_draining):
    return NOTHING


async def _sleep_until_something_happens(draining):
    crew = draining["db"]["crew"]
    crew["arrived"].clear()
    waiting = [asyncio.ensure_future(crew["arrived"].wait()), asyncio.ensure_future(draining["stop"].wait())]
    try:
        await asyncio.wait(waiting, timeout=draining["idle"], return_when=asyncio.FIRST_COMPLETED)
    finally:
        for sleeper in waiting:
            sleeper.cancel()
    return NOTHING


_THERE_IS_WORK = {True: _there_is_work_already, False: _sleep_until_something_happens}


async def crew_wait_for_work(draining):
    """Sleep until a write arrives, the crew stops, or the idle limit runs out (declaration
    crew_wait_for_work). Work already there means no sleep at all."""
    return await _THERE_IS_WORK[draining["db"]["crew"]["arrivals"] != []](draining)


# --- lifecycle_install_handler, lifecycle_register (declaration) -------------------------------------
_OURS = "_honest_persist_handler"
_WHAT_THE_PLATFORM_SENDS = (signal.SIGTERM, signal.SIGINT)


def _run_displaced(previous, number, frame):
    previous(number, frame)
    return True


def _nothing_displaced(_previous, _number, _frame):
    return False


_RUN_THE_DISPLACED = {True: _run_displaced, False: _nothing_displaced}


def _the_door(_number, _frame):
    from honest_persist.doors import lifecycle_stop

    lifecycle_stop()


def _a_handler_that_chains(displaced):
    def handler(number, frame):
        _the_door(number, frame)
        _RUN_THE_DISPLACED[callable(displaced)](displaced, number, frame)

    setattr(handler, _OURS, True)
    return handler


def _leave_it_alone(_number):
    return False


def _put_ours_in_front(number):
    signal.signal(number, _a_handler_that_chains(signal.getsignal(number)))
    return True


_ALREADY_THERE = {True: _leave_it_alone, False: _put_ours_in_front}


def lifecycle_install_handler():
    """Install the signal handler, chaining to whatever was already there (declaration
    lifecycle_install_handler). Twice changes nothing: a handler this library already put there is left
    where it is."""
    try:
        for number in _WHAT_THE_PLATFORM_SENDS:
            _ALREADY_THERE[getattr(signal.getsignal(number), _OURS, False)](number)
    except (ValueError, OSError) as said:
        return refused("handler_refused",
                       f"the signal handler did not go in, so nothing will replicate at exit: {said}", {})
    return NOTHING


_REGISTERED = []


def _put_on_the_list(db):
    _REGISTERED.append(db)
    return NOTHING


def _leave_off_the_list(_db):
    return NOTHING


_WHAT_TO_DO_WITH_IT = {"replicate_then_exit": _put_on_the_list, "exit_immediately": _leave_off_the_list}


def _no_word_for_shutdown(db):
    return refused("no_such_shutdown",
                   f"this handle asks for {db['shutdown']!r} at shutdown, and there is no such shutdown",
                   {"arrived": db["shutdown"]})


def lifecycle_register(db):
    """Add a replicating database to the list shutdown works through (declaration lifecycle_register);
    its answer is kept in the registered store, which lifecycle_shut_down reads at exit."""
    asked_for = db["shutdown"]
    return _read_or(_WHAT_TO_DO_WITH_IT, asked_for, lambda: _no_word_for_shutdown)(db)


def read_registered():
    """The databases that asked to replicate at exit (the registered store), copied so a database opening
    mid-shutdown does not change the list underneath the loop reading it."""
    return list(_REGISTERED)

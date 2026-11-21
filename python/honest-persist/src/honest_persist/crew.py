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


_refuse_empty_write = lambda _crew, statement: refused(
    "empty_write",
    f"you handed over a write whose text is {statement['text']!r}; there is nothing to run", {})


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
# Every ticket the crew is holding: the keys of the writes that arrived and the waiters parked on them.
# Only dict keys are read, never a Waiter handle, which is why this is pure.
_tickets_held_by = lambda crew: sorted(set(crew["writes"]) | set(crew["waiting"]))

_crew_holds_it = lambda _crew, _ticket: NOTHING

_crew_does_not_hold_it = lambda crew, ticket: no_match(
    "tickets", [ticket], _tickets_held_by(crew), "no_row_for_the_key", ticket)


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


_already_filled = lambda _crew, ticket, _receipt: refused(
    "double_receipt",
    f"an outcome has already been posted for ticket {ticket!r}; two drainers ran one write", {})


_WAITER_STILL_EMPTY = {False: _fill_it, True: _already_filled}

_hand_it_to_the_waiter = lambda crew, ticket, receipt: _WAITER_STILL_EMPTY[
    crew["waiting"][ticket].done()](crew, ticket, receipt)


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

_draining = lambda db, writer: {
    "db": db, "writer": writer, "stop": db["crew"]["stop"], "idle": _HOW_LONG_AN_IDLE_DRAINER_SLEEPS}

_already_running = lambda db, _turn: refused(
    "crew_already_running",
    f"this crew is already running {len(db['crew']['drainers'])} drainers", {})


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


_one_did_not_stop = lambda said: refused(
    "drainer_would_not_stop",
    f"{len(said)} of the crew's drainers did not stop cleanly: "
    + "; ".join(f"{type(one).__name__}: {one}" for one in said), {})

_all_stopped = lambda _said: NOTHING


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


_nothing_displaced = lambda _previous, _number, _frame: False


_RUN_THE_DISPLACED = {True: _run_displaced, False: _nothing_displaced}


def _run_the_shutdown_now(_loop, coro):
    """No loop is running, so run the shutdown coroutine to completion right here, where this handler is the
    only thing on the stack."""
    asyncio.run(coro)
    return NOTHING


def _hand_the_shutdown_to_the_loop(loop, coro):
    """A loop is running, so hand the already-built shutdown coroutine to it as a task and return at once. The
    task is created on the loop's own thread inside the scheduled callback, so the coroutine is always awaited
    and never dropped, and call_soon_threadsafe returns immediately so the chained handler can run the
    displaced handler afterward."""
    loop.call_soon_threadsafe(loop.create_task, coro)
    return NOTHING


_A_LOOP_IS_RUNNING = {False: _run_the_shutdown_now, True: _hand_the_shutdown_to_the_loop}


def _the_door(_number, _frame):
    """Drive the async shutdown from the sync signal handler (declaration lifecycle_stop, reached through the
    signal entry). lifecycle_stop is a coroutine, so a sync handler cannot just call and forget it: it builds
    the coroutine and drives it — onto the running loop when a server loop is on the stack, else to completion
    in a fresh loop. Either way this returns so the chained handler runs the displaced handler afterward."""
    from honest_persist.doors import lifecycle_stop

    def _detect_loop():
        """The asyncio loop already on the stack, or NOTHING when none is running. A signal can land with the
        server's loop running (the main thread was inside it, so this returns that loop) or with no loop at all
        (a plain process, so asyncio.get_running_loop() raises RuntimeError). That raise is resolved here into a
        value, so the caller dispatches on data — a loop or NOTHING — and never on a thrown exception."""
        try:  # honest: ignore HC-P002: asking the runtime whether a loop is running is the asyncio boundary; the no-loop RuntimeError resolves into NOTHING, a first-class tested outcome, not a swallowed error
            return asyncio.get_running_loop()
        except RuntimeError:
            return NOTHING

    coro = lifecycle_stop()
    loop = _detect_loop()
    return _A_LOOP_IS_RUNNING[loop is not NOTHING](loop, coro)


def _a_handler_that_chains(displaced):
    def handler(number, frame):
        _the_door(number, frame)
        _RUN_THE_DISPLACED[callable(displaced)](displaced, number, frame)

    setattr(handler, _OURS, True)
    return handler


_leave_it_alone = lambda _number: False


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


_leave_off_the_list = lambda _db: NOTHING


_WHAT_TO_DO_WITH_IT = {"replicate_then_exit": _put_on_the_list, "exit_immediately": _leave_off_the_list}

_no_word_for_shutdown = lambda db: refused(
    "no_such_shutdown",
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

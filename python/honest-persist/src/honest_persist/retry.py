"""The two write-decision leaves of the declaration: worth_retrying and budget_spent.

Both are pure reads of a number or a word, with no state of their own: the attempts a caller has made are
handed in, never counted here (the declaration's Attempt note — a rule that cannot see the number of tries
would have to keep a tally, and a tally is state).
"""


def worth_retrying(fault):
    """Answer whether a failure is worth another attempt, asked of its category (declaration
    `worth_retrying`, spec 3.1). Only a conflict is worth another attempt — two writers wrote one row, so
    trying again may win it. A refused request, a spent budget and a killed process never improve on a
    retry, so every other category answers no."""
    return fault["category"] == "conflict"


def budget_spent(attempts, budget):
    """Answer whether the retry budget is gone: the attempts made have reached the budget allowed
    (declaration `budget_spent`; the Attempt note — budget_spent means retried as many times as
    allowed). Gone when attempts >= budget, so a budget of three is spent at the third attempt."""
    return attempts >= budget


from honest_persist._util import _pick, _read_or  # noqa: E402
from honest_persist.types import is_fault, refused  # noqa: E402

# --- the pure backoff and the driven-retry generator (declaration, spec 7.7) ------------------------
_FIRST_WAIT_SECONDS = 0.05


def next_wait(attempt):
    """The backoff delay in seconds before one retry attempt, worked out from the attempt number alone
    (declaration next_wait): zero before the first attempt and rising with each one, a deterministic
    progression a test reads without a clock. Holds no clock and no ticket, which is why it is pure."""
    return _pick(attempt <= 1, lambda: 0.0, lambda: _FIRST_WAIT_SECONDS * 2.0 ** (attempt - 2))


def _landed(_policy, _outcome, attempt):
    """A success — an int outcome — lands at once, nothing to retry."""
    return {"attempt": attempt, "delay": 0.0, "disposition": "landed"}


def _give_up_logical(_policy, _outcome, attempt):
    """A logical fault the caller owns fails identically however often it runs, so it is never retried."""
    return {"attempt": attempt, "delay": 0.0, "disposition": "give_up_logical"}


def _give_up_contention(_policy, _outcome, attempt):
    """A conflict kept losing the race and the bound is reached; the failure is typed as contention."""
    return {"attempt": attempt, "delay": 0.0, "disposition": "give_up_contention"}


def _run_again(_policy, _outcome, attempt):
    """A conflict with budget to spare asks for another run at the next attempt, after its backoff."""
    nxt = attempt + 1
    return {"attempt": nxt, "delay": next_wait(nxt), "disposition": "run"}


def _on_conflict(policy, outcome, attempt):
    """A conflict: run again unless the bound is reached, in which case give up on contention."""
    return _ON_BUDGET[budget_spent(attempt, policy["bound"])](policy, outcome, attempt)


_ON_BUDGET = {True: _give_up_contention, False: _run_again}
_ON_RETRYABLE = {False: _give_up_logical, True: _on_conflict}


def _on_fault(policy, outcome, attempt):
    """A driver Fault: a conflict is worth another attempt, a logical fault is not."""
    return _ON_RETRYABLE[worth_retrying(outcome)](policy, outcome, attempt)


_ON_OUTCOME = {False: _landed, True: _on_fault}


def retry_schedule(policy, outcome, attempt):
    """The pure generator that owns the conflict-retry schedule for one write (declaration
    retry_schedule, spec 7.7). It is driven: lifecycle_catch_up performs the real write against
    crew_run_write, hands the outcome and the attempt number back here, and this yields the next
    RetryStep. The attempts and the backoff live here; the real writes live in the orchestrator; neither
    holds the other. A success yields `landed`; a conflict with budget to spare yields `run` at the next
    attempt with next_wait's backoff; a conflict at the bound yields `give_up_contention`; a logical
    fault yields `give_up_logical` at once."""
    return _ON_OUTCOME[is_fault(outcome)](policy, outcome, attempt)


# --- the crew's pure readers and settlers (declaration, lifecycle_catch_up path) --------------------
_RAISED_TO_THE_CALLER = {"refused": True, "cut_short": True, "conflict": False, "budget_spent": False}


def refusal_reaches_caller(fault):
    """Decide whether a fault is raised to its caller or comes back as a receipt (declaration
    refusal_reaches_caller), asked of its category: the two the engine did not stay busy for are raised,
    the two that are contention come back as a receipt a caller may deposit again."""
    return _RAISED_TO_THE_CALLER[fault["category"]]


def receipt_for(ticket, touched, failure, attempts):
    """Build the receipt a caller reads for its write (declaration receipt_for), carrying how many rows
    it touched and how many attempts it took; `ok` is true when no failure ended it."""
    return {"id": ticket, "ok": failure is None, "touched": touched, "attempts": attempts,
            "failure": failure}


def replicates(db):
    """Whether this database replicates, derived from whether it holds a channel (declaration
    replicates). It reads one field: a second field could disagree with the first."""
    return db["channel"] is not None


def writer_waiting(crew):
    """Whether a writer is waiting for the connection (declaration writer_waiting): a write still in the
    crew's arrival order is a write nobody has started."""
    return bool(crew["arrivals"])


def next_in_order(crew):
    """Whose write is next, in arrival order (declaration next_in_order); taking it out is the
    boundary's work, so this answers and never removes. An empty crew answers NOTHING, not a failure."""
    return next(iter(crew["arrivals"]), None)


def progress_line(db, elapsed, done):
    """Build a shutdown log line naming the database and the time elapsed (declaration progress_line).
    Every line has to be true if it is the last one, so it carries the elapsed time, which moves, and
    the database target, which names it."""
    return {
        "level": "info",
        "shutting_down": db["target"],
        "elapsed": elapsed,
        "state": _read_or(_WHETHER_IT_ARRIVED, done, lambda: ""),
        "done": done,
    }


_WHETHER_IT_ARRIVED = {
    True: "the primary has everything",
    False: "the data has not reached the primary yet",
}

_DEFAULT_CREW_SIZE = 1
_DEFAULT_CONNECTIONS = 1


def _nobody_said_size(_asked):
    """The deployment named no crew size, so a default is settled here (declaration crew_size)."""
    return _DEFAULT_CREW_SIZE


def _too_few_drainers(asked):
    """A crew of none takes tickets and runs nothing, so the caller would wait forever."""
    return refused(
        "crew_too_small",
        f"HONEST_PERSIST_CREW_SIZE is {asked}, so no drainer would run; set it to at least 1",
        {"asked": asked},
    )


def _asked_crew_size(asked):
    return asked


_CREW_SIZE = {
    (False, False): _nobody_said_size,
    (False, True): _nobody_said_size,
    (True, False): _too_few_drainers,
    (True, True): _asked_crew_size,
}


def crew_size(asked):
    """Settle how many drainers run, from what the deployment asked for (declaration crew_size); NOTHING
    means the deployment named none and a default is settled here."""
    said = asked is not None
    return _CREW_SIZE[(said, said and asked >= 1)](asked)


def _nobody_said_connections(_asked):
    return _DEFAULT_CONNECTIONS


def _too_few_connections(asked):
    return refused(
        "connections_too_few",
        f"HONEST_PERSIST_CONNECTIONS is {asked}, so no connection is permitted; set it to at least 1",
        {"asked": asked},
    )


def _asked_connections(asked):
    return asked


_CONNECTIONS = {
    (False, False): _nobody_said_connections,
    (False, True): _nobody_said_connections,
    (True, False): _too_few_connections,
    (True, True): _asked_connections,
}


def permitted_connections(asked):
    """Settle how many connections this database opens, from what the deployment asked for (declaration
    permitted_connections); NOTHING means the deployment named none and a default is settled here."""
    said = asked is not None
    return _CONNECTIONS[(said, said and asked >= 1)](asked)


# --- what a scheduler does after one refresh (declaration what_to_do_after_a_refresh) ----------------
_REFRESH_DISPOSITION = {
    True: {"kind": "continue", "delay": None},
    False: {"kind": "stop", "delay": None},
}


def _count_came_back(_written, _attempt, _allowed):
    """A refresh that wrote its rows is always worth running again; the count itself is not read."""
    return True


def _fault_came_back(written, attempt, allowed):
    """Ask the kind whether another go is worth it, then whether one is left."""
    return worth_retrying(written) and not budget_spent(attempt["consecutive_faults"], allowed)


_WHO_READS_THE_OUTCOME = {False: _count_came_back, True: _fault_came_back}


def what_to_do_after_a_refresh(written, attempt, attempts_allowed):
    """Read one refresh's outcome and say whether to run again or stop (declaration
    what_to_do_after_a_refresh); it never answers retry_after, because a refresh already has its cadence
    as the spacing and this rule holds no clock to mint a delay with."""
    return _REFRESH_DISPOSITION[_WHO_READS_THE_OUTCOME[is_fault(written)](written, attempt, attempts_allowed)]

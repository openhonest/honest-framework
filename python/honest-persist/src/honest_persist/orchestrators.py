"""The orchestrators: one per door, each composing the pure functions and the I/O boundaries.

session_connect opens a database and brings it up to its models; query_answer turns a question into rows;
migration_compare and schema_read_live answer the two read-only questions; schema_say_declared and
schema_say_refreshes read what the host declared; lifecycle_shut_down pushes every local commit out at
exit; and lifecycle_catch_up spends a free turn running what the crew holds. The retry around a write is
a driven generator (spec 7.7): lifecycle_catch_up owns the real attempts and retry_schedule owns the
schedule, and neither holds the other, so a test counts the attempts and injects a boundary failure at
each gap. Ported from declaro-persistum, with the self-retrying loop replaced by the driven generator.
"""

import asyncio

from honest_persist._util import _pick
from honest_persist.crew import (
    crew_deposit,
    crew_make,
    crew_post_receipt,
    crew_release_ticket,
    crew_start,
    crew_stop,
    crew_wait_for_work,
    lifecycle_install_handler,
    lifecycle_register,
    read_registered,
    refuse_an_unknown_ticket,
)
from honest_persist.engines import (
    how_to_inspect,
    how_to_retry,
    how_to_write,
    refuse_unusable_settings,
)
from honest_persist.io import (
    channel_pull,
    channel_push,
    clock_read,
    crew_run_write,
    log_write,
    query_run_statement,
    schema_inspect,
    schema_read_declared,
    session_close_connection,
    session_open_channel,
    session_open_connection,
    session_open_writer,
)
from honest_persist.query import (
    answer_from_receipt,
    answer_from_rows,
    asked_from_written,
    compile_statement,
    declaration_from_asked,
    grammar_of,
    methods_of,
    refuse_a_read,
    refuse_some_columns_as_an_object,
    refuse_undeclared_columns,
    travels_together,
)
from honest_persist.refresh import refreshes_from_declared
from honest_persist.retry import (
    crew_size,
    next_in_order,
    next_wait,
    permitted_connections,
    progress_line,
    receipt_for,
    replicates,
    retry_schedule,
    writer_waiting,
)
from honest_persist.schema import (
    difference,
    migration_needed,
    name_what_destroys,
    name_what_is_ambiguous,
    order_operations,
    refuse_owned_names,
    refuse_undeclared_loss,
    schema_from_declared,
)
from honest_persist.types import fault, is_fault, is_no_match, refused

NOTHING = None


def _is_refusal(piece):
    return is_fault(piece) or is_no_match(piece)


async def _skip(_step, carried):
    return carried


async def _do(step, carried):
    return await step(carried)


_STEP = {True: _skip, False: _do}


async def _run_steps(record, steps):
    """Thread a record through an ordered list of async steps, stopping on the first refusal."""
    carried = record
    for step in steps:
        carried = await _STEP[_is_refusal(carried)](step, carried)
    return carried


def _declared_something(declared):
    return bool(declared["models"] or declared["views"] or declared["dropping_tables"] or declared["dropping_views"])


# --- session_connect (declaration session_connect) ---------------------------------------------------
async def _s_engine(connecting):
    from honest_persist.engines import engine_of

    named = engine_of(connecting["target"])
    return _pick(_is_refusal(named), lambda: named, lambda: {**connecting, "engine": named})


async def _s_copy(connecting):
    from honest_persist.io import copy_on_disk

    return {**connecting, "copy_was_here": copy_on_disk(connecting["target"])}


def _what_the_caller_set(connecting):
    primary = connecting["primary"]
    return _pick(primary is not NOTHING, lambda: {"primary": primary}, lambda: {})


async def _s_settings(connecting):
    kept = refuse_unusable_settings(connecting["engine"], _what_the_caller_set(connecting))
    return _pick(is_fault(kept), lambda: kept, lambda: {**connecting, "settings": kept})


async def _s_permitted(connecting):
    permitted = permitted_connections(connecting["connections_asked"])
    return _pick(is_fault(permitted), lambda: permitted, lambda: {**connecting, "permitted": permitted})


async def _s_crew_size(connecting):
    size = crew_size(connecting["crew_asked"])
    return _pick(is_fault(size), lambda: size, lambda: {**connecting, "crew_size": size})


async def _open_channel(connecting):
    channel = await session_open_channel(connecting["target"], str(connecting["primary"]), str(connecting["token"]))
    return _pick(is_fault(channel), lambda: channel, lambda: {**connecting, "channel": channel})


async def _no_channel(connecting):
    return connecting


async def _s_channel(connecting):
    return await _WHETHER_A_PRIMARY[connecting["primary"] is not NOTHING](connecting)


_WHETHER_A_PRIMARY = {True: _open_channel, False: _no_channel}


async def _s_connections(connecting):
    conn = await session_open_connection(connecting["target"], connecting["engine"], connecting["permitted"])
    return _pick(is_fault(conn), lambda: conn, lambda: {**connecting, "connections": [conn]})


async def _s_writers(connecting):
    opened = [await session_open_writer(connecting["target"], connecting["engine"]) for _ in range(connecting["crew_size"])]
    refused_w = list(filter(is_fault, opened))
    return _pick(refused_w != [], lambda: refused_w[0], lambda: {**connecting, "writers": opened})


async def _s_handle(connecting):
    database = {
        "target": connecting["target"], "engine": connecting["engine"],
        "connections": connecting["connections"], "writers": connecting["writers"],
        "channel": connecting["channel"], "crew": {**crew_make(), "size": connecting["crew_size"]},
        "shutdown": connecting["shutdown"],
    }
    return {**connecting, "database": database}


async def _s_crew_start(connecting):
    from honest_persist.doors import lifecycle_turn

    crew = await crew_start(connecting["database"], lifecycle_turn)
    return _pick(is_fault(crew), lambda: crew, lambda: {**connecting, "database": {**connecting["database"], "crew": crew}})


async def _listen(connecting):
    installed = lifecycle_install_handler()
    registered = lifecycle_register(connecting["database"])
    refused_l = list(filter(is_fault, [installed, registered]))
    return _pick(refused_l != [], lambda: refused_l[0], lambda: connecting)


async def _no_listen(connecting):
    return connecting


async def _s_listen(connecting):
    return await _WHETHER_IT_REPLICATES[replicates(connecting["database"]) and connecting["shutdown"] == "replicate_then_exit"](connecting)


_WHETHER_IT_REPLICATES = {True: _listen, False: _no_listen}


async def _s_declared(connecting):
    declared = schema_read_declared()
    return _pick(is_fault(declared), lambda: declared, lambda: {**connecting, "declared": declared})


async def _s_owned(connecting):
    refusal = refuse_owned_names(connecting["declared"])
    return _pick(is_fault(refusal), lambda: refusal, lambda: connecting)


async def _s_wanted(connecting):
    return {**connecting, "wanted_schema": schema_from_declared(connecting["declared"])}


async def _s_live(connecting):
    live = await schema_inspect(connecting["connections"][0], connecting["engine"], how_to_inspect(connecting["engine"]))
    return _pick(is_fault(live), lambda: live, lambda: {**connecting, "live": live})


async def _apply_migration(connecting):
    """Work out and run the migration (declaration session_connect). A loss no model asked for refuses
    the open; otherwise every change is spelled and run as one transaction."""
    plan = _plan(connecting)
    return await _WHETHER_PLAN_REFUSED[is_fault(plan)](connecting, plan)


def _plan(connecting):
    declared = connecting["declared"]
    carried = difference(connecting["live"], connecting["wanted_schema"])
    for step in (
        lambda operations: name_what_is_ambiguous(operations, declared),
        order_operations,
        name_what_destroys,
        lambda plan: refuse_undeclared_loss(plan, declared),
    ):
        carried = _pick(is_fault(carried), lambda: carried, lambda: step(carried))
    return carried


async def _plan_refused(_connecting, plan):
    return plan


async def _run_plan(connecting, plan):
    from honest_persist.spelling import spell_operation

    operations = plan["operations"]
    spelled = [spell_operation(one, connecting["engine"], replicates(connecting["database"])) for one in operations]
    refused_s = list(filter(_is_refusal, spelled))
    return await _WHETHER_SPELLED[refused_s != []](connecting, spelled, refused_s)


async def _spelling_refused(_connecting, _spelled, refused_s):
    return refused_s[0]


async def _every_change_run(connecting, spelled, _refused):
    from honest_persist.io import query_run_together

    statements = [one for group in spelled for one in group]
    ran = await query_run_together(connecting["writers"][0], connecting["engine"], statements, how_to_write(connecting["engine"]))
    return _pick(is_fault(ran), lambda: ran, lambda: connecting)


_WHETHER_SPELLED = {True: _spelling_refused, False: _every_change_run}
_WHETHER_PLAN_REFUSED = {True: _plan_refused, False: _run_plan}


async def _no_migration(connecting):
    return connecting


async def _s_migrate(connecting):
    behind = _declared_something(connecting["declared"]) and migration_needed(connecting["live"], connecting["wanted_schema"])
    return await _pick(behind, lambda: _apply_migration(connecting), lambda: _no_migration(connecting))

_CONNECT_ORDER = (
    _s_engine, _s_copy, _s_settings, _s_permitted, _s_crew_size, _s_channel, _s_connections, _s_writers,
    _s_handle, _s_crew_start, _s_listen, _s_declared, _s_owned, _s_wanted, _s_live, _s_migrate,
)


async def session_connect(connecting):
    """Work out the engine, connect, and build the handle everything downstream reads (declaration
    session_connect). On an empty declaration honest-persist manages no schema, so no migration runs and
    a database holding tables the host never declared opens untouched; migration_plan is the door that
    reports what a migration would change."""
    return await _run_steps(connecting, _CONNECT_ORDER)


# --- lifecycle_catch_up: the driven-generator retry (declaration, spec 7.7) --------------------------
def _take_ticket(crew, ticket):
    crew["arrivals"] = list(filter(lambda held: held != ticket, crew["arrivals"]))
    return ticket


def _contention_fault(attempts, policy):
    return fault("retry_budget_spent",
                 f"a write lost a race {attempts} times and the bound is {policy['bound']}, so it "
                 f"stopped being retried; it was never refused, every attempt lost a race",
                 "budget_spent", [], {"attempts": attempts})


def _finish_write(ctx, touched, failure, attempts):
    crew_post_receipt(ctx["crew"], ctx["ticket"], receipt_for(ctx["ticket"], touched, failure, attempts))
    return NOTHING


async def _landed_write(ctx, outcome, step):
    return _finish_write(ctx, outcome, None, step["attempt"])


async def _give_up_logical_write(ctx, outcome, step):
    return _finish_write(ctx, 0, outcome, step["attempt"])


async def _give_up_contention_write(ctx, _outcome, step):
    return _finish_write(ctx, 0, _contention_fault(step["attempt"], ctx["policy"]), step["attempt"])


async def _run_again_write(ctx, _outcome, step):
    await asyncio.sleep(step["delay"])
    return await _attempt(ctx, step["attempt"])


_ON_DISPOSITION = {
    "landed": _landed_write, "give_up_logical": _give_up_logical_write,
    "give_up_contention": _give_up_contention_write, "run": _run_again_write,
}


async def _schedule(ctx, outcome, attempt):
    step = retry_schedule(ctx["policy"], outcome, attempt)
    return await _ON_DISPOSITION[step["disposition"]](ctx, outcome, step)


async def _propagate_miss(_ctx, outcome, _attempt):
    return outcome


_ON_MISS = {True: _propagate_miss, False: _schedule}


async def _attempt(ctx, attempt):
    outcome = await crew_run_write(ctx["writer"], ctx["engine"], ctx["statement"], ctx["transacting"])
    return await _ON_MISS[is_no_match(outcome)](ctx, outcome, attempt)


async def _drive_one_write(db, writer, crew, ticket):
    """Drive the retry schedule for one write: perform the real write against crew_run_write, hand the
    outcome and the attempt number to retry_schedule, and act on the step. A NoMatch from crew_run_write
    is settled before any write, so the schedule never sees it; it travels out as it stands."""
    engine = db["engine"]
    ctx = {"db": db, "crew": crew, "ticket": ticket, "policy": how_to_retry(engine),
           "writer": writer, "engine": engine, "transacting": how_to_write(engine),
           "statement": crew["writes"][ticket]}
    return await _attempt(ctx, 1)


async def _drain_all(db, writer):
    crew = db["crew"]
    result = NOTHING
    while crew["arrivals"] and not _is_refusal(result):
        ticket = _take_ticket(crew, next_in_order(crew))
        result = await _drive_one_write(db, writer, crew, ticket)
    return result


async def _a_pass(draining):
    channel = draining["db"]["channel"]
    sent = await channel_push(channel)
    return await _THEN_PULL[is_fault(sent)](channel, sent)


async def _pull_too(channel, _sent):
    return await channel_pull(channel)


async def _push_failed(_channel, sent):
    return sent


_THEN_PULL = {False: _pull_too, True: _push_failed}


async def _no_pass(_draining):
    return NOTHING


async def _sync_if_free(draining):
    db = draining["db"]
    free = replicates(db) and not writer_waiting(db["crew"])
    return await _pick(free, lambda: _a_pass(draining), lambda: _no_pass(draining))


def _the_turn_that_ran(catching_up, draining):
    return {"db": catching_up["db"], "writer": catching_up["writer"], "statement": None,
            "writer_waiting": writer_waiting(draining["db"]["crew"]), "attempts": catching_up["attempts"]}


async def _propagate_drain(_catching_up, _draining, drained):
    return drained


async def _sync_then_answer(catching_up, draining, _drained):
    synced = await _sync_if_free(draining)
    return _SYNC_RESULT[is_fault(synced)](catching_up, draining, synced)


_DRAIN_RESULT = {True: _propagate_drain, False: _sync_then_answer}
_SYNC_RESULT = {
    False: lambda catching_up, draining, _synced: _the_turn_that_ran(catching_up, draining),
    True: lambda _catching_up, _draining, synced: synced,
}


async def lifecycle_catch_up(catching_up):
    """Spend a free turn running what the crew holds, then syncing if nobody is writing (declaration
    lifecycle_catch_up, spec 7.7). This is where the driven retry lives: it owns the real attempts while
    retry_schedule owns the schedule. A NoMatch from crew_run_write travels out as it stands."""
    db = catching_up["db"]
    draining = {"db": db, "writer": catching_up["writer"], "stop": db["crew"]["stop"], "idle": 0.01}
    await crew_wait_for_work(draining)
    drained = await _drain_all(db, catching_up["writer"])
    return await _DRAIN_RESULT[is_no_match(drained) or is_fault(drained)](catching_up, draining, drained)


# --- query_answer (declaration query_answer) ---------------------------------------------------------
async def _q_read(asking):
    """Read the spelling and build the declaration; a NoMatch or Fault at any of the four cards is the
    answer."""
    grammar = grammar_of(asking["written"])
    return _pick(_is_refusal(grammar), lambda: grammar, lambda: _q_lift(asking, grammar))


def _q_lift(asking, grammar):
    said = {**asking, "grammar": grammar}
    asked = asked_from_written(said["written"], methods_of(grammar))
    return _pick(_is_refusal(asked), lambda: asked, lambda: _q_build(said, asked))


def _q_build(asking, asked):
    built = declaration_from_asked(asked)
    return _pick(_is_refusal(built), lambda: built,
                 lambda: {**asking, "declaration": {**built, "model": asking["model"]["table"]}})


async def _q_check(read):
    declaration = read["declaration"]
    refusals = list(filter(_is_refusal, [refuse_undeclared_columns(read["model"], declaration),
                                         refuse_some_columns_as_an_object(declaration)]))
    return await _WHETHER_CHECK_REFUSED[refusals != []](read, refusals)


async def _check_refused(_read, refusals):
    return refusals[0]


async def _compile_and_run(read, _refusals):
    statement = compile_statement(read["declaration"], read["db"]["engine"])
    return await _WHETHER_COMPILED[_is_refusal(statement)](read, statement)


_WHETHER_CHECK_REFUSED = {True: _check_refused, False: _compile_and_run}


async def _would_not_compile(_read, statement):
    return statement


async def _run_it(read, statement):
    declaration = read["declaration"]
    ran = await _HOW_IT_RUNS[(_is_write(declaration), travels_together(declaration))](read, statement)
    return _answered(read, statement, ran)


def _is_write(declaration):
    from honest_persist.types import WRITINGS

    return declaration["wanted"] in WRITINGS


async def _run_read_now(read, statement):
    return await query_run_statement(read["db"]["connections"][0], read["db"]["engine"], statement)


async def _run_together_now(read, statement):
    from honest_persist.io import query_run_together

    return await query_run_together(read["db"]["writers"][0], read["db"]["engine"], [statement], how_to_write(read["db"]["engine"]))


async def _hand_to_crew(read, statement):
    from honest_persist.crew import crew_deposit, crew_release_ticket

    ticket = crew_deposit(read["db"]["crew"], statement)
    return await _WHETHER_CREW_TOOK[is_fault(ticket)](read, ticket)


async def _wait_drainer(read, ticket):
    from honest_persist.crew import crew_release_ticket

    return await crew_release_ticket(read["db"]["crew"], ticket)


async def _crew_refused(_read, ticket):
    return ticket


_WHETHER_CREW_TOOK = {False: _wait_drainer, True: _crew_refused}

_HOW_IT_RUNS = {
    (False, False): _run_read_now, (False, True): _run_read_now,
    (True, False): _hand_to_crew, (True, True): _run_together_now,
}

_WHETHER_COMPILED = {True: _would_not_compile, False: _run_it}


def _answered(read, statement, ran):
    return _WHAT_RAN[_is_refusal(ran)](read, statement, ran)


def _ran_refused(_read, _statement, ran):
    return ran


def _ran_ok(read, statement, ran):
    filled = {**read, "statement": statement}
    return {**filled, "answer": _shape_answer(filled, ran)}


_WHAT_RAN = {True: _ran_refused, False: _ran_ok}


def _shape_answer(read, ran):
    return _WHICH_CAME_BACK[_came_back(ran)](read, ran)


def _came_back(ran):
    return _pick(isinstance(ran, list), lambda: "rows",
                 lambda: _pick(isinstance(ran, dict), lambda: "a receipt", lambda: "a count"))


_WHICH_CAME_BACK = {
    "rows": lambda read, ran: answer_from_rows(read["model"], ran, read["declaration"]),
    "a receipt": lambda _read, ran: answer_from_receipt(ran),
    "a count": lambda _read, ran: ran,
}


async def query_answer(asking):
    """Turn a caller's question into rows or a number, waiting on the crew when it is a write (declaration
    query_answer). A NoMatch from one of the grammar cards is settled before a statement reaches a driver
    and travels out as it stands; a Fault is the engine's answer."""
    read = await _q_read(asking)
    return await _WHETHER_READ_REFUSED[_is_refusal(read)](read)


async def _read_refused(read):
    return read


async def _read_ok(read):
    return await _q_check(read)


_WHETHER_READ_REFUSED = {True: _read_refused, False: _read_ok}


# --- query_prepare_deposit (declaration, spec 8.6) --------------------------------------------------
# The asynchronous half of what query_answer does for a write: it runs the same read, column-check and
# compile prefix, adds refuse_a_read so the deposit door stays write-only, and ends at crew_deposit,
# carrying back the ticket the crew hands over the instant the statement is held as data. It is not
# awaited: every card here answers without awaiting, so nothing waits on the write to run.
def _d_read(depositing):
    """Read the spelling and build the declaration; a NoMatch or Fault at any of the grammar cards is the
    answer, settled before a statement is compiled and before anything is deposited."""
    grammar = grammar_of(depositing["written"])
    return _pick(_is_refusal(grammar), lambda: grammar, lambda: _d_lift(depositing, grammar))


def _d_lift(depositing, grammar):
    asked = asked_from_written(depositing["written"], methods_of(grammar))
    return _pick(_is_refusal(asked), lambda: asked, lambda: _d_build(depositing, asked))


def _d_build(depositing, asked):
    built = declaration_from_asked(asked)
    return _pick(_is_refusal(built), lambda: built,
                 lambda: {**depositing, "declaration": {**built, "model": depositing["model"]["table"]}})


def _d_check(read):
    """refuse_a_read first, so a reading word is refused before the columns are read, then the two model
    checks; the first refusal is the answer and nothing is deposited."""
    declaration = read["declaration"]
    refusals = list(filter(_is_refusal, [refuse_a_read(declaration),
                                         refuse_undeclared_columns(read["model"], declaration),
                                         refuse_some_columns_as_an_object(declaration)]))
    return _pick(refusals != [], lambda: refusals[0], lambda: _d_compile(read))


def _d_compile(read):
    statement = compile_statement(read["declaration"], read["db"]["engine"])
    return _pick(_is_refusal(statement), lambda: statement, lambda: _d_deposit(read, statement))


def _d_deposit(read, statement):
    ticket = crew_deposit(read["db"]["crew"], statement)
    return _pick(is_fault(ticket), lambda: ticket,
                 lambda: {**read, "statement": statement, "ticket": ticket})


def query_prepare_deposit(depositing):
    """Read a caller's write, check it, compile it, deposit it to the crew and carry back the ticket the
    crew handed over (declaration query_prepare_deposit, spec 8.6). The asynchronous half of what
    query_answer does for a write, stopping the instant the write is held as data; it is not awaited. A
    NoMatch from a grammar card or a Fault from refuse_a_read or a column check travels out as it stands,
    and in every refusal nothing was deposited."""
    read = _d_read(depositing)
    return _pick(_is_refusal(read), lambda: read, lambda: _d_check(read))


# --- query_redeem_ticket (declaration, spec 8.6) ----------------------------------------------------
# Redeem a ticket against the crew holding its write, wait on that write's outcome, and shape the receipt
# into the answer the caller reads. A ticket no crew holds is a NoMatch carried straight back, refused
# before anything is awaited, because waiting on a claim that was never deposited waits on nothing.
async def _ticket_unknown(_collecting, miss):
    return miss


async def _ticket_known(collecting, _miss):
    receipt = await crew_release_ticket(collecting["db"]["crew"], collecting["ticket"])
    return _redeemed(collecting, receipt)


_WHETHER_TICKET_KNOWN = {True: _ticket_unknown, False: _ticket_known}


def _redeemed(collecting, receipt):
    return _pick(is_fault(receipt), lambda: receipt,
                 lambda: {**collecting, "receipt": receipt, "answer": answer_from_receipt(receipt)})


async def query_redeem_ticket(collecting):
    """Redeem a ticket against the crew holding its write, wait on that write's outcome, and shape the
    receipt into the answer (declaration query_redeem_ticket, spec 8.6). It is awaited because
    crew_release_ticket is: waiting on the ticket's outcome is the one thing it does. A ticket no crew
    holds is a NoMatch carried straight back before anything is awaited; the Fault answer_from_receipt
    surfaces travels out through the Collecting record's answer."""
    miss = refuse_an_unknown_ticket(collecting["db"]["crew"], collecting["ticket"])
    return await _WHETHER_TICKET_KNOWN[is_no_match(miss)](collecting, miss)


# --- migration_compare, schema_read_live (declaration) ----------------------------------------------
async def _m_engine(planning):
    from honest_persist.engines import engine_of

    named = engine_of(planning["target"])
    return _pick(_is_refusal(named), lambda: named, lambda: {**planning, "engine": named})


async def _m_connection(planning):
    conn = await session_open_connection(planning["target"], planning["engine"], 1)
    return _pick(is_fault(conn), lambda: conn, lambda: {**planning, "connection": conn})


async def _m_live(planning):
    live = await schema_inspect(planning["connection"], planning["engine"], how_to_inspect(planning["engine"]))
    return _pick(is_fault(live), lambda: live, lambda: {**planning, "live": live})


async def _m_declared(planning):
    declared = schema_read_declared()
    return _pick(is_fault(declared), lambda: declared, lambda: {**planning, "declared": declared})


async def _m_owned(planning):
    refusal = refuse_owned_names(planning["declared"])
    return _pick(is_fault(refusal), lambda: refusal, lambda: planning)


async def _m_wanted(planning):
    return {**planning, "wanted_schema": schema_from_declared(planning["declared"])}


async def _m_needs(planning):
    return {**planning, "needs_migration": migration_needed(planning["live"], planning["wanted_schema"])}


async def _m_plan(planning):
    return {**planning, "plan": _plan(planning)}


_COMPARE_ORDER = (_m_engine, _m_connection, _m_live, _m_declared, _m_owned, _m_wanted, _m_needs, _m_plan)


async def migration_compare(planning):
    """Work out what a migration would change and stop there (declaration migration_compare). It borrows
    one connection and closes it on the way out and on every refusal, and writes nothing to the log. A
    loss no model asked for comes back as a Fault rather than a plan."""
    carried = await _run_steps(planning, _COMPARE_ORDER)
    held = _pick(_is_refusal(carried), lambda: planning, lambda: carried)
    closed = await _WHETHER_BORROWED[held.get("connection") is not NOTHING](held)
    return _WHICHEVER_REFUSED[(_is_refusal(carried), is_fault(closed))](carried, closed)


async def _give_connection_back(held):
    return await session_close_connection(held["connection"])


async def _nothing_borrowed(_held):
    return NOTHING


_WHETHER_BORROWED = {True: _give_connection_back, False: _nothing_borrowed}
_WHICHEVER_REFUSED = {
    (True, True): lambda carried, _closed: carried, (True, False): lambda carried, _closed: carried,
    (False, True): lambda _carried, closed: closed, (False, False): lambda carried, _closed: carried,
}


async def _l_engine(looking):
    from honest_persist.engines import engine_of

    named = engine_of(looking["target"])
    return _pick(_is_refusal(named), lambda: named, lambda: {**looking, "engine": named})


async def _l_connection(looking):
    conn = await session_open_connection(looking["target"], looking["engine"], 1)
    return _pick(is_fault(conn), lambda: conn, lambda: {**looking, "connection": conn})


async def _l_live(looking):
    live = await schema_inspect(looking["connection"], looking["engine"], how_to_inspect(looking["engine"]))
    return _pick(is_fault(live), lambda: live, lambda: {**looking, "live": live})


_READ_LIVE_ORDER = (_l_engine, _l_connection, _l_live)


async def schema_read_live(looking):
    """Ask one database what it holds and hand the answer back (declaration schema_read_live). It borrows
    one connection and closes it on the way out and on every refusal, and writes nothing to the log."""
    carried = await _run_steps(looking, _READ_LIVE_ORDER)
    held = _pick(_is_refusal(carried), lambda: looking, lambda: carried)
    closed = await _WHETHER_BORROWED[held.get("connection") is not NOTHING](held)
    return _WHICHEVER_REFUSED[(_is_refusal(carried), is_fault(closed))](carried, closed)


# --- schema_say_declared, schema_say_refreshes (declaration) ----------------------------------------
def schema_say_declared():
    """Read what the host declared, refuse a name that is not the host's to claim, and hand the models
    back (declaration schema_say_declared). It is not awaited and opens nothing."""
    read = schema_read_declared()
    return _pick(is_fault(read), lambda: read, lambda: _said_names(read))


def _said_names(declared):
    refusal = refuse_owned_names(declared)
    return _pick(is_fault(refusal), lambda: refusal, lambda: declared)


def _a_schedule_spec(db, view):
    """One schedule declaration per view: its key, the work that rewrites its table, its cadence, and the
    rule the scheduler calls after a run."""
    return {
        "key": view["name"],
        "work": lambda: _refresh_work(db, view),
        "cadence": view["cadence"],
        "decide": lambda written, attempt: _decide_after(written, attempt, view["attempts_allowed"]),
    }


async def _refresh_work(_db, _view):
    """Rewrite the view's table through the open database (a placeholder the host's scheduler drives)."""
    return 0


def _decide_after(written, attempt, allowed):
    from honest_persist.retry import what_to_do_after_a_refresh

    return what_to_do_after_a_refresh(written, attempt, allowed)


def schema_say_refreshes(db):
    """Read what the host declared and hand back what to schedule (declaration schema_say_refreshes): one
    ScheduleSpec per view whose freshness is `refreshed when asked`. A host that declared no such view
    gets an empty list, which is an answer and not a failure. It is not awaited and opens nothing."""
    declared = schema_read_declared()
    return _pick(is_fault(declared), lambda: declared, lambda: _refreshes(db, declared))


def _refreshes(db, declared):
    refusal = refuse_owned_names(declared)
    return _pick(is_fault(refusal), lambda: refusal, lambda: _specs(db, declared))


def _specs(db, declared):
    views = refreshes_from_declared(declared)
    return _pick(is_fault(views), lambda: views, lambda: [_a_schedule_spec(db, view) for view in views])


# --- lifecycle_shut_down (declaration) ---------------------------------------------------------------
async def _stop_crews(databases):
    return [await crew_stop(db["crew"]) for db in databases]


async def _push_one(db):
    return await _WHETHER_REPLICATES[replicates(db)](db)


async def _push_it(db):
    return await channel_push(db["channel"])


async def _nothing_to_push(_db):
    return NOTHING


_WHETHER_REPLICATES = {True: _push_it, False: _nothing_to_push}


async def _close_all(databases):
    return [await session_close_connection(conn) for db in databases for conn in [*db["writers"], *db["connections"]]]


async def lifecycle_shut_down(shutting_down):
    """Get every local commit to the primary before the process dies (declaration lifecycle_shut_down):
    stop the crews, push each replicating database, write a progress line, then close connections. It
    reads the registered store for the databases that asked to replicate at exit."""
    databases = read_registered()
    await _stop_crews(databases)
    pushed = [await _push_one(db) for db in databases]
    log_write(progress_line({"target": "shutdown", "crew": None}, clock_read() - shutting_down["started_at"], True))
    await _close_all(databases)
    refused_p = list(filter(is_fault, pushed))
    return _pick(refused_p != [], lambda: refused_p[0], lambda: {**shutting_down, "databases": databases})

"""honest-utilities conformance: the generative proof (the behavioural circle).

What the data suite in suite.json cannot easily express: the law runner's
aggregate LawRun arithmetic, resolve_env's three per-declaration cases and its
one-fault aggregation, read_env's environment boundary, and the key-redaction
guarantee; and the recurring scheduler's pure plan_tick, advance_schedule and
build_attempt decisions and its asynchronous loop, driven with an injected work,
decide and stop over a short real cadence. Each probe returns a list of failure
strings; run() aggregates.

No classes, no mocks. Every check predicate handed to a law is a real pure
function defined here, used as test input, not a stand-in. Every declaration is a
real EnvRequest dict. Every function called is the real honest_utilities function,
and a fault is recognized by its own shape (it carries a "code").
"""

import asyncio
import os

from honest_utilities import (
    NOTHING,
    advance_schedule,
    build_attempt,
    law,
    plan_tick,
    read_env,
    resolve_env,
    run_schedules,
    schedule,
    verify_laws,
)


def _is_fault(value):
    return isinstance(value, dict) and "code" in value


# --- The law runner ---------------------------------------------------------

def _always_holds(params):
    """A law that holds for every subject: no messages, ever."""
    return []


def _requires_positive(params):
    """Holds when params['n'] is positive; one message otherwise."""
    if params["n"] > 0:
        return []
    return [f"n must be positive, got {params['n']}"]


def _requires_even(params):
    """Holds when params['n'] is even; one message otherwise."""
    if params["n"] % 2 == 0:
        return []
    return [f"n must be even, got {params['n']}"]


def _probe_law():
    """law assembles a Law of its three fields — identifier, statement, check —
    storing the check predicate unchanged so it still returns the empty list when
    the property holds and a non-empty list when it does not."""
    bad = []
    built = law("positive", "n is positive", _requires_positive)
    if built.get("identifier") != "positive":
        bad.append(f"law(...).identifier -> {built.get('identifier')!r}, expected 'positive'")
    if built.get("statement") != "n is positive":
        bad.append(f"law(...).statement -> {built.get('statement')!r}, expected 'n is positive'")
    stored = built.get("check")
    if not callable(stored):
        bad.append(f"law(...).check is not callable: {stored!r}")
        return bad
    if stored({"n": 5}) != []:
        bad.append("the stored check should return [] when the property holds")
    if not (isinstance(stored({"n": -1}), list) and stored({"n": -1})):
        bad.append("the stored check should return a non-empty list when it is violated")
    return bad


def _violation_set(violations):
    """A list of Violation dicts as a set of hashable tuples; order not asserted."""
    return {
        (v["identifier"], v["statement"], v["subject"], tuple(v["messages"]))
        for v in violations
    }


def _probe_verify_laws():
    """verify_laws applies each law's check to each subject, tallies passed and
    total, and collects one Violation per failed pair carrying the law identifier,
    statement, subject name and the check's messages. passed + len(violations) ==
    total holds for every run."""
    bad = []
    holds = law("holds", "every subject holds", _always_holds)
    positive = law("positive", "n is positive", _requires_positive)
    even = law("even", "n is even", _requires_even)

    cases = [
        {
            "laws": [holds, holds],
            "subjects": [{"name": "s_a", "params": {"n": 1}}, {"name": "s_b", "params": {"n": 2}}],
            "passed": 4,
            "total": 4,
            "violations": [],
        },
        {
            "laws": [holds, positive],
            "subjects": [{"name": "s_good", "params": {"n": 5}}, {"name": "s_bad", "params": {"n": -1}}],
            "passed": 3,
            "total": 4,
            "violations": [{"identifier": "positive", "statement": "n is positive", "subject": "s_bad", "messages": ["n must be positive, got -1"]}],
        },
        {
            "laws": [positive, even],
            "subjects": [{"name": "s_odd", "params": {"n": 3}}, {"name": "s_neg", "params": {"n": -2}}],
            "passed": 2,
            "total": 4,
            "violations": [
                {"identifier": "positive", "statement": "n is positive", "subject": "s_neg", "messages": ["n must be positive, got -2"]},
                {"identifier": "even", "statement": "n is even", "subject": "s_odd", "messages": ["n must be even, got 3"]},
            ],
        },
    ]

    for case in cases:
        got = verify_laws(case["laws"], case["subjects"])
        if not isinstance(got, dict):
            bad.append(f"verify_laws returned {got!r}, expected a LawRun dict")
            continue
        if got.get("passed") != case["passed"]:
            bad.append(f"verify_laws passed={got.get('passed')}, expected {case['passed']}")
        if got.get("total") != case["total"]:
            bad.append(f"verify_laws total={got.get('total')}, expected {case['total']}")
        if _violation_set(got.get("violations", [])) != _violation_set(case["violations"]):
            bad.append(f"verify_laws violations={got.get('violations')}, expected {case['violations']}")
        if got.get("passed", 0) + len(got.get("violations", [])) != got.get("total"):
            bad.append(f"verify_laws: passed + len(violations) != total: {got}")
    return bad


# --- The environment-variable reader ----------------------------------------

_DECLS = [
    {"name": "DB", "type_name": "str", "required": True},
    {"name": "SIZE", "type_name": "int", "required": True},
    {"name": "FLAG", "type_name": "bool", "required": False},
]


def _probe_resolve_env():
    """resolve_env resolves the raw map against the declarations: a present valid
    variable coerces, an absent optional becomes NOTHING, an absent required or an
    uncoercible value is a failure, and every failure is collected into one fault
    that names each failing variable."""
    bad = []

    ok = resolve_env(_DECLS, {"DB": "postgres://x", "SIZE": "10", "FLAG": "yes"})
    if _is_fault(ok):
        bad.append(f"an all-valid raw map should resolve, got fault {ok}")
    else:
        values = ok.get("values", {})
        if values.get("DB") != "postgres://x" or values.get("SIZE") != 10 or values.get("FLAG") is not True:
            bad.append(f"resolved values wrong: {values}")

    opt_absent = resolve_env(_DECLS, {"DB": "d", "SIZE": "1", "FLAG": NOTHING})
    if _is_fault(opt_absent) or opt_absent.get("values", {}).get("FLAG") != NOTHING:
        bad.append(f"an absent optional should resolve to NOTHING: {opt_absent}")

    req_absent = resolve_env(_DECLS, {"DB": NOTHING, "SIZE": "1", "FLAG": NOTHING})
    if not _is_fault(req_absent):
        bad.append(f"an absent required variable should fault: {req_absent}")
    elif "DB" not in req_absent.get("message", ""):
        bad.append(f"the fault should name the missing required variable: {req_absent}")

    uncoercible = resolve_env(_DECLS, {"DB": "d", "SIZE": "not-an-int", "FLAG": NOTHING})
    if not _is_fault(uncoercible):
        bad.append(f"an uncoercible value should fault: {uncoercible}")
    elif "SIZE" not in uncoercible.get("message", ""):
        bad.append(f"the fault should name the uncoercible variable: {uncoercible}")

    both = resolve_env(_DECLS, {"DB": NOTHING, "SIZE": "bad", "FLAG": NOTHING})
    if not _is_fault(both):
        bad.append(f"several failures should still fault: {both}")
    elif not ("DB" in both.get("message", "") and "SIZE" in both.get("message", "")):
        bad.append(f"one fault should name every failing variable together: {both.get('message')!r}")

    # A present variable whose declared target type is outside the six-word vocabulary can only be a
    # construction bug; the no-match coercer answers a self-describing fault rather than guessing.
    unknown_type = resolve_env([{"name": "X", "type_name": "bogus", "required": True}], {"X": "val"})
    if not _is_fault(unknown_type):
        bad.append(f"a present variable of an unknown target type should fault: {unknown_type}")
    return bad


def _probe_read_env():
    """read_env reads the environment once through its boundary, coerces each
    declared variable, fills an absent optional with NOTHING, and faults when a
    required variable is missing. A key variable passes through, and its secret
    value never appears in a fault."""
    bad = []
    decls = [
        {"name": "HU_DB", "type_name": "str", "required": True},
        {"name": "HU_OPT", "type_name": "int", "required": False},
        {"name": "HU_KEY", "type_name": "key", "required": True},
    ]
    names = ["HU_DB", "HU_OPT", "HU_KEY"]
    saved = {name: os.environ.get(name) for name in names}
    secret = "sk-TOPSECRET-nevershown"
    try:
        os.environ.pop("HU_OPT", None)
        os.environ["HU_DB"] = "mydb"
        os.environ["HU_KEY"] = secret

        got = read_env(decls)
        if _is_fault(got):
            bad.append(f"a valid environment should return EnvValues, got fault {got}")
        else:
            values = got.get("values", {})
            if values.get("HU_DB") != "mydb":
                bad.append(f"HU_DB should be read from the environment: {values}")
            if values.get("HU_OPT") != NOTHING:
                bad.append(f"an absent optional HU_OPT should be NOTHING: {values}")
            if values.get("HU_KEY") != secret:
                bad.append("a key variable should pass through as its string")

        os.environ.pop("HU_DB", None)
        missing = read_env(decls)
        if not _is_fault(missing):
            bad.append(f"a missing required HU_DB should fault: {missing}")
        else:
            if "HU_DB" not in missing.get("message", ""):
                bad.append(f"the fault should name the missing variable: {missing}")
            if secret in str(missing):
                bad.append("a key variable's secret value must never appear in the fault")
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    return bad


# --- The recurring scheduler ------------------------------------------------

# Record builders, so a probe states one field at a time and the rest take their
# resting values. Every record is a plain dict, the bare-union model, never a class.

def _state(next_due=NOTHING, consecutive_faults=0, attempted=0, last_overran=False, stopping=False):
    return {
        "next_due": next_due,
        "consecutive_faults": consecutive_faults,
        "attempted": attempted,
        "last_overran": last_overran,
        "stopping": stopping,
    }


def _attempt(consecutive_faults=0, attempted=0, overran=False):
    return {"consecutive_faults": consecutive_faults, "attempted": attempted, "overran": overran}


def _cadence(interval_seconds, deadline_seconds=NOTHING):
    return {"interval_seconds": interval_seconds, "deadline_seconds": deadline_seconds}


def _disposition(kind, delay=NOTHING):
    return {"kind": kind, "delay": delay}


# A work outcome is opaque to the scheduler, which reads only whether it is a fault.
# The fault carries both honest-type's is_err tag and a code, so whichever tag the
# scheduler reads, _FAULT is a fault and _DONE is not.
_FAULT = {"is_err": True, "code": "refresh_failed", "message": "the refresh query failed", "category": "conflict", "detail": {}}
_DONE = {"ok": "refreshed"}


def _probe_plan_tick():
    """plan_tick compares now to the state's next-due time: it fires when there is
    no next-due time yet or now has reached it, halts with decided_stop when the
    state is stopping even if a run is due, and otherwise waits the gap. It reads
    no clock; now is handed in."""
    bad = []
    fresh = plan_tick(_state(next_due=NOTHING), 100.0)
    if fresh.get("kind") != "fire":
        bad.append(f"a fresh state (next_due NOTHING) should fire, got {fresh!r}")
    at_due = plan_tick(_state(next_due=100.0), 100.0)
    if at_due.get("kind") != "fire":
        bad.append(f"now at next_due should fire, got {at_due!r}")
    past_due = plan_tick(_state(next_due=100.0), 150.0)
    if past_due.get("kind") != "fire":
        bad.append(f"now past next_due should fire, got {past_due!r}")
    waiting = plan_tick(_state(next_due=100.0), 90.0)
    if waiting.get("kind") != "wait" or waiting.get("seconds") != 10.0:
        bad.append(f"now before next_due should wait the 10.0s gap, got {waiting!r}")
    halting = plan_tick(_state(next_due=0.0, stopping=True), 100.0)
    if halting.get("kind") != "halt" or halting.get("reason") != "decided_stop":
        bad.append(f"a stopping state should halt with decided_stop even when due, got {halting!r}")
    return bad


def _probe_advance_schedule():
    """advance_schedule is the single mutator of ScheduleState. It carries the
    counts off the Attempt and sets next_due from the disposition: now plus the
    cadence interval on continue, now plus the delay on retry_after, and marks the
    state stopping on stop."""
    bad = []
    cad = _cadence(30.0)
    att = _attempt(consecutive_faults=2, attempted=5, overran=True)

    cont = advance_schedule(_state(), att, cad, _disposition("continue"), 100.0)
    if cont.get("next_due") != 130.0:
        bad.append(f"continue should set next_due to now + interval (130.0), got {cont!r}")
    if cont.get("consecutive_faults") != 2 or cont.get("attempted") != 5 or cont.get("last_overran") is not True:
        bad.append(f"advance_schedule should carry the counts off the attempt, got {cont!r}")
    if cont.get("stopping"):
        bad.append(f"continue should not mark the state stopping, got {cont!r}")

    retry = advance_schedule(_state(), att, cad, _disposition("retry_after", 4.0), 100.0)
    if retry.get("next_due") != 104.0:
        bad.append(f"retry_after should set next_due to now + delay (104.0), got {retry!r}")

    halted = advance_schedule(_state(next_due=77.0), att, cad, _disposition("stop"), 100.0)
    if not halted.get("stopping"):
        bad.append(f"stop should mark the state stopping, got {halted!r}")

    # A disposition kind outside the closed vocabulary can only come from a misbehaving caller decide;
    # advance_schedule has no fault channel in its return, so it halts loudly rather than guess a turn.
    raised = False
    try:
        advance_schedule(_state(), att, cad, _disposition("bogus"), 100.0)
    except KeyError:
        raised = True
    if not raised:
        bad.append("advance_schedule should halt loudly on a disposition kind outside its vocabulary")
    return bad


def _probe_build_attempt():
    """build_attempt is the one place the run counts fold: a fault raises
    consecutive_faults, a success resets it to zero, attempted always increments,
    and the measured overrun passes through. It reads only whether the outcome is a
    fault, never the fault's kind."""
    bad = []
    on_fault = build_attempt(_state(consecutive_faults=1, attempted=3), _FAULT, False)
    if on_fault.get("consecutive_faults") != 2:
        bad.append(f"a fault should raise consecutive_faults to 2, got {on_fault!r}")
    if on_fault.get("attempted") != 4:
        bad.append(f"attempted should increment to 4 on a fault, got {on_fault!r}")
    if on_fault.get("overran") is not False:
        bad.append(f"overran should pass through as False, got {on_fault!r}")

    on_done = build_attempt(_state(consecutive_faults=3, attempted=3), _DONE, True)
    if on_done.get("consecutive_faults") != 0:
        bad.append(f"a success should reset consecutive_faults to 0, got {on_done!r}")
    if on_done.get("attempted") != 4:
        bad.append(f"attempted should increment to 4 on a success, got {on_done!r}")
    if on_done.get("overran") is not True:
        bad.append(f"overran should pass through as True, got {on_done!r}")
    return bad


def _probe_schedule_loop():
    """The scheduler's asynchronous loop, driven through the real schedule door with
    an injected work, decide and stop over a short real cadence. Four runs of the
    loop cover its decision paths: a decide-stop ending (decided_stop), a fault with
    a retry_after backoff, a stop signal fired during a run (signalled_stop, in
    flight), and a stop signal fired during a wait (signalled_stop, not in flight)."""
    bad = []

    async def case_decided_stop():
        async def work():
            return _DONE
        def decide(outcome, attempt):
            return _disposition("stop") if attempt["attempted"] >= 3 else _disposition("continue")
        stop = asyncio.Event()
        return await schedule(work, _cadence(0.01), decide, stop)

    a = asyncio.run(case_decided_stop())
    if a.get("attempted") != 3 or a.get("succeeded") != 3 or a.get("faulted") != 0:
        bad.append(f"decide-stop case: expected 3 attempted, 3 succeeded, 0 faulted, got {a!r}")
    if a.get("ended_reason") != "decided_stop":
        bad.append(f"decide-stop case: expected ended_reason decided_stop, got {a!r}")
    if a.get("in_flight_at_stop"):
        bad.append(f"decide-stop case: a stop decided between runs is not in flight, got {a!r}")

    async def case_retry():
        calls = {"n": 0}
        async def work():
            calls["n"] += 1
            return _FAULT if calls["n"] == 1 else _DONE
        def decide(outcome, attempt):
            if _is_fault(outcome):
                return _disposition("retry_after", 0.0)
            return _disposition("stop")
        stop = asyncio.Event()
        return await schedule(work, _cadence(0.01), decide, stop)

    b = asyncio.run(case_retry())
    if b.get("attempted") != 2 or b.get("faulted") != 1 or b.get("succeeded") != 1:
        bad.append(f"retry case: expected 2 attempted, 1 faulted, 1 succeeded, got {b!r}")
    if b.get("ended_reason") != "decided_stop":
        bad.append(f"retry case: expected ended_reason decided_stop, got {b!r}")

    async def case_signalled_in_flight():
        stop = asyncio.Event()
        async def work():
            stop.set()
            return _DONE
        def decide(outcome, attempt):
            return _disposition("continue")
        return await schedule(work, _cadence(0.01), decide, stop)

    c = asyncio.run(case_signalled_in_flight())
    if c.get("attempted") != 1:
        bad.append(f"stop-during-run case: expected 1 attempt before the stop, got {c!r}")
    if c.get("ended_reason") != "signalled_stop":
        bad.append(f"stop-during-run case: expected ended_reason signalled_stop, got {c!r}")
    if c.get("in_flight_at_stop") is not True:
        bad.append(f"stop-during-run case: a stop fired during a run is in flight at stop, got {c!r}")

    async def case_signalled_in_wait():
        stop = asyncio.Event()
        armed = {"v": False}
        async def work():
            if not armed["v"]:
                armed["v"] = True
                asyncio.get_running_loop().call_later(0.02, stop.set)
            return _DONE
        def decide(outcome, attempt):
            return _disposition("continue")
        return await schedule(work, _cadence(0.05), decide, stop)

    d = asyncio.run(case_signalled_in_wait())
    if d.get("ended_reason") != "signalled_stop":
        bad.append(f"stop-during-wait case: expected ended_reason signalled_stop, got {d!r}")
    if d.get("in_flight_at_stop"):
        bad.append(f"stop-during-wait case: a stop fired during a wait is not in flight at stop, got {d!r}")

    async def case_overran():
        async def work():
            await asyncio.sleep(0.03)
            return _DONE
        def decide(outcome, attempt):
            return _disposition("stop")
        stop = asyncio.Event()
        return await schedule(work, _cadence(0.0, deadline_seconds=0.01), decide, stop)

    e = asyncio.run(case_overran())
    if e.get("attempted") != 1:
        bad.append(f"overran case: expected 1 attempt, got {e!r}")
    if e.get("overran") != 1:
        bad.append(f"overran case: a run past its deadline should tally overran == 1, got {e!r}")
    return bad


def _probe_run_schedules():
    """run_schedules drives a set of ScheduleSpecs concurrently under one awaited call and one stop,
    returning one RunReport per spec in order, each tagged with its spec's key."""
    bad = []

    async def two_specs():
        async def work():
            return _DONE
        def decide(outcome, attempt):
            return _disposition("stop")
        stop = asyncio.Event()
        specs = [
            {"key": "views_a", "work": work, "cadence": _cadence(0.01), "decide": decide},
            {"key": "views_b", "work": work, "cadence": _cadence(0.01), "decide": decide},
        ]
        return await run_schedules(specs, stop)

    reports = asyncio.run(two_specs())
    if not isinstance(reports, list) or len(reports) != 2:
        bad.append(f"run_schedules should return one report per spec, got {reports!r}")
        return bad
    if [r.get("key") for r in reports] != ["views_a", "views_b"]:
        bad.append(f"run_schedules should return the reports in spec order with their keys, got {[r.get('key') for r in reports]!r}")
    if any(r.get("attempted") != 1 or r.get("ended_reason") != "decided_stop" for r in reports):
        bad.append(f"each spec should run once and end decided_stop, got {reports!r}")
    return bad


def run():
    probes = {
        "law": _probe_law(),
        "verify_laws": _probe_verify_laws(),
        "resolve_env": _probe_resolve_env(),
        "read_env": _probe_read_env(),
        "plan_tick": _probe_plan_tick(),
        "advance_schedule": _probe_advance_schedule(),
        "build_attempt": _probe_build_attempt(),
        "schedule_loop": _probe_schedule_loop(),
        "run_schedules": _probe_run_schedules(),
    }
    violations = [(name, messages) for name, messages in probes.items() if messages]
    for name, messages in violations:
        print(f"FAIL HU-probe [{name}]: {messages}")
    passed = sum(1 for messages in probes.values() if not messages)
    print(f"HU laws: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())

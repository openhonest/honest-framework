"""honest-utilities — the capability several modules share and none owns (honest-utilities-architecture.md).

Two capabilities, each entered by import and running from no flow of its own. The law runner (door
`verify_laws`) checks a caller's injected predicate across a bounded space of subjects and reports
failures as Violations, never faults. The environment-variable reader (door `read_env`) coerces named
variables to a caller-declared type, returns NOTHING for an absent optional, and returns one Fault
naming every missing-required or uncoercible variable together.

Fault is honest-type's shape across the seam: built with honest_type.fault, carried as a bare union
`X | Fault` recognized by shape — a record carrying a "code" — never raised and never wrapped in an
ok/err envelope. NOTHING is the explicit absence sentinel, the empty tuple, defined locally so this
foundation-layer module depends on nothing above honest-type.

If-free by construction (P01, P16). Every branch is a bool (or closed word) key into a dict literal
of thunks, read by subscript and invoked — `{True: a, False: b}[cond]()` for a two-row choice, or a
merge-for-default `{key: no_match, **table}[key]` for an open-key read guarded by its no-match row —
so this file carries no `if` statement, no conditional expression, and no comprehension if-clause.
The module declares exactly the functions its .hd names; the glue that once sat between them is
inlined at its call sites.
"""

import asyncio
import os
import re
import time
import uuid
from typing import Any, Callable, TypedDict

from honest_type import fault

# ---------------------------------------------------------------------------
# The absence sentinel. An optional field holds a value or NOTHING.
# ---------------------------------------------------------------------------

NOTHING: Any = ()

# ---------------------------------------------------------------------------
# The closed target-type vocabulary (Appendix B).
# ---------------------------------------------------------------------------

TARGET_TYPES = frozenset({"str", "int", "bool", "float", "UUID", "key"})

# ---------------------------------------------------------------------------
# The data dictionary (Appendix A and B). Plain records; TypedDict, never classes.
# ---------------------------------------------------------------------------


class Law(TypedDict):
    identifier: str
    statement: str
    check: Callable


class Subject(TypedDict):
    name: str
    params: dict


class Violation(TypedDict):
    identifier: str
    statement: str
    subject: str
    messages: list


class LawRun(TypedDict):
    passed: int
    total: int
    violations: list


class EnvRequest(TypedDict):
    name: str
    type_name: str
    required: bool


class EnvValues(TypedDict):
    values: dict


class Fault(TypedDict):
    code: str
    message: str
    category: str
    detail: dict


# ===========================================================================
# Capability 1 — the law runner, an engine (Appendix A).
# ===========================================================================


def verify_laws(laws, subjects):
    """The law-runner door (Appendix A): hands the two lists to run_laws and returns the LawRun."""
    return run_laws(laws, subjects)


def run_laws(laws, subjects):
    """The law-runner orchestrator (Appendix A). Runs each law against each subject at run_check's
    boundary, builds one Violation per failed pair, and assembles the LawRun where passed plus the
    number of violations equals total."""
    pairs = [(one_law, subject) for one_law in laws for subject in subjects]
    checked = [
        (one_law, subject, run_check(one_law["check"], subject["params"]))
        for (one_law, subject) in pairs
    ]
    results = [
        {True: lambda: to_violation(one_law, subject, messages), False: lambda: NOTHING}[len(messages) > 0]()
        for (one_law, subject, messages) in checked
    ]
    violations = list(filter(lambda result: result is not NOTHING, results))
    total = len(pairs)
    return {"passed": total - len(violations), "total": total, "violations": violations}


def run_check(check, params):
    """The law engine's boundary (Appendix A): runs the caller's injected predicate — code this module
    did not write — on one subject's params and returns its messages, empty when the property holds."""
    return check(params)


def to_violation(one_law, subject, messages):
    """The pure half of the law engine (Appendix A): records one failed pair as a Violation."""
    return {
        "identifier": one_law["identifier"],
        "statement": one_law["statement"],
        "subject": subject["name"],
        "messages": messages,
    }


def law(identifier, statement, check):
    """The pure constructor a sibling imports to write its own generative conformance (Appendix A)."""
    return {"identifier": identifier, "statement": statement, "check": check}


# ===========================================================================
# Capability 2 — the environment-variable reader, a reader (Appendix B).
# ===========================================================================


def read_env(declarations):
    """The reader's door (Appendix B): hands the declarations to load_env and returns the EnvValues or
    the one aggregate Fault."""
    return load_env(declarations)


def load_env(declarations):
    """The reader's orchestrator (Appendix B): reads the environment once through read_raw_env, then
    hands the declarations and the raw map to resolve_env and returns its answer."""
    names = [declaration["name"] for declaration in declarations]
    raw = read_raw_env(names)
    return resolve_env(declarations, raw)


def read_raw_env(names):
    """The capability's boundary (Appendix B): the one place the process environment is touched. Maps
    each declared name to its raw string, or to NOTHING when the variable is absent. The open-key read
    of the environment is guarded by its no-match row rather than a silent default."""
    return {
        name: {True: lambda: os.environ[name], False: lambda: NOTHING}[name in os.environ]()
        for name in names
    }


def resolve_env(declarations, raw):
    """Resolve the raw map against the declarations (Appendix B). Three cases per declaration: an absent
    required variable is a failure, an absent optional resolves to NOTHING, a present variable coerces
    through by_target_type. Every failure is collected into one Fault naming every failing variable
    together; a key variable's name may appear but never its value."""
    resolutions = []
    for declaration in declarations:
        name = declaration["name"]
        rawval = raw[name]
        coercer = {
            True: lambda: by_target_type[declaration["type_name"]],
            False: lambda: lambda raw_value: fault(
                "unknown_target_type",
                f"target type matched no coercer; accepted types are {sorted(by_target_type)}",
                "server",
                [],
                {"accepted": sorted(by_target_type)},
            ),
        }[declaration["type_name"] in by_target_type]()
        coerced = {True: lambda: NOTHING, False: lambda: coercer(rawval)}[rawval is NOTHING]()
        resolution = {
            True: lambda: {
                True: lambda: {"outcome": "fail", "name": name, "reason": "missing required variable"},
                False: lambda: {"outcome": "value", "name": name, "value": NOTHING},
            }[declaration["required"]](),
            False: lambda: {
                True: lambda: {"outcome": "fail", "name": name, "reason": "value will not coerce"},
                False: lambda: {"outcome": "value", "name": name, "value": coerced},
            }[isinstance(coerced, dict) and "code" in coerced](),  # honest: ignore HC-P005: bare-union recognizer for the scalar|Fault seam — isinstance is the arm discriminant, guarding "code" from raising on a scalar coerced value
        }[rawval is NOTHING]()
        resolutions.append(resolution)
    failures = list(filter(lambda resolution: resolution["outcome"] == "fail", resolutions))
    names = [failure["name"] for failure in failures]
    detail = [{"name": failure["name"], "reason": failure["reason"]} for failure in failures]
    return {
        True: lambda: fault(
            "env_unresolved",
            "environment configuration failed for: " + ", ".join(names),
            "server",
            [],
            {"variables": detail},
        ),
        False: lambda: {"values": {resolution["name"]: resolution["value"] for resolution in resolutions}},
    }[len(failures) > 0]()


# ---------------------------------------------------------------------------
# The six coercers (Appendix B), one per by_target_type row. Each returns the
# coerced value or a Fault; none raises. Validation is a regex or a closed word
# table, so no coercer catches an exception.
# ---------------------------------------------------------------------------

_INT_RE = re.compile(r"[+-]?[0-9]+")
_FLOAT_RE = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

_BOOL_WORDS = {
    "true": True, "1": True, "yes": True, "on": True,
    "false": False, "0": False, "no": False, "off": False,
}


def coerce_str(raw):
    """str (Appendix B): the raw string passes through unchanged. Never fails."""
    return raw


def coerce_int(raw):
    """int (Appendix B): the raw string parses as a whole number, else a Fault."""
    return {
        True: lambda: int(raw),
        False: lambda: fault(
            "uncoercible_value", "value does not coerce to int; expected a whole number",
            "server", [], {"target_type": "int", "expected": "a whole number"}),
    }[_INT_RE.fullmatch(raw) is not None]()


def coerce_bool(raw):
    """bool (Appendix B): 'true'/'1'/'yes'/'on' read true and 'false'/'0'/'no'/'off' read false,
    case-insensitive; any other word is a Fault — the open-key read guarded by its no-match row."""
    return {
        True: lambda: _BOOL_WORDS[raw.lower()],
        False: lambda: fault(
            "uncoercible_value", "value does not coerce to bool; expected a boolean word",
            "server", [], {"target_type": "bool", "expected": "a boolean word"}),
    }[raw.lower() in _BOOL_WORDS]()


def coerce_float(raw):
    """float (Appendix B): the raw string parses as a number, else a Fault."""
    return {
        True: lambda: float(raw),
        False: lambda: fault(
            "uncoercible_value", "value does not coerce to float; expected a number",
            "server", [], {"target_type": "float", "expected": "a number"}),
    }[_FLOAT_RE.fullmatch(raw) is not None]()


def coerce_uuid(raw):
    """UUID (Appendix B): the raw string parses as a UUID, else a Fault."""
    return {
        True: lambda: uuid.UUID(raw),
        False: lambda: fault(
            "uncoercible_value", "value does not coerce to UUID; expected a UUID",
            "server", [], {"target_type": "UUID", "expected": "a UUID"}),
    }[_UUID_RE.fullmatch(raw) is not None]()


def coerce_key(raw):
    """key (Appendix B): a secret passes through as its string; its value never appears in a fault
    message or anywhere this module reports — only the variable's name does. Never fails."""
    return raw


# ---------------------------------------------------------------------------
# The coercer dispatch (Appendix B): the one place the six coercions are
# enumerated, one row per TargetType word.
# ---------------------------------------------------------------------------

by_target_type = {
    "str": coerce_str,
    "int": coerce_int,
    "bool": coerce_bool,
    "float": coerce_float,
    "UUID": coerce_uuid,
    "key": coerce_key,
}


# ---------------------------------------------------------------------------
# Capability 3 — the recurring scheduler's records (Appendix C). Plain records;
# TypedDict, never classes. The `float | NOTHING` and Callable fields are open
# values, so they are typed Any — the same shape EnvValues.values takes.
# ---------------------------------------------------------------------------


class Cadence(TypedDict):
    interval_seconds: float
    deadline_seconds: Any


class ScheduleSpec(TypedDict):
    key: str
    work: Callable
    cadence: Cadence
    decide: Callable


class ScheduleState(TypedDict):
    next_due: Any
    consecutive_faults: int
    attempted: int
    last_overran: bool
    stopping: bool


class Attempt(TypedDict):
    consecutive_faults: int
    attempted: int
    overran: bool


class TickPlan(TypedDict):
    kind: str
    seconds: Any
    reason: Any


class Disposition(TypedDict):
    kind: str
    delay: Any


class RunReport(TypedDict):
    key: str
    attempted: int
    succeeded: int
    faulted: int
    overran: int
    ended_reason: str
    in_flight_at_stop: bool


# ===========================================================================
# Capability 3 — the recurring scheduler, an ENGINE and a CLOCK-READER
# (Appendix C). schedule and run_schedules are the doors; drive_schedule is the
# per-work loop; plan_tick, advance_schedule and build_attempt hold every
# decision and read no world. If-free by construction: every branch is a dict
# literal of thunks read by subscript, so every declared boundary stays a
# direct, traceable call.
# ===========================================================================


def plan_tick(state, now):
    """Choose the next move for one schedule, the pure heart of the loop (Appendix C). A stopping state
    halts with decided_stop and takes precedence even when a run is due; a state whose next-due time is
    NOTHING or has arrived fires; otherwise it waits the gap. It reads no clock; now is handed in."""
    return {
        True: lambda: {"kind": "halt", "seconds": NOTHING, "reason": "decided_stop"},
        False: lambda: {
            True: lambda: {"kind": "fire", "seconds": NOTHING, "reason": NOTHING},
            False: lambda: {"kind": "wait", "seconds": state["next_due"] - now, "reason": NOTHING},
        }[state["next_due"] is NOTHING or now >= state["next_due"]](),
    }[state["stopping"]]()


def build_attempt(state, outcome, overran):
    """Build the run history the caller's decide reads, the one place the run counts fold (Appendix C).
    A fault raises consecutive_faults by one, a success resets it to zero; attempted always increments;
    the measured overrun passes through. It reads only whether the outcome is a fault, never its kind."""
    consecutive = {
        True: lambda: state["consecutive_faults"] + 1,
        False: lambda: 0,
    }[isinstance(outcome, dict) and "code" in outcome]()  # honest: ignore HC-P005: bare-union recognizer for the opaque outcome|Fault seam — isinstance guards "code" from raising on a non-dict success value
    return {
        "consecutive_faults": consecutive,
        "attempted": state["attempted"] + 1,
        "overran": overran,
    }


# ---------------------------------------------------------------------------
# The disposition dispatch (Appendix C): one row per DispositionKind word, each
# a lambda assembling the fresh ScheduleState that word commands. advance_schedule
# reads it by the merge-for-default idiom so a word outside the closed vocabulary
# halts loudly, naming every accepted kind.
# ---------------------------------------------------------------------------

_by_disposition_kind = {
    "continue": lambda state, attempt, cadence, disposition, now: {
        "next_due": now + cadence["interval_seconds"],
        "consecutive_faults": attempt["consecutive_faults"],
        "attempted": attempt["attempted"],
        "last_overran": attempt["overran"],
        "stopping": False,
    },
    "retry_after": lambda state, attempt, cadence, disposition, now: {
        "next_due": now + disposition["delay"],
        "consecutive_faults": attempt["consecutive_faults"],
        "attempted": attempt["attempted"],
        "last_overran": attempt["overran"],
        "stopping": False,
    },
    "stop": lambda state, attempt, cadence, disposition, now: {
        "next_due": state["next_due"],
        "consecutive_faults": attempt["consecutive_faults"],
        "attempted": attempt["attempted"],
        "last_overran": attempt["overran"],
        "stopping": True,
    },
}


def advance_schedule(state, attempt, cadence, disposition, now):
    """Fold one run's result into the schedule's memory (Appendix C), the single mutator of
    ScheduleState. It carries consecutive_faults, attempted and last_overran off the attempt and sets
    next_due from the disposition: continue sets now plus the cadence interval, retry_after sets now
    plus the delay, and stop leaves next_due and marks the state stopping. The disposition kind is a
    closed vocabulary, so the read is guarded by its no-match row — a word no branch carries can only be
    a caller contract bug, and advance_schedule's declared return is ScheduleState with no Fault arm, so
    the no-match lambda halts the loop at once, naming every accepted kind, rather than guessing."""
    handler = {
        disposition["kind"]: lambda state, attempt, cadence, disposition, now: (_ for _ in ()).throw(
            KeyError(
                f"disposition kind {disposition['kind']!r} matched no branch; "
                f"accepted kinds are {sorted(_by_disposition_kind)}"
            )
        ),
        **_by_disposition_kind,
    }[disposition["kind"]]
    return handler(state, attempt, cadence, disposition, now)


# ---------------------------------------------------------------------------
# The scheduler's boundaries (Appendix C): run_work and run_decide run the
# caller's injected code (the engine's "process" boundary), read_clock and
# wait_until touch the wall clock.
# ---------------------------------------------------------------------------


def read_clock():
    """Read the current wall-clock time (Appendix C), the scheduler's clock boundary. It returns a
    monotonic number of seconds and decides nothing; reading the clock is its one side effect."""
    return time.monotonic()


async def wait_until(seconds, stop):
    """Sleep until a due time or until the caller stops, whichever comes first (Appendix C), the
    bounded, stop-interruptible wait. It races the sleep against the stop signal, returning True when
    the stop fired before the interval elapsed and False when the full interval passed, so a stop ends
    an idle wait at once and never blocks shutdown."""
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
        return True
    except asyncio.TimeoutError:
        return False


async def run_work(work, deadline_seconds):
    """Run the caller's injected unit of work once, at the scheduler's engine boundary (Appendix C) —
    code the module did not write. It awaits the work and returns the work's own opaque result, the
    success value or honest-type's Fault, and never inspects the success value. deadline_seconds is the
    caller's budget, which drive_schedule measures against between two clock reads; run_work carries no
    overran channel of its own and never abandons a run."""
    return await work()


def run_decide(decide, outcome, attempt):
    """Run the caller's injected decide rule once, at the scheduler's engine boundary (Appendix C). It
    runs decide on the opaque outcome and the run history and returns the one Disposition it chose. It
    is synchronous, because decide is a pure rule; the scheduler owns the three dispositions and never
    interprets the fault."""
    return decide(outcome, attempt)


# ---------------------------------------------------------------------------
# The scheduler's orchestrator (Appendix C): the per-work loop. Each turn reads
# the clock and asks the pure plan_tick to wait, fire, or halt, then dispatches
# every world-touching and folding call through a dict literal of thunks keyed on
# the plan kind, so each declared boundary stays a direct call in declared order
# and only the chosen turn's calls run. The awaited boundary (wait_until on a
# wait, run_work on a fire) is the value of a sync thunk; the await itself is at
# the loop's top level, never buried in a lambda. A halt awaits an already-settled
# future, which returns at once without yielding.
# ---------------------------------------------------------------------------


async def drive_schedule(spec, stop):
    """The scheduler's one orchestrator (Appendix C), the per-work loop both doors hand a schedule to.
    Each turn it reads the clock, asks the pure plan_tick whether to wait, fire, or halt, and acts: on
    wait it sleeps through wait_until and ends recording signalled_stop when the stop fired; on fire it
    brackets run_work with two clock reads to measure the overrun, folds the outcome into the counts
    with build_attempt, consults decide through run_decide, and folds the disposition into the next
    state with advance_schedule, ending recording signalled_stop when the stop fired during the run; on
    halt it ends recording decided_stop. It tallies the attempts, successes, faults and overruns and
    returns one RunReport. It never builds a Fault; it reads only whether an outcome is a fault."""
    cadence = spec["cadence"]
    deadline = cadence["deadline_seconds"]
    state = {"next_due": NOTHING, "consecutive_faults": 0, "attempted": 0, "last_overran": False, "stopping": False}
    tally = {"attempted": 0, "succeeded": 0, "faulted": 0, "overran": 0}
    ending = {"running": True, "ended_reason": NOTHING, "in_flight_at_stop": False}
    settled = asyncio.get_running_loop().create_future()
    settled.set_result(None)
    while ending["running"]:
        now = read_clock()
        plan = plan_tick(state, now)
        kind = plan["kind"]
        stop_before = stop.is_set()
        result = await {
            "wait": lambda: wait_until(plan["seconds"], stop),
            "fire": lambda: run_work(spec["work"], deadline),
            "halt": lambda: settled,
        }[kind]()
        overran = {
            "wait": lambda: False,
            "fire": lambda: deadline is not NOTHING and (read_clock() - now) > deadline,
            "halt": lambda: False,
        }[kind]()
        faulted = {
            "wait": lambda: False,
            "fire": lambda: isinstance(result, dict) and "code" in result,  # honest: ignore HC-P005: bare-union recognizer for the opaque outcome|Fault seam — isinstance guards "code" from raising on a non-dict success value
            "halt": lambda: False,
        }[kind]()
        attempt = {
            "wait": lambda: None,
            "fire": lambda: build_attempt(state, result, overran),
            "halt": lambda: None,
        }[kind]()
        disposition = {
            "wait": lambda: None,
            "fire": lambda: run_decide(spec["decide"], result, attempt),
            "halt": lambda: None,
        }[kind]()
        state = {
            "wait": lambda: state,
            "fire": lambda: advance_schedule(state, attempt, cadence, disposition, now),
            "halt": lambda: state,
        }[kind]()
        tally = {
            "wait": lambda: tally,
            "fire": lambda: {
                "attempted": tally["attempted"] + 1,
                "succeeded": tally["succeeded"] + int(not faulted),
                "faulted": tally["faulted"] + int(faulted),
                "overran": tally["overran"] + int(overran),
            },
            "halt": lambda: tally,
        }[kind]()
        ending = {
            "wait": lambda: {
                True: lambda: {"running": False, "ended_reason": "signalled_stop", "in_flight_at_stop": False},
                False: lambda: ending,
            }[result](),
            "fire": lambda: {
                True: lambda: {"running": False, "ended_reason": "signalled_stop", "in_flight_at_stop": True},
                False: lambda: ending,
            }[(not stop_before) and stop.is_set()](),
            "halt": lambda: {"running": False, "ended_reason": plan["reason"], "in_flight_at_stop": False},
        }[kind]()
    return {
        "key": spec["key"],
        "attempted": tally["attempted"],
        "succeeded": tally["succeeded"],
        "faulted": tally["faulted"],
        "overran": tally["overran"],
        "ended_reason": ending["ended_reason"],
        "in_flight_at_stop": ending["in_flight_at_stop"],
    }


# ---------------------------------------------------------------------------
# The scheduler's two doors (Appendix C): schedule drives one unit of work;
# run_schedules drives a set concurrently under one awaited call and one stop.
# ---------------------------------------------------------------------------


async def schedule(work, cadence, decide, stop):
    """The single-work scheduler door (Appendix C): wrap the work, cadence and decide in a ScheduleSpec
    under the fixed key "", hand it and the stop to drive_schedule, and return the RunReport. It is
    awaited for the life of the one schedule."""
    spec = {"key": "", "work": work, "cadence": cadence, "decide": decide}
    return await drive_schedule(spec, stop)


async def run_schedules(specs, stop):
    """The many-schedule scheduler door (Appendix C), the surface the host awaits for process lifetime.
    It drives each spec through its own drive_schedule loop and awaits them together under one stop,
    returning one RunReport per spec in order."""
    reports = await asyncio.gather(*[drive_schedule(spec, stop) for spec in specs])
    return list(reports)


__all__ = [
    "NOTHING",
    "law",
    "verify_laws",
    "read_env",
    "resolve_env",
    "coerce_str",
    "coerce_int",
    "coerce_bool",
    "coerce_float",
    "coerce_uuid",
    "coerce_key",
    "plan_tick",
    "advance_schedule",
    "build_attempt",
    "schedule",
    "run_schedules",
]

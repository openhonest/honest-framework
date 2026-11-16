"""honest-errors — the error-cadence pure core (architecture v0.2, spec §2-§5).

A failure becomes one canonical ExceptionReport, the caller declares as data how it is handled, and
honest-errors computes the next cadence state and the display actions due now. This file holds only
the fifteen pure functions, the ten bounded vocabularies, the NOTHING absence sentinel, and the IR
record shapes. The door `capture`, the orchestrator `handle_failure`, and the two persistence
functions `load_cadence_state` / `store_cadence_state` run through the honest-persist boundary and
are parked until persistence is wired (bead: honest-errors cadence-state persistence).

No clock and no environment are read here: `environment`, `timestamp` and `now` are arguments. No
function raises; a failure returns as a bare Fault — a dict carrying a `code` — recognized by shape.

If-free by construction. A branch is a key computed and a thunk looked up in a closed table (P01),
so this file carries no `if` statement, no conditional expression, no comprehension `if`-clause, no
isinstance recognizer, and no variable-key table subscript. `pick` is the lazy two-row dispatch and
`read_or` is the open-key read guarded by its no-match row (P16), mirroring honest-check's own
_util.py. A domain module is the first to carry these locally; that is sanctioned.

Representation of absence. NOTHING is the explicit absent value an optional union arm holds, never
bare None and never an implicit default. It is the empty tuple: a single immutable value distinct
from every populated record, severity, mode or timestamp a field legitimately carries, and stable
under copy.deepcopy in both identity and equality, which the conformance laws rely on.
"""

from datetime import datetime, timedelta
from typing import Any, TypedDict

# ---------------------------------------------------------------------------
# If-free control primitives (P01, P16). A branch is a bool key into a closed
# two-row table of thunks; only the chosen arm runs. read_or reads a table by a
# key that may be absent, returning a named fallback thunk's result — never the
# default-filed-as-a-hit of table.get(key, default).
# ---------------------------------------------------------------------------

_TWO_ROW = {True: lambda when_true, when_false: when_true,
            False: lambda when_true, when_false: when_false}


def pick(flag, when_true, when_false):
    """Call and return when_true() when flag is truthy, else when_false(). The arms are thunks, so
    only the chosen one runs."""
    return _TWO_ROW[bool(flag)](when_true, when_false)()


def read_or(table, key, default_thunk):
    """table[key] when key is a member, else default_thunk() — the open-key read guarded by its
    no-match row, never the silent default of table.get(key, default)."""
    return pick(key in table, lambda: table[key], default_thunk)


# ---------------------------------------------------------------------------
# The absence sentinel (§4). An optional field holds a value or NOTHING.
# ---------------------------------------------------------------------------

NOTHING: Any = ()

# ---------------------------------------------------------------------------
# The bounded vocabularies (§2.1, §4, §5). Closed frozensets, never free str.
# ---------------------------------------------------------------------------

SEVERITIES = frozenset({"debug", "info", "warning", "error", "critical"})
ENVIRONMENTS = frozenset({"development", "production", "test"})
RESPONSE_MODES = frozenset({"returned", "acknowledged"})
PAYLOAD_SOURCES = frozenset({"js", "py"})
PRESET_NAMES = frozenset({"silent", "acknowledge", "report_back", "notify"})
ACTION_KINDS = frozenset({"show", "hide", "send"})
DISPLAY_STATUSES = frozenset({"showing", "pending"})
DURATION_KINDS = frozenset({"once", "period"})
TIMING_KINDS = frozenset({"immediate", "scheduled"})
FAULT_CODES = frozenset({"malformed_payload", "unknown_source", "unknown_preset"})

# ---------------------------------------------------------------------------
# The IR records (§2, §4, §5, §7). All TypedDict, no classes. Optional arms are
# typed `Any` because their absent value is the NOTHING sentinel, not None.
# ---------------------------------------------------------------------------


class JSErrorPayload(TypedDict):
    message: str
    source: str
    lineno: int
    colno: int
    stack: str
    url: str
    user_agent: str
    timestamp: str
    context: dict


class PythonExceptionPayload(TypedDict):
    exception_type: str
    message: str
    tb_file: str
    tb_line: int
    tb_function: str
    traceback: str
    context: dict


class ExceptionReport(TypedDict):
    exception_type: str
    message: str
    severity: str
    environment: str
    file: str
    line: int
    function: str
    traceback: str
    context: dict
    timestamp: str


class Fault(TypedDict):
    code: str
    message: str


class ResponseSpec(TypedDict):
    mode: str


class Period(TypedDict):
    seconds: int


class Duration(TypedDict):
    kind: str
    period: Any


class Scheduled(TypedDict):
    at: str


class Timing(TypedDict):
    kind: str
    scheduled: Any


class DisplaySpec(TypedDict):
    duration: Duration
    timing: Timing


class Cadence(TypedDict):
    respond: Any
    display: Any


class Acknowledgement(TypedDict):
    captured: bool


class DedupKey(TypedDict):
    exception_type: str
    file: str
    line: int


class LiveDisplay(TypedDict):
    key: DedupKey
    status: str
    until: Any
    due: Any


class CadenceState(TypedDict):
    live: list


class DisplayAction(TypedDict):
    key: DedupKey
    report: Any
    kind: str


class AdvanceResult(TypedDict):
    state: CadenceState
    actions: list


class CaptureResult(TypedDict):
    report: ExceptionReport
    response: Any
    actions: list


# ---------------------------------------------------------------------------
# Normalization (§3).
# ---------------------------------------------------------------------------


def js_severity(message):
    """Grade a browser failure: 'critical' when the message text contains 'critical'
    case-insensitively, 'error' otherwise. A predicate over the message, dispatched through a
    two-row table, not an if-ladder that grows a branch per rule."""
    return pick("critical" in message.lower(), lambda: "critical", lambda: "error")


def classify_js_payload(payload, environment, timestamp):
    """Normalize a raw browser JavaScript error object into the one canonical ExceptionReport (§3).
    Validates the foreign payload against the keys the JS shape requires and returns a bare Fault
    with code 'malformed_payload' when one is absent; otherwise decomposes the browser object into
    the report, grading severity with js_severity and stamping the environment and timestamp it was
    handed. environment and timestamp are arguments, never read from a clock or os.getenv."""
    required = ("message", "source", "lineno", "colno", "stack", "url", "user_agent", "timestamp")
    missing = frozenset(required) - frozenset(payload)

    def malformed():
        return {"code": "malformed_payload",
                "message": f"js payload missing required keys {sorted(missing)}; a browser error object must carry {list(required)}"}

    def report():
        return {
            "exception_type": "Error",
            "message": payload["message"],
            "severity": js_severity(payload["message"]),
            "environment": environment,
            "file": payload["source"],
            "line": payload["lineno"],
            "function": "",
            "traceback": payload["stack"],
            "context": pick("context" in payload, lambda: payload["context"], lambda: {}),
            "timestamp": timestamp,
        }

    return pick(not missing, report, malformed)


def classify_py_payload(payload, environment, timestamp):
    """Normalize a raw server Python exception payload into the one canonical ExceptionReport (§3).
    Validates the foreign payload against the keys the Python shape requires and returns a bare Fault
    with code 'malformed_payload' when one is absent; otherwise decomposes the exception into the
    report, stamps severity 'error' for every Python-path report, and writes the environment and
    timestamp it was handed. environment and timestamp are arguments, never a clock or the env."""
    required = ("exception_type", "message", "tb_file", "tb_line", "tb_function", "traceback")
    missing = frozenset(required) - frozenset(payload)

    def malformed():
        return {"code": "malformed_payload",
                "message": f"python payload missing required keys {sorted(missing)}; an exception payload must carry {list(required)}"}

    def report():
        return {
            "exception_type": payload["exception_type"],
            "message": payload["message"],
            "severity": "error",
            "environment": environment,
            "file": payload["tb_file"],
            "line": payload["tb_line"],
            "function": payload["tb_function"],
            "traceback": payload["traceback"],
            "context": pick("context" in payload, lambda: payload["context"], lambda: {}),
            "timestamp": timestamp,
        }

    return pick(not missing, report, malformed)


# The normalizer dispatch table (§3, §6): source word -> normalizer.
normalize_by_source = {"js": classify_js_payload, "py": classify_py_payload}


def normalize(source, payload, environment, timestamp):
    """Dispatch the raw payload to its normalizer by the host's source word through the
    normalize_by_source table and return the normalizer's ExceptionReport, or forward its
    malformed_payload Fault (§6). A source word the table does not carry is the no-match row, for
    which normalize returns a bare Fault with code 'unknown_source' rather than guessing."""

    def unknown_source(_payload, _environment, _timestamp):
        accepted = sorted(normalize_by_source)
        return {"code": "unknown_source",
                "message": f"source {source!r} matched no normalizer; accepted sources are {accepted}"}

    handler = read_or(normalize_by_source, source, lambda: unknown_source)
    return handler(payload, environment, timestamp)


# ---------------------------------------------------------------------------
# The cadence declaration and its presets (§4.1).
# ---------------------------------------------------------------------------


def preset_silent():
    """The 'silent' preset Cadence (§4.1): respond Absent, display Absent."""
    return {"respond": NOTHING, "display": NOTHING}


def preset_acknowledge():
    """The 'acknowledge' preset Cadence (§4.1): respond acknowledged, display Absent."""
    return {"respond": {"mode": "acknowledged"}, "display": NOTHING}


def preset_report_back():
    """The 'report_back' preset Cadence (§4.1): respond returned, display Absent."""
    return {"respond": {"mode": "returned"}, "display": NOTHING}


def preset_notify():
    """The 'notify' preset Cadence (§4.1): respond acknowledged, display Once-Immediate."""
    return {
        "respond": {"mode": "acknowledged"},
        "display": {
            "duration": {"kind": "once", "period": NOTHING},
            "timing": {"kind": "immediate", "scheduled": NOTHING},
        },
    }


# The preset dispatch table (§4.1): preset name -> its Cadence constructor.
presets = {
    "silent": preset_silent,
    "acknowledge": preset_acknowledge,
    "report_back": preset_report_back,
    "notify": preset_notify,
}


def resolve_cadence(arg):
    """Resolve what the caller passed into a full Cadence (§4.1). A full Cadence (a mapping) passes
    through unchanged; a PresetName (a string) resolves through the presets table. The record-vs-name
    discrimination is a recognizer on the argument — whether it answers to `keys`, a mapping does and
    a name does not — not an isinstance and not an if. A name the presets table does not carry is the
    no-match row, returning a bare Fault with code 'unknown_preset' naming the presets it accepts."""

    def resolve_name():
        def unknown_preset():
            accepted = sorted(presets)
            return {"code": "unknown_preset",
                    "message": f"preset name {arg!r} matched no preset; accepted presets are {accepted}"}

        constructor = read_or(presets, arg, lambda: unknown_preset)
        return constructor()

    return pick(hasattr(arg, "keys"), lambda: arg, resolve_name)


# ---------------------------------------------------------------------------
# The response (§4, §6).
# ---------------------------------------------------------------------------


def build_response(report, cadence):
    """Build the caller's response from the cadence's respond spec (§6): the normalized report when
    mode is 'returned', a bare Acknowledgement when 'acknowledged', and NOTHING when respond is
    Absent. The respond spec selects the outcome through a table, not an if."""
    respond = cadence["respond"]
    outcomes = {
        "returned": lambda: report,
        "acknowledged": lambda: {"captured": True},
        "__absent__": lambda: NOTHING,
    }
    mode = pick(respond is not NOTHING, lambda: respond["mode"], lambda: "__absent__")
    return read_or(outcomes, mode, lambda: lambda: NOTHING)()


# ---------------------------------------------------------------------------
# The cadence state and its pure advance steps (§5). Each returns a new
# AdvanceResult and never mutates the state it was given.
# ---------------------------------------------------------------------------


def dedup_key(report):
    """The display identity of a report (§5): its exception_type, file and line. Two failures that
    agree on those three are the same display."""
    return {"exception_type": report["exception_type"], "file": report["file"], "line": report["line"]}


def expire_elapsed(state, now):
    """Drop displays whose held period has ended (§5): remove every LiveDisplay whose until time has
    passed relative to now, returning the trimmed state and a hide DisplayAction for each removed
    entry. now is an argument, never read from a clock."""

    def elapsed(display):
        until = display["until"]
        return until is not NOTHING and until <= now

    live = state["live"]
    kept = list(filter(lambda display: not elapsed(display), live))
    gone = list(filter(elapsed, live))
    actions = list(map(lambda display: {"key": display["key"], "report": NOTHING, "kind": "hide"}, gone))
    return {"state": {"live": kept}, "actions": actions}


def release_due(state, now):
    """Turn scheduled displays live when their time arrives (§5): flip every Pending LiveDisplay
    whose due time has arrived relative to now to Showing, returning the updated state and a show
    DisplayAction for each released entry. now is an argument."""

    def due(display):
        at = display["due"]
        return at is not NOTHING and at <= now

    def flip(display):
        return pick(due(display), lambda: {**display, "status": "showing"}, lambda: dict(display))

    live = state["live"]
    new_live = list(map(flip, live))
    released = list(filter(due, live))
    actions = list(map(lambda display: {"key": display["key"], "report": NOTHING, "kind": "show"}, released))
    return {"state": {"live": new_live}, "actions": actions}


def add_display(state, report, cadence, now):
    """Add the new report's display per the caller's declaration (§5). When display is Absent, add
    nothing. When present, add a LiveDisplay keyed by dedup_key(report): Showing with an until when
    timing is Immediate (a period duration setting how long it stays), or Pending with a due when
    timing is Scheduled. A display whose key is already live is not added again. Returns the updated
    state and the show DisplayAction for an immediate display. now is an argument."""
    display = cadence["display"]

    def absent():
        return {"state": {"live": list(state["live"])}, "actions": []}

    def present():
        key = dedup_key(report)
        already_live = any(map(lambda entry: entry["key"] == key, state["live"]))

        def skip():
            return {"state": {"live": list(state["live"])}, "actions": []}

        def place():
            duration = display["duration"]
            timing = display["timing"]

            def until_period():
                seconds = duration["period"]["seconds"]
                return (datetime.fromisoformat(now) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")

            until_by_kind = {"once": lambda: NOTHING, "period": until_period}

            def immediate():
                until = read_or(until_by_kind, duration["kind"], lambda: lambda: NOTHING)()
                entry = {"key": key, "status": "showing", "until": until, "due": NOTHING}
                return entry, [{"key": key, "report": report, "kind": "show"}]

            def scheduled():
                entry = {"key": key, "status": "pending", "until": NOTHING, "due": timing["scheduled"]["at"]}
                return entry, []

            build_by_timing = {"immediate": immediate, "scheduled": scheduled}
            entry, actions = read_or(build_by_timing, timing["kind"], lambda: immediate)()
            return {"state": {"live": [*state["live"], entry]}, "actions": actions}

        return pick(already_live, skip, place)

    return pick(display is not NOTHING, present, absent)


def advance_cadence(state, report, cadence, now):
    """Compute the next cadence state and the actions due now (§5): thread the state through
    expire_elapsed, release_due and add_display, collecting their DisplayActions, and return one
    AdvanceResult. Never mutates its argument; the orchestrator (not this function) writes the
    returned state, so the state has a single mutator. now is an argument."""
    expired = expire_elapsed(state, now)
    released = release_due(expired["state"], now)
    added = add_display(released["state"], report, cadence, now)
    return {
        "state": added["state"],
        "actions": [*expired["actions"], *released["actions"], *added["actions"]],
    }


__all__ = [
    "NOTHING",
    "SEVERITIES", "ENVIRONMENTS", "RESPONSE_MODES", "PAYLOAD_SOURCES", "PRESET_NAMES",
    "ACTION_KINDS", "DISPLAY_STATUSES", "DURATION_KINDS", "TIMING_KINDS", "FAULT_CODES",
    "JSErrorPayload", "PythonExceptionPayload", "ExceptionReport", "Fault", "ResponseSpec",
    "Period", "Duration", "Scheduled", "Timing", "DisplaySpec", "Cadence", "Acknowledgement",
    "DedupKey", "LiveDisplay", "CadenceState", "DisplayAction", "AdvanceResult", "CaptureResult",
    "js_severity", "classify_js_payload", "classify_py_payload", "normalize",
    "preset_silent", "preset_acknowledge", "preset_report_back", "preset_notify",
    "resolve_cadence", "build_response", "dedup_key",
    "expire_elapsed", "release_due", "add_display", "advance_cadence",
    "normalize_by_source", "presets",
]

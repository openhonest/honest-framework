"""honest-errors generative laws — the error-cadence pure core (spec §2-§5).

suite.json pins exact values at representative points that live cleanly as JSON. These laws assert
the properties that hold across a whole vocabulary or a sequence of calls, and the behaviour that
carries honest-errors' own `Absent` encoding, which JSON cannot express: the preset Cadences,
resolve_cadence's pass-through, the three build_response outcomes, every required payload key, the
case-insensitive severity marker, the no-mutation guarantee of the cadence-state steps, the
once-not-twice rule, and the advance composition.

The representation contract these laws fix, which honest_errors implements:
  NOTHING          the absent sentinel; an optional field holds a value or NOTHING, which is `None`, the framework's idiomatic null (honest-type-architecture.md §5.6).
  ResponseSpec     {"mode": "returned" | "acknowledged"}
  Duration         {"kind": "once" | "period", "period": {"seconds": int} | NOTHING}
  Timing           {"kind": "immediate" | "scheduled", "scheduled": {"at": str} | NOTHING}
  DisplaySpec      {"duration": Duration, "timing": Timing}
  Cadence          {"respond": ResponseSpec | NOTHING, "display": DisplaySpec | NOTHING}
  Acknowledgement  {"captured": True}
  DedupKey         {"exception_type": str, "file": str, "line": int}
  LiveDisplay      {"key": DedupKey, "status": "showing" | "pending", "until": str | NOTHING, "due": str | NOTHING}
  CadenceState     {"live": [LiveDisplay]}
  DisplayAction    {"key": DedupKey, "report": ExceptionReport, "kind": "show" | "hide" | "send"}
  AdvanceResult    {"state": CadenceState, "actions": [DisplayAction]}

A fault arm is a dict carrying a `code`; a success arm is the value itself. No ok/err envelope.
"""

import copy

import honest_errors
from probe_add_display import probe_add_display
from honest_errors import (
    NOTHING,
    PRESET_NAMES,
    SEVERITIES,
    add_display,
    advance_cadence,
    build_response,
    classify_js_payload,
    classify_py_payload,
    expire_elapsed,
    js_severity,
    preset_acknowledge,
    preset_notify,
    preset_report_back,
    preset_silent,
    release_due,
    resolve_cadence,
)

_PRESET_FN = {
    "silent": preset_silent,
    "acknowledge": preset_acknowledge,
    "report_back": preset_report_back,
    "notify": preset_notify,
}


def _is_fault(value):
    return isinstance(value, dict) and "code" in value


def _report(exc="ValueError", message="bad literal", severity="error",
            environment="development", file="svc.py", line=88, function="parse"):
    return {
        "exception_type": exc, "message": message, "severity": severity,
        "environment": environment, "file": file, "line": line, "function": function,
        "traceback": "Traceback ...", "context": {}, "timestamp": "2026-11-15T12:00:00Z",
    }


def _js_payload():
    return {
        "message": "render went critical", "source": "app.js", "lineno": 42, "colno": 7,
        "stack": "at render (app.js:42:7)", "url": "https://example.test/app",
        "user_agent": "UA/1.0", "timestamp": "2026-11-15T11:59:00Z", "context": {},
    }


def _py_payload():
    return {
        "exception_type": "ValueError", "message": "bad literal", "tb_file": "svc.py",
        "tb_line": 88, "tb_function": "parse", "traceback": "Traceback ...", "context": {},
    }


# ---- laws -------------------------------------------------------------------

def law_preset_cadences():
    """Each preset returns exactly its declared Cadence (§4.1), carrying NOTHING for an absent arm."""
    once_immediate = {
        "duration": {"kind": "once", "period": NOTHING},
        "timing": {"kind": "immediate", "scheduled": NOTHING},
    }
    expect = {
        "silent": {"respond": NOTHING, "display": NOTHING},
        "acknowledge": {"respond": {"mode": "acknowledged"}, "display": NOTHING},
        "report_back": {"respond": {"mode": "returned"}, "display": NOTHING},
        "notify": {"respond": {"mode": "acknowledged"}, "display": once_immediate},
    }
    bad = []
    for name, fn in _PRESET_FN.items():
        got = fn()
        if got != expect[name]:
            bad.append(f"preset_{name}() = {got!r}, expected {expect[name]!r}")
    return bad


def law_preset_names_match_functions():
    """PRESET_NAMES is exactly the set of presets that have a constructor function (§4.1)."""
    if set(PRESET_NAMES) != set(_PRESET_FN):
        return [f"PRESET_NAMES {set(PRESET_NAMES)!r} != preset functions {set(_PRESET_FN)!r}"]
    return []


def law_resolve_passthrough_and_names():
    """resolve_cadence passes a full Cadence through unchanged, and resolves every PRESET_NAME to the
    Cadence its constructor builds (§4.1)."""
    bad = []
    cadence = {"respond": {"mode": "returned"}, "display": NOTHING}
    got = resolve_cadence(copy.deepcopy(cadence))
    if got != cadence:
        bad.append(f"resolve_cadence(Cadence) = {got!r}, expected it unchanged {cadence!r}")
    for name in PRESET_NAMES:
        got = resolve_cadence(name)
        want = _PRESET_FN[name]()
        if got != want:
            bad.append(f"resolve_cadence({name!r}) = {got!r}, expected {want!r}")
    return bad


def law_build_response_outcomes():
    """build_response gives the three outcomes the respond spec fixes (§4, §6): the report when
    mode is returned, an Acknowledgement when acknowledged, NOTHING when respond is Absent."""
    report = _report()
    cases = [
        ({"respond": NOTHING, "display": NOTHING}, NOTHING),
        ({"respond": {"mode": "returned"}, "display": NOTHING}, report),
        ({"respond": {"mode": "acknowledged"}, "display": NOTHING}, {"captured": True}),
    ]
    bad = []
    for cadence, want in cases:
        got = build_response(report, cadence)
        if got != want:
            bad.append(f"build_response(report, respond={cadence['respond']!r}) = {got!r}, expected {want!r}")
    return bad


def law_js_severity_marker():
    """js_severity returns a SEVERITIES member, and 'critical' is a case-insensitive substring test:
    a message containing 'critical' in any case grades critical, every other message grades error."""
    bad = []
    samples = {
        "the widget went critical": "critical",
        "CRITICAL meltdown": "critical",
        "a CrItIcAl path": "critical",
        "criticality warning": "critical",
        "undefined is not a function": "error",
        "": "error",
        "crit": "error",
    }
    for message, want in samples.items():
        got = js_severity(message)
        if got not in SEVERITIES:
            bad.append(f"js_severity({message!r}) = {got!r}, not a SEVERITIES member")
        elif got != want:
            bad.append(f"js_severity({message!r}) = {got!r}, expected {want!r}")
    return bad


def law_missing_key_is_malformed():
    """Removing any one required key from a payload is reported as a malformed_payload fault (§3).
    `context` is optional (a pass-through bag) and is not in the required set."""
    bad = []
    for label, full, classify in (
        ("js", _js_payload(), classify_js_payload),
        ("py", _py_payload(), classify_py_payload),
    ):
        required = [k for k in full if k != "context"]
        for key in required:
            payload = {k: v for k, v in full.items() if k != key}
            got = classify(payload, "production", "2026-11-15T12:00:00Z")
            if not _is_fault(got) or got.get("code") != "malformed_payload":
                bad.append(f"classify_{label}_payload without {key!r} = {got!r}, expected a malformed_payload fault")
    return bad


def law_advance_steps_do_not_mutate():
    """Every cadence-state step returns a new state and never mutates the one it was given (§5)."""
    bad = []
    report = _report()
    cadence = {
        "respond": NOTHING,
        "display": {"duration": {"kind": "once", "period": NOTHING},
                    "timing": {"kind": "immediate", "scheduled": NOTHING}},
    }
    state = {"live": [
        {"key": {"exception_type": "KeyError", "file": "a.py", "line": 1},
         "status": "showing", "until": "2026-11-15T11:00:00Z", "due": NOTHING},
        {"key": {"exception_type": "IOError", "file": "b.py", "line": 2},
         "status": "pending", "until": NOTHING, "due": "2026-11-15T11:30:00Z"},
    ]}
    now = "2026-11-15T12:00:00Z"
    for label, call in (
        ("expire_elapsed", lambda s: expire_elapsed(s, now)),
        ("release_due", lambda s: release_due(s, now)),
        ("add_display", lambda s: add_display(s, report, cadence, now)),
        ("advance_cadence", lambda s: advance_cadence(s, report, cadence, now)),
    ):
        before = copy.deepcopy(state)
        result = call(state)
        if state != before:
            bad.append(f"{label} mutated its input state: {state!r} != {before!r}")
        if not isinstance(result, dict) or set(result.keys()) != {"state", "actions"}:
            bad.append(f"{label} returned {result!r}, expected an AdvanceResult {{state, actions}}")
    return bad


def law_once_display_not_added_twice():
    """A Once display whose key is already live is not added a second time (§5)."""
    report = _report()
    key = {"exception_type": report["exception_type"], "file": report["file"], "line": report["line"]}
    cadence = {
        "respond": NOTHING,
        "display": {"duration": {"kind": "once", "period": NOTHING},
                    "timing": {"kind": "immediate", "scheduled": NOTHING}},
    }
    now = "2026-11-15T12:00:00Z"
    state = {"live": [{"key": key, "status": "showing", "until": NOTHING, "due": NOTHING}]}
    result = add_display(state, report, cadence, now)
    live_for_key = [d for d in result["state"]["live"] if d["key"] == key]
    if len(live_for_key) != 1:
        return [f"a Once display already live was added again: {len(live_for_key)} entries for {key!r}"]
    return []


_LAWS = [
    law_preset_cadences,
    law_preset_names_match_functions,
    law_resolve_passthrough_and_names,
    law_build_response_outcomes,
    law_js_severity_marker,
    law_missing_key_is_malformed,
    law_advance_steps_do_not_mutate,
    law_once_display_not_added_twice,
    probe_add_display,
]


def run():
    failures = []
    for law in _LAWS:
        failures.extend(f"{law.__name__}: {msg}" for msg in law())
    for msg in failures:
        print(f"LAW FAIL {msg}")
    print(f"laws: {len(_LAWS) - len({m.split(':')[0] for m in failures})} law-functions clean, {len(failures)} failures")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(run())

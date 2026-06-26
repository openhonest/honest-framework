"""honest-errors conformance: the generative proof (the behavioural circle).

Probes every branch a data file cannot reach: the JS severity predicate, the payload defaults,
the rate-limiter's pruning and every suppression path with state threading, and the email
formatter. The boundaries (< vs <=, the hour constant, the context limit) are pinned at their exact
edges, the suppression paths assert the full threaded state, the email body is pinned verbatim, the
faults carry exact messages, the four vocabularies are pinned to a hand-written oracle, and the
public surface is checked against __all__ — so a mechanical mutation of any of these fails a probe.
Each probe returns a list of failures; run() aggregates.
"""

from honest_errors import (
    BEHAVIOR_NAMES,
    ENVIRONMENTS,
    SEVERITIES,
    SUPPRESS_REASONS,
    behaviors_for,
    check_rate_limit,
    classify_js_payload,
    classify_py_payload,
    dedup_key,
    format_email_body,
    new_state,
    should_bypass_dedup,
)

_TS = "2026-01-01T00:00:00Z"


def _probe_normalize():
    """Normalization (§3): both shapes to one report, faults as data, severity predicate, and the
    optional-field defaults."""
    bad = []

    # JS, full payload, message marked critical -> critical; optional fields used verbatim.
    full = {"message": "Critical failure", "source": "app.js", "lineno": 42, "colno": 5, "stack": "at f", "function": "h", "context": {"u": 1}}
    result = classify_js_payload(full, "production", _TS)
    report = result.get("ok", {})
    if report.get("severity") != "critical" or report.get("traceback") != "at f" or report.get("function") != "h" or report.get("context") != {"u": 1}:
        bad.append(f"JS full/critical report wrong: {result}")
    if report.get("exception_type") != "JavaScriptError" or report.get("timestamp") != _TS:
        bad.append("JS report should carry JavaScriptError type and the supplied timestamp")

    # JS, minimal payload, ordinary message -> error; optional fields default.
    minimal = {"message": "boom", "source": "app.js", "lineno": 1, "colno": 1}
    report = classify_js_payload(minimal, "test", _TS)["ok"]
    if report["severity"] != "error" or report["traceback"] != "" or report["function"] != "" or report["context"] != {}:
        bad.append(f"JS minimal report should default optional fields and be 'error': {report}")

    # JS missing a required key -> malformed_payload naming it, with the exact message and category.
    miss = classify_js_payload({"message": "x", "source": "a", "lineno": 1}, "test", _TS)
    if miss.get("err", {}).get("code") != "malformed_payload" or "colno" not in miss["err"]["detail"]["missing"]:
        bad.append(f"a JS payload missing colno should fault: {miss}")
    if miss["err"]["message"] != "JS error payload missing key(s): ['colno']" or miss["err"]["category"] != "client":
        bad.append(f"a JS malformed fault should carry the exact message and the client category: {miss['err']}")

    # Python, full payload -> severity defaults to error.
    py = {"exception_type": "ValueError", "message": "bad", "tb_file": "x.py", "tb_line": 10, "tb_function": "g", "traceback": "TB", "context": {"k": 2}}
    report = classify_py_payload(py, "production", _TS)["ok"]
    if report["severity"] != "error" or report["exception_type"] != "ValueError" or report["file"] != "x.py" or report["line"] != 10:
        bad.append(f"Python report wrong: {report}")

    # Python minimal -> traceback/context default.
    report = classify_py_payload({"exception_type": "E", "message": "m", "tb_file": "f", "tb_line": 1, "tb_function": "fn"}, "test", _TS)["ok"]
    if report["traceback"] != "" or report["context"] != {}:
        bad.append("Python minimal should default traceback/context")

    # Python missing a required key -> malformed_payload with the exact message and server category.
    py_miss = classify_py_payload({"exception_type": "E", "message": "m", "tb_file": "f", "tb_line": 1}, "test", _TS)
    if py_miss.get("err", {}).get("code") != "malformed_payload" or "tb_function" not in py_miss["err"]["detail"]["missing"]:
        bad.append("a Python payload missing tb_function should fault, naming it in the detail")
    if py_miss["err"]["message"] != "Python exception payload missing key(s): ['tb_function']" or py_miss["err"]["category"] != "server":
        bad.append(f"a Python malformed fault should carry the exact message and the server category: {py_miss['err']}")

    # should_bypass_dedup: critical bypasses, others do not.
    if not should_bypass_dedup("critical") or should_bypass_dedup("error"):
        bad.append("should_bypass_dedup must be true only for critical")
    return bad


def _probe_behaviors():
    """Behavior policy (§4): each declared environment, and the development default for unknowns."""
    bad = []
    if behaviors_for("production") != [{"name": "log", "order": 0}, {"name": "email", "order": 1}]:
        bad.append("production behaviors wrong")
    if behaviors_for("development") != [{"name": "log", "order": 0}, {"name": "reraise", "order": 1}]:
        bad.append("development behaviors wrong")
    if behaviors_for("test") != [{"name": "log", "order": 0}]:
        bad.append("test behaviors wrong")
    if behaviors_for("staging") != behaviors_for("development"):
        bad.append("an unknown environment should fall back to development")
    return bad


def _probe_ratelimit():
    """The throttle (§5): every suppression path, the hourly/dedup pruning, the exact boundaries, and
    state threading. Never mutates the input state."""
    bad = []
    key = dedup_key({"exception_type": "ValueError", "file": "x.py", "line": 10, "message": "m"})
    if key != {"exception_type": "ValueError", "file": "x.py", "line": 10}:
        bad.append(f"dedup_key wrong: {key}")
    if new_state() != {"dedup_cache": {}, "hourly_sends": []}:
        bad.append("new_state wrong")
    config = {"dedup_window_seconds": 60, "max_per_hour": 3}

    # Allow from empty state; the send is recorded; the input state is untouched.
    start = new_state()
    decision, state = check_rate_limit(key, config, start, 1000)
    if decision != {"should_send": True, "reason": ""} or state["hourly_sends"] != [1000] or "ValueError|x.py|10" not in state["dedup_cache"]:
        bad.append(f"empty state should allow and record: {decision} {state}")
    if start != {"dedup_cache": {}, "hourly_sends": []}:
        bad.append("check_rate_limit must not mutate its state argument")

    # Hourly suppression at max_per_hour; a >1h-old send is pruned (not counted). The full threaded
    # state is pinned, not just the decision, so the returned state's keys are constrained too.
    decision, state = check_rate_limit(key, config, {"dedup_cache": {}, "hourly_sends": [1000 - 4000, 990, 995, 998]}, 1000)
    if decision != {"should_send": False, "reason": "rate_limit_hourly"}:
        bad.append(f"at the cap it should suppress hourly: {decision}")
    if state != {"dedup_cache": {}, "hourly_sends": [990, 995, 998]}:
        bad.append(f"hourly suppression should prune the >1h send and thread state forward: {state}")

    # Dedup suppression: same key fired within the window (hourly under cap). State pinned in full.
    decision, state = check_rate_limit(key, config, {"dedup_cache": {"ValueError|x.py|10": 990}, "hourly_sends": [990]}, 1000)
    if decision != {"should_send": False, "reason": "rate_limit_dedup"}:
        bad.append(f"a recent same-key send should suppress dedup: {decision}")
    if state != {"dedup_cache": {"ValueError|x.py|10": 990}, "hourly_sends": [990]}:
        bad.append(f"dedup suppression should thread state forward unchanged: {state}")

    # Last send OUTSIDE the dedup window -> allowed (the not-suppressed dedup branch).
    decision, _ = check_rate_limit(key, config, {"dedup_cache": {"ValueError|x.py|10": 900}, "hourly_sends": [900]}, 1000)
    if decision["should_send"] is not True:
        bad.append("a send older than the dedup window should be allowed")

    # Allow prunes a stale dedup entry for another key, and records the new one.
    _, state = check_rate_limit(key, config, {"dedup_cache": {"Other|y.py|1": 900}, "hourly_sends": []}, 1000)
    if "Other|y.py|1" in state["dedup_cache"] or "ValueError|x.py|10" not in state["dedup_cache"]:
        bad.append(f"allow should prune stale dedup entries and record the new key: {state}")

    # Boundaries (< vs <= at each prune/window, and the hour constant). A send exactly one hour old is
    # pruned, so at the cap it does not count; one second younger still counts.
    hourly_cap = {"dedup_window_seconds": 60, "max_per_hour": 1}
    at_hour, _ = check_rate_limit(key, hourly_cap, {"dedup_cache": {}, "hourly_sends": [10000 - 3600]}, 10000)
    if at_hour["should_send"] is not True:
        bad.append("a send exactly one hour old is pruned, so the cap is not reached")
    under_hour, _ = check_rate_limit(key, hourly_cap, {"dedup_cache": {}, "hourly_sends": [10000 - 3599]}, 10000)
    if under_hour["should_send"] is not False:
        bad.append("a send one second under the hour still counts toward the cap")

    # Dedup-window edge: a prior send exactly at the window is outside it (allowed); another key's
    # entry exactly one window old is pruned on the allow path.
    wide = {"dedup_window_seconds": 60, "max_per_hour": 5}
    at_window, edge_state = check_rate_limit(key, wide, {"dedup_cache": {"ValueError|x.py|10": 9940, "Other|y.py|1": 9940}, "hourly_sends": [9940]}, 10000)
    if at_window["should_send"] is not True:
        bad.append("a prior send exactly at the dedup window is outside it and allowed")
    if "Other|y.py|1" in edge_state["dedup_cache"]:
        bad.append("a dedup entry exactly one window old is pruned on the allow path")
    return bad


def _probe_email():
    """The email body (§6): rendered verbatim — labels, alignment, separators all pinned — plus the
    empty-context line and the exact ten-item context truncation."""
    bad = []
    report = {"severity": "error", "environment": "production", "timestamp": "t", "exception_type": "E", "message": "m", "file": "f.py", "line": 3, "function": "g", "traceback": "TB", "context": {"a": 1, "b": 2}}
    expected = (
        "Severity:    error\n"
        "Environment: production\n"
        "Time:        t\n"
        "Type:        E\n"
        "Message:     m\n"
        "Location:    f.py:3 in g\n"
        "Context:     a=1, b=2\n"
        "\n"
        "Traceback:\n"
        "TB"
    )
    body = format_email_body(report)
    if body != expected:
        bad.append(f"email body not rendered verbatim: {body!r}")

    # Empty context renders without crashing: only the context line goes empty.
    if format_email_body({**report, "context": {}}) != expected.replace("a=1, b=2", ""):
        bad.append("an empty-context body should render with an empty context line")

    # A context renders exactly the first ten items: the tenth is present, the eleventh is not.
    big = format_email_body({**report, "context": {f"k{i}": i for i in range(15)}})
    if "k9=9" not in big or "k10=10" in big:
        bad.append("context should be truncated to exactly the first ten items")
    return bad


def _probe_vocabularies():
    """The four closed vocabularies (§2), pinned to a hand-written oracle — the contract honest-test
    enumerates and honest-check treats as discriminant sets. The expected members are literals here,
    not the module's own value, so a dropped, emptied, or renamed member fails."""
    bad = []
    expected = {
        "SEVERITIES": (SEVERITIES, {"debug", "info", "warning", "error", "critical"}),
        "ENVIRONMENTS": (ENVIRONMENTS, {"development", "production", "test"}),
        "BEHAVIOR_NAMES": (BEHAVIOR_NAMES, {"log", "email", "reraise"}),
        "SUPPRESS_REASONS": (SUPPRESS_REASONS, {"rate_limit_hourly", "rate_limit_dedup"}),
    }
    for name, (actual, members) in expected.items():
        if actual != frozenset(members):
            bad.append(f"vocabulary {name} drifted from its declared contract: {actual}")
    return bad


def _probe_public_surface():
    """Every name the package promises in __all__ resolves on the package (§2). Catches a dropped
    re-export or an emptied __all__ entry — the adopter-visible surface the behavioural probes reach
    only through direct imports."""
    import honest_errors

    bad = []
    for name in honest_errors.__all__:
        if not hasattr(honest_errors, name):
            bad.append(f"__all__ promises {name!r} but the package does not export it")
    return bad


def run():
    probes = {
        "normalize": _probe_normalize(),
        "behaviors": _probe_behaviors(),
        "ratelimit": _probe_ratelimit(),
        "email": _probe_email(),
        "vocabularies": _probe_vocabularies(),
        "public_surface": _probe_public_surface(),
    }
    violations = [(name, messages) for name, messages in probes.items() if messages]
    for name, messages in violations:
        print(f"FAIL HE-probe [{name}]: {messages}")
    passed = sum(1 for messages in probes.values() if not messages)
    print(f"HE laws: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())

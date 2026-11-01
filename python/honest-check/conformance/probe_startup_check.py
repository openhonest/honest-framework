"""startup_check hands paths to check_paths, returns that diagnostic list, and acts
per on_error: 'warn' returns and does not raise, 'raise' raises HonestCheckError
when a finding reaches severity.

A class .py produces an error-severity HC-P003 (the .hd: startup_check returns the
same diagnostic list check_paths produced). Under on_error 'warn', severity 'error'
it returns that list and does not raise; under on_error 'raise' it raises
HonestCheckError. 'halt' is never exercised here: it would exit the process.
Its side effect is writing stderr, redirected here so the run stays quiet.
"""

import contextlib
import io
import os
import tempfile

_CLASS_SOURCE = "class Report:\n    pass\n"

_CASES = [
    {"on_error": "warn", "severity": "error", "want_rule": "HC-P003", "should_raise": False},
    {"on_error": "raise", "severity": "error", "should_raise": True},
]


def probe_startup_check():
    try:
        from honest_check import startup_check
    except ImportError as exc:
        return [f"cannot import startup_check: {exc}"]

    bad = []
    for case in _CASES:
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "source.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_CLASS_SOURCE)
            stderr = io.StringIO()
            if case["should_raise"]:
                raised = None
                try:
                    with contextlib.redirect_stderr(stderr):
                        startup_check([path], case["on_error"], case["severity"])
                except Exception as exc:  # the probe records the raise as data
                    raised = exc
                if raised is None:
                    bad.append(
                        f"startup_check([{path!r}], 'raise', 'error') did not raise; "
                        f"expected HonestCheckError"
                    )
                elif type(raised).__name__ != "HonestCheckError":
                    bad.append(
                        f"startup_check([{path!r}], 'raise', 'error') raised "
                        f"{type(raised).__name__}, expected HonestCheckError"
                    )
            else:
                raised = None
                got = None
                try:
                    with contextlib.redirect_stderr(stderr):
                        got = startup_check([path], case["on_error"], case["severity"])
                except Exception as exc:
                    raised = exc
                if raised is not None:
                    bad.append(
                        f"startup_check([{path!r}], 'warn', 'error') raised "
                        f"{type(raised).__name__}, expected it to return"
                    )
                elif not isinstance(got, list):
                    bad.append(
                        f"startup_check([{path!r}], 'warn', 'error') -> {got!r}, expected a list"
                    )
                else:
                    rule_ids = [diag.get("rule_id") for diag in got]
                    if case["want_rule"] not in rule_ids:
                        bad.append(
                            f"startup_check([{path!r}], 'warn', 'error') -> rule_ids {rule_ids}, "
                            f"expected one to be {case['want_rule']!r}"
                        )
    return bad

# scenario: _pick invokes only the thunk selected by truthiness
# inherits: hd=python/honest-parse/honest-parse.hd::_pick -> feature=specs/features/honest-parse.feature::_pick invokes only the thunk selected by truthiness
"""Verify that _pick invokes only the thunk selected by truthiness."""


def probe__pick_truthiness():
    try:
        from honest_parse import _pick
    except ImportError as exc:
        return [f"cannot import _pick: {exc}"]

    failures = []
    for flag, expected_calls in (([1], ["true"]), ([], ["false"])):
        true_answer, false_answer = {"true": 1}, {"false": 2}
        calls = []

        def when_true():
            calls.append("true")
            return true_answer

        def when_false():
            calls.append("false")
            return false_answer

        expected_answer = true_answer if flag else false_answer
        got = _pick(flag, when_true, when_false)
        if got is not expected_answer or calls != expected_calls:
            failures.append(f"_pick({flag!r}) returned {got!r} and called {calls!r}")
    return failures

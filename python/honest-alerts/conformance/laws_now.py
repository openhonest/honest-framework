# scenario: now
"""Red test for the `now` scenario of honest-alerts (specs/features/honest-alerts.feature).

Scenario clause under test:
  "it is a reader that pulls the current wall-clock time as epoch seconds UTC. It reads the clock
   and nothing else." The .hd signature is `reader fn now : () -> int side_effect reads "clock"`.

`now` is a boundary reader of the wall clock, so it is tested by calling the REAL function and
asserting the effect it reports: an integer epoch-seconds UTC time. A clock reader cannot be pinned
to one literal value, so the behaviour it fixes is a type-and-window law: the answer is an `int`, and
it names a plausible wall-clock moment -- at or after a fixed past epoch bound and before a fixed
future epoch bound, bracketing the test-boundary's own reading of `time.time()`.

The window is load-bearing against a stub. A body of `return 0` (or `return ""`, or any non-int or
out-of-window constant) fails every window/type case below; only a real read of the clock in epoch
seconds lands inside the bracket.
"""
import time

from honest_alerts import now

# Fixed epoch-seconds bounds that any real "now" taken during this test run must fall between.
# Lower: 2020-01-01T00:00:00Z. Upper: 2100-01-01T00:00:00Z. These are the literal non-trivial
# values the type-and-window law pins -- not recomputed from the function under test.
_EPOCH_2020 = 1577836800
_EPOCH_2100 = 4102444800

_CASES = [
    # The clock reader returns an int.
    {"check": "is_int", "expect": True},
    # It is at or after the fixed past bound (a plausible positive epoch-seconds time, not 0).
    {"check": "ge_2020", "expect": True},
    # It is before the fixed future bound (epoch seconds, not milliseconds or nanoseconds).
    {"check": "lt_2100", "expect": True},
    # It brackets the test boundary's own wall-clock reading (reads the real clock, UTC epoch seconds).
    {"check": "brackets_wall_clock", "expect": True},
]


def _evaluate(check):
    before = int(time.time())
    got = now()
    after = int(time.time())
    if check == "is_int":
        return isinstance(got, int) and not isinstance(got, bool)
    if check == "ge_2020":
        return isinstance(got, int) and got >= _EPOCH_2020
    if check == "lt_2100":
        return isinstance(got, int) and got < _EPOCH_2100
    if check == "brackets_wall_clock":
        return isinstance(got, int) and before <= got <= after
    return False


def probe_now():
    """`now` reads the wall clock and returns an integer epoch-seconds UTC time."""
    bad = []
    for case in _CASES:
        got = _evaluate(case["check"])
        if got != case["expect"]:
            bad.append(f"now() check {case['check']!r} -> {got}, expected {case['expect']}")
    return bad

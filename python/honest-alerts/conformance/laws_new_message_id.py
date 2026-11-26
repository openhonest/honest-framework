# scenario: new_message_id
"""Check freshness and the wall-clock timestamp of real UUID v7 IDs."""
import time
import uuid

from honest_alerts import new_message_id

# Each case: a claim the scenario fixes, and a predicate over the observed answer(s).
# "two_calls" carries two independent reads so the distinctness claim is checked on real reads.
_CASES = [
    {
        "claim": "returns a non-empty string",
        "check": lambda a, b: isinstance(a, str) and a != "",
    },
    {
        "claim": "the id is a UUID version 7",
        "check": lambda a, b: uuid.UUID(a).version == 7,
    },
    {
        "claim": "two calls return different ids (reads random, not a constant)",
        "check": lambda a, b: a != b,
    },
    {
        "claim": "UUIDs sort in the order in which they were created",
        "check": lambda a, b: uuid.UUID(a).int < uuid.UUID(b).int,
    },
]


def probe_new_message_id():
    """Check that fresh v7 IDs encode the clock and sort by creation."""
    bad = []
    before = time.time_ns() // 1_000_000
    first = new_message_id()
    # The declared timestamp has millisecond resolution. Compare IDs from different ticks.
    time.sleep(0.004)
    second = new_message_id()
    after = time.time_ns() // 1_000_000
    for case in _CASES:
        try:
            ok = case["check"](first, second)
        except (ValueError, AttributeError, TypeError) as exc:
            bad.append(
                f"new_message_id() -> ({first!r}, {second!r}), claim {case['claim']!r} "
                f"could not be evaluated: {exc!r}"
            )
            continue
        if not ok:
            bad.append(
                f"new_message_id() -> ({first!r}, {second!r}), expected: {case['claim']}"
            )
    try:
        timestamps = [uuid.UUID(value).int >> 80 for value in (first, second)]
    except (ValueError, AttributeError, TypeError) as exc:
        bad.append(f"could not read UUID v7 timestamps: {exc!r}")
        return bad
    for timestamp in timestamps:
        if not before <= timestamp <= after:
            bad.append(f"UUID v7 timestamp {timestamp} is outside the call interval [{before}, {after}]")
    return bad


if __name__ == "__main__":
    import sys

    failures = probe_new_message_id()
    if failures:
        print("RED: probe_new_message_id found failures:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("GREEN: probe_new_message_id passed")

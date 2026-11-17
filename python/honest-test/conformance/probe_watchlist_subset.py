"""honest-test conformance: the trapped non-determinism call-forms do not drift (§4.5).

honest-test carries its own call-form subset of the non-determinism watch list rather than
importing honest-check at runtime (honest-test builds before honest-check). This probe is
the guard that keeps the two from drifting: every call-form honest-test traps must be
covered by honest-check's published list, exactly or by its module wildcard (so "random.random"
is covered by "random.*"). If honest-check drops or renames an entry honest-test still traps,
this fails.

No classes, no mocks: it reads honest-test's own NONDETERMINISTIC_CALLS and honest-check's
published _HC008_WATCH as data.
"""

from honest_check.rules import _HC008_WATCH

from honest_test import NONDETERMINISTIC_CALLS


def _covered(call, published):
    module_wildcard = call.rsplit(".", 1)[0] + ".*"
    return call in published or module_wildcard in published


def probe_watchlist_subset():
    bad = []
    published = _HC008_WATCH["python"]

    if not NONDETERMINISTIC_CALLS:
        bad.append("honest-test's non-determinism watch list is empty: it traps nothing")

    for call in NONDETERMINISTIC_CALLS:
        if not _covered(call, published):
            bad.append(
                f"honest-test traps {call!r} but honest-check's published watch list does not "
                f"cover it (neither {call!r} nor its module wildcard is present): the two have drifted"
            )

    return bad


def run():
    messages = probe_watchlist_subset()
    for message in messages:
        print(f"FAIL probe_watchlist_subset: {message}")
    print(f"watchlist_subset: {'passed' if not messages else f'{len(messages)} failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())

# scenario: invoke_probe leaves an awaitable answer untouched
# inherits: hd=python/honest-test/honest-test.hd::invoke_probe -> feature=specs/features/honest-test.feature::invoke_probe leaves an awaitable answer untouched
"""Verify that invoke_probe leaves an awaitable answer untouched."""


def probe_invoke_probe_awaitable():
    try:
        from honest_test.honesty import invoke_probe
    except ImportError as exc:
        return [f"cannot import invoke_probe: {exc}"]

    awaited = []

    async def answer():
        awaited.append(True)
        return 2

    pending = answer()
    try:
        got = invoke_probe(lambda value: pending, 1)
        if got is not pending or awaited:
            return ["invoke_probe did not return the identical unawaited answer"]
    finally:
        pending.close()
    return []



def run():
    failures = probe_invoke_probe_awaitable()
    for failure in failures:
        print(f"FAIL probe_invoke_probe_awaitable: {failure}")
    return len(failures)

# scenario: invoke_probe propagates a callback exception
# inherits: hd=python/honest-test/honest-test.hd::invoke_probe -> feature=specs/features/honest-test.feature::invoke_probe propagates a callback exception
"""Verify that invoke_probe propagates a callback exception."""


def probe_invoke_probe_exception():
    try:
        from honest_test.honesty import invoke_probe
    except ImportError as exc:
        return [f"cannot import invoke_probe: {exc}"]

    expected = ValueError("callback refused argument")

    def callback(argument):
        raise expected

    try:
        invoke_probe(callback, 1)
    except ValueError as actual:
        if actual is expected:
            return []
        return ["invoke_probe replaced the callback's exception"]
    return ["invoke_probe returned instead of propagating the callback's exception"]



def run():
    failures = probe_invoke_probe_exception()
    for failure in failures:
        print(f"FAIL probe_invoke_probe_exception: {failure}")
    return len(failures)

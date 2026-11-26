# scenario: invoke_probe returns the callback answer unchanged
# inherits: hd=python/honest-test/honest-test.hd::invoke_probe -> feature=specs/features/honest-test.feature::invoke_probe returns the callback answer unchanged
"""Verify that invoke_probe returns the callback answer unchanged."""


def probe_invoke_probe_identity():
    try:
        from honest_test.honesty import invoke_probe
    except ImportError as exc:
        return [f"cannot import invoke_probe: {exc}"]

    argument = {"argument": 1}
    answer = {"answer": 2}
    received = []

    def callback(value):
        received.append(value)
        return answer

    got = invoke_probe(callback, argument)
    if got is not answer or len(received) != 1 or received[0] is not argument:
        return ["invoke_probe did not pass the original argument once and return the original answer"]
    return []



def run():
    failures = probe_invoke_probe_identity()
    for failure in failures:
        print(f"FAIL probe_invoke_probe_identity: {failure}")
    return len(failures)

# scenario: server_rejection recognizes only server-category faults
# inherits: hd=python/honest-test/honest-test.hd::server_rejection -> feature=specs/features/honest-test.feature::server_rejection recognizes only server-category faults

from honest_type import fault

from honest_test.honesty import server_rejection


def probe_server_rejection():
    cases = (
        (fault("rejected", "server rejected the answer", "server", [], {}), True),
        (fault("rejected", "client rejected the answer", "client", [], {}), False),
        ({"category": "server", "value": "widgets"}, False),
    )
    failures = []
    for answer, expected in cases:
        result = server_rejection(answer)
        if result is not expected:
            failures.append(f"{answer!r}: got {result!r}, expected {expected!r}")
    return failures


def run():
    failures = probe_server_rejection()
    for failure in failures:
        print(f"FAIL server_rejection recognizes only server-category faults: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())

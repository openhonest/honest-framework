# scenario: run_monitor_check judges the original manifest monitor record
# inherits: hd=python/honest-test/honest-test.hd::run_monitor_check -> feature=specs/features/honest-test.feature::run_monitor_check judges the original manifest monitor record

from honest_type import link

from honest_test.honesty import run_monitor_check


@link(boundary=False)
def _watched(manifest):
    return manifest


def probe_run_monitor_check():
    calls = []
    original = {"name": "widgets"}

    def monitor(watched, manifest):
        calls.append((watched is _watched, manifest is original))
        watched(manifest)
        return ["builtins.open"]

    result = run_monitor_check(_watched, original, monitor, "unrecognized")
    actual = (calls, [(finding["kind"], finding["code"]) for finding in result])
    expected = ([(True, True)], [("warning", "io_detected")])
    return [] if actual == expected else [f"got {actual!r}, expected {expected!r}"]


def run():
    failures = probe_run_monitor_check()
    for failure in failures:
        print(f"FAIL run_monitor_check judges the original manifest monitor record: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())

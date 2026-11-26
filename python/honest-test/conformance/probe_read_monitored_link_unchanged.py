# scenario: read_monitored_link passes the supplied link and manifest unchanged
# inherits: hd=python/honest-test/honest-test.hd::read_monitored_link -> feature=specs/features/honest-test.feature::read_monitored_link passes the supplied link and manifest unchanged

from honest_test.honesty import read_monitored_link


def probe_read_monitored_link_unchanged():
    record = ["builtins.open"]
    manifest = {"name": "widgets"}
    calls = []

    def watched(argument):
        return argument

    def monitor(link, supplied):
        calls.append((link is watched, supplied is manifest))
        link(supplied)
        return record

    answer = read_monitored_link(monitor, watched, manifest)
    actual = (calls, answer)
    expected = ([(True, True)], ["builtins.open"])
    return [] if actual == expected else [f"got {actual!r}, expected {expected!r}"]


def run():
    failures = probe_read_monitored_link_unchanged()
    for failure in failures:
        print(f"FAIL read_monitored_link passes the supplied link and manifest unchanged: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())

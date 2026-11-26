# scenario: read_monitored_link propagates monitor exceptions
# inherits: hd=python/honest-test/honest-test.hd::read_monitored_link -> feature=specs/features/honest-test.feature::read_monitored_link propagates monitor exceptions

from honest_test.honesty import read_monitored_link


def probe_read_monitored_link_exception():
    error = RuntimeError("monitor failed")

    def watched(manifest):
        return manifest

    def monitor(link, manifest):
        link(manifest)
        raise error

    try:
        read_monitored_link(monitor, watched, {"name": "widgets"})
    except RuntimeError as raised:
        return [] if raised is error else ["the original RuntimeError was replaced"]
    return ["the monitor's RuntimeError did not propagate"]


def run():
    failures = probe_read_monitored_link_exception()
    for failure in failures:
        print(f"FAIL read_monitored_link propagates monitor exceptions: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())

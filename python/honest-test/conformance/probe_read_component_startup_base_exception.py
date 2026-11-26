# scenario: read_component_startup propagates a non-Exception BaseException
# inherits: hd=python/honest-test/honest-test.hd::read_component_startup -> feature=specs/features/honest-test.feature::read_component_startup propagates a non-Exception BaseException

from honest_test.persist_components import read_component_startup


def probe_read_component_startup_base_exception():
    interruption = KeyboardInterrupt("stop loading")

    def load_component(component):
        raise interruption

    try:
        read_component_startup(load_component, {"name": "widgets", "template": "", "routes": []})
    except KeyboardInterrupt as raised:
        return [] if raised is interruption else ["the original interrupt was replaced"]
    return ["the loader's interrupt did not propagate"]


def run():
    failures = probe_read_component_startup_base_exception()
    for failure in failures:
        print(f"FAIL read_component_startup propagates a non-Exception BaseException: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())

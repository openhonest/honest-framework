# scenario: read_component_startup records whether the loader returned
# inherits: hd=python/honest-test/honest-test.hd::read_component_startup -> feature=specs/features/honest-test.feature::read_component_startup records whether the loader returned

from honest_test.persist_components import read_component_startup


def probe_read_component_startup_observed():
    calls = []
    component = {"name": "widgets", "template": "", "routes": []}

    def load_success(supplied):
        calls.append(("success", supplied is component))
        return None

    def load_failure(supplied):
        calls.append(("failure", supplied is component))
        raise RuntimeError("failed to load")

    observations = [read_component_startup(loader, component) for loader in (load_success, load_failure)]
    actual = (calls, observations)
    expected = (
        [("success", True), ("failure", True)],
        [{"name": "widgets", "loaded": True}, {"name": "widgets", "loaded": False}],
    )
    return [] if actual == expected else [f"got {actual!r}, expected {expected!r}"]


def run():
    failures = probe_read_component_startup_observed()
    for failure in failures:
        print(f"FAIL read_component_startup records whether the loader returned: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())

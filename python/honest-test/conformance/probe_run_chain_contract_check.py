# scenario: run_chain_contract_check skips upstream faults and reports downstream server rejection
# inherits: hd=python/honest-test/honest-test.hd::run_chain_contract_check -> feature=specs/features/honest-test.feature::run_chain_contract_check skips upstream faults and reports downstream server rejection

from honest_type import binding, fault, vocabulary

from honest_test.honesty import run_chain_contract_check


def probe_run_chain_contract_check():
    calls = []
    cases = vocabulary({"color": {"skip", "reject", "client", "accept"}})
    slot = binding({"color": "color"})
    upstream_answers = {
        "skip": fault("upstream_fault", "no answer", "client", [], {}),
        "reject": {"verdict": "reject"},
        "client": {"verdict": "client"},
        "accept": {"verdict": "accept"},
    }
    downstream_answers = {
        "reject": fault("downstream_server", "join failed", "server", [], {}),
        "client": fault("downstream_client", "input rejected", "client", [], {}),
        "accept": {"value": "accepted"},
    }

    def upstream(manifest):
        return upstream_answers[manifest["color"]]

    def downstream(manifest):
        calls.append(manifest)
        return downstream_answers[manifest["verdict"]]

    findings = run_chain_contract_check([upstream, downstream], cases, slot)
    actual = (
        sorted(manifest["verdict"] for manifest in calls),
        [(finding["kind"], finding["code"]) for finding in findings],
    )
    expected = (["accept", "client", "reject"], [("failure", "chain_contract")])
    return [] if actual == expected else [f"got {actual!r}, expected {expected!r}"]


def run():
    failures = probe_run_chain_contract_check()
    for failure in failures:
        print(f"FAIL run_chain_contract_check skips upstream faults and reports downstream server rejection: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())

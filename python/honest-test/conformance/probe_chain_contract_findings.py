# scenario: chain_contract_findings reports a failed join only for server rejection
# inherits: hd=python/honest-test/honest-test.hd::chain_contract_findings -> feature=specs/features/honest-test.feature::chain_contract_findings reports a failed join only for server rejection

from honest_test.honesty import chain_contract_findings


def probe_chain_contract_findings():
    actual = [
        [
            (
                finding["kind"],
                finding["code"],
                all(term in finding["message"].casefold() for term in ("downstream", "server fault")),
            )
            for finding in chain_contract_findings(rejected)
        ]
        for rejected in (True, False)
    ]
    expected = [[("failure", "chain_contract", True)], []]
    return [] if actual == expected else [f"got {actual!r}, expected {expected!r}"]


def run():
    failures = probe_chain_contract_findings()
    for failure in failures:
        print(f"FAIL chain_contract_findings reports a failed join only for server rejection: {failure}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(run())

"""Conformance fragment for the test_chain_contracts scenario (honest-test.feature).

Scenario: test_chain_contracts checks each adjacent pair of links and reports
  chain_contract on a broken join.
  Then for each adjacent pair it enumerates the input cases the upstream link
  accepts, runs the upstream link, and when that produces an ok manifest feeds it
  to the downstream link.
  And it returns a chain_contract failure Finding when the downstream link rejects
  that valid output with a server fault.
  And a client fault from the downstream link is not a contract failure — only a
  server fault indicates a broken join.
  And it returns one failure per broken join, empty when every join holds.

Cases are data; one pure probe feeds them to the real function and returns a list
of failure strings (empty when every case holds). No classes, no mocks: the links
are plain functions injected as real test inputs, each taking a manifest and
returning honest-type's real ok/err Result built with ok(), err() and fault(). The
vocab and binding are built with the real honest_type.vocabulary and
honest_type.binding, and the probe calls the real honest_test.test_chain_contracts.

A singleton Set vocabulary makes enumerate_test_cases yield exactly one input
manifest per link, so "one failure per broken join" is one failure, however the
engine counts — the join-count and the manifest-count agree at one.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from honest_type import binding, err, fault, ok, vocabulary

from honest_test import test_chain_contracts

# One Set of one member: enumerate_test_cases yields exactly one input manifest,
# so a broken join produces exactly one failure and the count is unambiguous.
_VOCAB = vocabulary({"color": {"red"}})
_BINDING = binding({"color": "color"})


def _accept(manifest):
    """A link that accepts its input and passes the manifest on as an ok Result."""
    return ok(manifest)


def _server_reject(manifest):
    """A downstream link that rejects a valid upstream output with a SERVER fault:
    a broken join, every valid output of one link must be accepted by the next."""
    return err(fault("broken_join", "rejected valid upstream output", "server", [], {}))


def _client_reject(manifest):
    """A downstream link that rejects with a CLIENT fault: not a broken join, the
    server-vs-client carve-out the scenario pins."""
    return err(fault("bad_input", "rejected as client error", "client", [], {}))


_CASES = [
    # Every join holds: both links accept the upstream ok output -> empty list.
    {
        "links": [_accept, _accept],
        "expect_failures": 0,
    },
    # One broken join: the downstream link returns a SERVER fault on a valid
    # upstream output -> exactly one chain_contract failure. This is the literal,
    # non-trivial case a `return []` stub cannot pass.
    {
        "links": [_accept, _server_reject],
        "expect_failures": 1,
    },
    # The client-fault carve-out: the downstream link returns a CLIENT fault on a
    # valid upstream output -> NOT a contract failure, empty list. The explicit
    # absence case, written out, not left to a default.
    {
        "links": [_accept, _client_reject],
        "expect_failures": 0,
    },
]


def probe_test_chain_contracts():
    """test_chain_contracts reports a chain_contract failure Finding when a downstream link rejects a valid upstream output with a server fault, treats a client fault as no violation, and is empty when every join holds."""
    bad = []
    for case in _CASES:
        findings = test_chain_contracts(case["links"], _VOCAB, _BINDING)
        if len(findings) != case["expect_failures"]:
            bad.append(
                f"test_chain_contracts({[f.__name__ for f in case['links']]}) "
                f"returned {len(findings)} finding(s), "
                f"expected {case['expect_failures']}: {findings}"
            )
            continue
        # On the broken-join case, pin the exact grade and code of the Finding.
        for finding in findings:
            if finding["code"] != "chain_contract":
                bad.append(
                    f"test_chain_contracts({[f.__name__ for f in case['links']]}) "
                    f"finding code {finding['code']!r}, expected 'chain_contract'"
                )
            if finding["kind"] != "failure":
                bad.append(
                    f"test_chain_contracts({[f.__name__ for f in case['links']]}) "
                    f"finding kind {finding['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_test_chain_contracts()
    for line in bad:
        print(line)
    print(f"probe_test_chain_contracts: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

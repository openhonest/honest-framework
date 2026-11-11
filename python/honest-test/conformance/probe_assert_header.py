"""Conformance fragment for the assert_header scenario (honest-test.feature).

Scenario: assert_header a named response header equals the asserted value
  Then it returns the empty list when the property holds.
  And it returns one header_mismatch Finding of kind failure naming the field when it does not.

Cases are data; one pure probe feeds them to the real honest_test.assert_header and returns a
list of failure strings (empty when every case holds). No classes, no mocks. The cases
cover the holding path and every violation branch the function distinguishes, so a
narrower implementation that handles only the simplest violation cannot pass.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import assert_header

_CASES = [
    {'given': {'response': {'status': 200, 'headers': {'X-Api-Version': '2'}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'name': 'X-Api-Version', 'value': '2'}, 'expect_codes': []},
    {'given': {'response': {'status': 200, 'headers': {'X-Api-Version': '2'}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'name': 'X-Api-Version', 'value': '3'}, 'expect_codes': ['header_mismatch']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'name': 'X-Api-Version', 'value': '2'}, 'expect_codes': ['header_mismatch']},
]


def probe_assert_header():
    """assert_header returns the empty list when the property holds, and one header_mismatch Finding of kind failure when it does not, across every violation branch it distinguishes."""
    bad = []
    for case in _CASES:
        got = assert_header(**case["given"])
        if not isinstance(got, list):
            bad.append(f"assert_header({case['given']}) -> {got!r}, expected a list")
            continue
        codes = [f["code"] for f in got]
        if codes != case["expect_codes"]:
            bad.append(
                f"assert_header({case['given']}) -> codes {codes}, expected {case['expect_codes']}"
            )
            continue
        for f in got:
            if f["kind"] != "failure":
                bad.append(
                    f"assert_header finding {f['code']!r} has kind {f['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_assert_header()
    for line in bad:
        print(line)
    print(f"probe_assert_header: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

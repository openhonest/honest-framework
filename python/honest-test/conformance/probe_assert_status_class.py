"""Conformance fragment for the assert_status_class scenario (honest-test.feature).

Scenario: assert_status_class the response status falls in the asserted hundred-band
  Then it returns the empty list when the property holds.
  And it returns one status_class_mismatch Finding of kind failure naming the field when it does not.

Cases are data; one pure probe feeds them to the real honest_test.assert_status_class and returns a
list of failure strings (empty when every case holds). No classes, no mocks. The cases
cover the holding path and every violation branch the function distinguishes, so a
narrower implementation that handles only the simplest violation cannot pass.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import assert_status_class

_CASES = [
    {'given': {'response': {'status': 204, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'status_class': '2xx'}, 'expect_codes': []},
    {'given': {'response': {'status': 301, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'status_class': '3xx'}, 'expect_codes': []},
    {'given': {'response': {'status': 404, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'status_class': '4xx'}, 'expect_codes': []},
    {'given': {'response': {'status': 503, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'status_class': '5xx'}, 'expect_codes': []},
    {'given': {'response': {'status': 500, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'status_class': '2xx'}, 'expect_codes': ['status_class_mismatch']},
    {'given': {'response': {'status': 204, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'status_class': '5xx'}, 'expect_codes': ['status_class_mismatch']},
]


def probe_assert_status_class():
    """assert_status_class returns the empty list when the property holds, and one status_class_mismatch Finding of kind failure when it does not, across every violation branch it distinguishes."""
    bad = []
    for case in _CASES:
        got = assert_status_class(**case["given"])
        if not isinstance(got, list):
            bad.append(f"assert_status_class({case['given']}) -> {got!r}, expected a list")
            continue
        codes = [f["code"] for f in got]
        if codes != case["expect_codes"]:
            bad.append(
                f"assert_status_class({case['given']}) -> codes {codes}, expected {case['expect_codes']}"
            )
            continue
        for f in got:
            if f["kind"] != "failure":
                bad.append(
                    f"assert_status_class finding {f['code']!r} has kind {f['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_assert_status_class()
    for line in bad:
        print(line)
    print(f"probe_assert_status_class: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

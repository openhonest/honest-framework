"""Conformance fragment for the assert_cookie_max_age scenario (honest-test.feature).

Scenario: assert_cookie_max_age a named response cookie's Max-Age equals the asserted seconds
  Then it returns the empty list when the property holds.
  And it returns one cookie_max_age_mismatch Finding of kind failure naming the field when it does not.

Cases are data; one pure probe feeds them to the real honest_test.assert_cookie_max_age and returns a
list of failure strings (empty when every case holds). No classes, no mocks. The cases
cover the holding path and every violation branch the function distinguishes, so a
narrower implementation that handles only the simplest violation cannot pass.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import assert_cookie_max_age

_CASES = [
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [{'name': 'session', 'value': 'abc', 'attributes': {'HttpOnly': '', 'Max-Age': '3600'}}], 'location': ''}, 'name': 'session', 'max_age': 3600}, 'expect_codes': []},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [{'name': 'session', 'value': 'abc', 'attributes': {'HttpOnly': '', 'Max-Age': '3600'}}], 'location': ''}, 'name': 'session', 'max_age': 60}, 'expect_codes': ['cookie_max_age_mismatch']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [{'name': 'session', 'value': 'abc', 'attributes': {'HttpOnly': ''}}], 'location': ''}, 'name': 'session', 'max_age': 3600}, 'expect_codes': ['cookie_max_age_mismatch']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'name': 'session', 'max_age': 3600}, 'expect_codes': ['cookie_max_age_mismatch']},
]


def probe_assert_cookie_max_age():
    """assert_cookie_max_age returns the empty list when the property holds, and one cookie_max_age_mismatch Finding of kind failure when it does not, across every violation branch it distinguishes."""
    bad = []
    for case in _CASES:
        got = assert_cookie_max_age(**case["given"])
        if not isinstance(got, list):
            bad.append(f"assert_cookie_max_age({case['given']}) -> {got!r}, expected a list")
            continue
        codes = [f["code"] for f in got]
        if codes != case["expect_codes"]:
            bad.append(
                f"assert_cookie_max_age({case['given']}) -> codes {codes}, expected {case['expect_codes']}"
            )
            continue
        for f in got:
            if f["kind"] != "failure":
                bad.append(
                    f"assert_cookie_max_age finding {f['code']!r} has kind {f['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_assert_cookie_max_age()
    for line in bad:
        print(line)
    print(f"probe_assert_cookie_max_age: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

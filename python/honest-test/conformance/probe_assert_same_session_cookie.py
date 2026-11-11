"""Conformance fragment for the assert_same_session_cookie scenario (honest-test.feature).

Scenario: assert_same_session_cookie two responses in a sequence share one session cookie value
  Then it returns the empty list when the property holds.
  And it returns one session_cookie_mismatch Finding of kind failure naming the field when it does not.

Cases are data; one pure probe feeds them to the real honest_test.assert_same_session_cookie and returns a
list of failure strings (empty when every case holds). No classes, no mocks. The cases
cover the holding path and every violation branch the function distinguishes, so a
narrower implementation that handles only the simplest violation cannot pass.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import assert_same_session_cookie

_CASES = [
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [{'name': 'session', 'value': 'abc', 'attributes': {}}], 'location': ''}, 'previous': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [{'name': 'session', 'value': 'abc', 'attributes': {}}], 'location': ''}}, 'expect_codes': []},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [{'name': 'session', 'value': 'abc', 'attributes': {}}], 'location': ''}, 'previous': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [{'name': 'session', 'value': 'zzz', 'attributes': {}}], 'location': ''}}, 'expect_codes': ['session_cookie_mismatch']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [{'name': 'session', 'value': 'abc', 'attributes': {}}], 'location': ''}, 'previous': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}}, 'expect_codes': ['session_cookie_mismatch']},
]


def probe_assert_same_session_cookie():
    """assert_same_session_cookie returns the empty list when the property holds, and one session_cookie_mismatch Finding of kind failure when it does not, across every violation branch it distinguishes."""
    bad = []
    for case in _CASES:
        got = assert_same_session_cookie(**case["given"])
        if not isinstance(got, list):
            bad.append(f"assert_same_session_cookie({case['given']}) -> {got!r}, expected a list")
            continue
        codes = [f["code"] for f in got]
        if codes != case["expect_codes"]:
            bad.append(
                f"assert_same_session_cookie({case['given']}) -> codes {codes}, expected {case['expect_codes']}"
            )
            continue
        for f in got:
            if f["kind"] != "failure":
                bad.append(
                    f"assert_same_session_cookie finding {f['code']!r} has kind {f['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_assert_same_session_cookie()
    for line in bad:
        print(line)
    print(f"probe_assert_same_session_cookie: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

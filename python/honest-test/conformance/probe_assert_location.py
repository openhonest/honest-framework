"""Conformance fragment for the assert_location scenario (honest-test.feature).

Scenario: assert_location the response Location equals the asserted URL
  Then it returns the empty list when the property holds.
  And it returns one location_mismatch Finding of kind failure naming the field when it does not.

Cases are data; one pure probe feeds them to the real honest_test.assert_location and returns a
list of failure strings (empty when every case holds). No classes, no mocks.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import assert_location

_CASES = [
    {"given": {'response': {'status': 302, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': '/home'}, 'url': '/home'}, "expect_codes": []},
    {"given": {'response': {'status': 302, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': '/home'}, 'url': '/away'}, "expect_codes": ['location_mismatch']},
]


def probe_assert_location():
    """assert_location returns the empty list when the property holds, and one location_mismatch Finding of kind failure naming the field when it does not."""
    bad = []
    for case in _CASES:
        got = assert_location(**case["given"])
        if not isinstance(got, list):
            bad.append(f"assert_location({case['given']}) -> {got!r}, expected a list")
            continue
        codes = [f["code"] for f in got]
        if codes != case["expect_codes"]:
            bad.append(
                f"assert_location({case['given']}) -> codes {codes}, expected {case['expect_codes']}"
            )
            continue
        for f in got:
            if f["kind"] != "failure":
                bad.append(
                    f"assert_location finding {f['code']!r} has kind {f['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_assert_location()
    for line in bad:
        print(line)
    print(f"probe_assert_location: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

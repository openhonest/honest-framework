"""Conformance fragment for the assert_no_header scenario (honest-test.feature).

Scenario: assert_no_header a named header is absent from the response
  Then it returns the empty list when the property holds.
  And it returns one header_present Finding of kind failure naming the field when it does not.

Cases are data; one pure probe feeds them to the real honest_test.assert_no_header and returns a
list of failure strings (empty when every case holds). No classes, no mocks.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import assert_no_header

_CASES = [
    {"given": {'response': {'status': 200, 'headers': {'X-Public': '1'}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'name': 'X-Debug'}, "expect_codes": []},
    {"given": {'response': {'status': 200, 'headers': {'X-Debug': 'on'}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'name': 'X-Debug'}, "expect_codes": ['header_present']},
]


def probe_assert_no_header():
    """assert_no_header returns the empty list when the property holds, and one header_present Finding of kind failure naming the field when it does not."""
    bad = []
    for case in _CASES:
        got = assert_no_header(**case["given"])
        if not isinstance(got, list):
            bad.append(f"assert_no_header({case['given']}) -> {got!r}, expected a list")
            continue
        codes = [f["code"] for f in got]
        if codes != case["expect_codes"]:
            bad.append(
                f"assert_no_header({case['given']}) -> codes {codes}, expected {case['expect_codes']}"
            )
            continue
        for f in got:
            if f["kind"] != "failure":
                bad.append(
                    f"assert_no_header finding {f['code']!r} has kind {f['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_assert_no_header()
    for line in bad:
        print(line)
    print(f"probe_assert_no_header: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

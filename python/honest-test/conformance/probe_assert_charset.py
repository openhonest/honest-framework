"""Conformance fragment for the assert_charset scenario (honest-test.feature).

Scenario: assert_charset the response character set equals the asserted one
  Then it returns the empty list when the property holds.
  And it returns one charset_mismatch Finding of kind failure naming the field when it does not.

Cases are data; one pure probe feeds them to the real honest_test.assert_charset and returns a
list of failure strings (empty when every case holds). No classes, no mocks.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import assert_charset

_CASES = [
    {"given": {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'charset': 'utf-8'}, "expect_codes": []},
    {"given": {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b'', 'cookies': [], 'location': ''}, 'charset': 'latin-1'}, "expect_codes": ['charset_mismatch']},
]


def probe_assert_charset():
    """assert_charset returns the empty list when the property holds, and one charset_mismatch Finding of kind failure naming the field when it does not."""
    bad = []
    for case in _CASES:
        got = assert_charset(**case["given"])
        if not isinstance(got, list):
            bad.append(f"assert_charset({case['given']}) -> {got!r}, expected a list")
            continue
        codes = [f["code"] for f in got]
        if codes != case["expect_codes"]:
            bad.append(
                f"assert_charset({case['given']}) -> codes {codes}, expected {case['expect_codes']}"
            )
            continue
        for f in got:
            if f["kind"] != "failure":
                bad.append(
                    f"assert_charset finding {f['code']!r} has kind {f['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_assert_charset()
    for line in bad:
        print(line)
    print(f"probe_assert_charset: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

"""Conformance fragment for the assert_body_html_selector scenario (honest-test.feature).

Scenario: assert_body_html_selector the response body is HTML containing an element the selector matches
  Then it returns the empty list when the property holds.
  And it returns one body_selector_absent Finding of kind failure naming the field when it does not.

Cases are data; one pure probe feeds them to the real honest_test.assert_body_html_selector and returns a
list of failure strings (empty when every case holds). No classes, no mocks. The cases
cover the holding path and every violation branch the function distinguishes, so a
narrower implementation that handles only the simplest violation cannot pass.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import assert_body_html_selector

_CASES = [
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b"<ul id='list'><li class='item' id='first'>x</li></ul>", 'cookies': [], 'location': ''}, 'selector': '.item'}, 'expect_codes': []},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b"<ul id='list'><li class='item' id='first'>x</li></ul>", 'cookies': [], 'location': ''}, 'selector': 'li'}, 'expect_codes': []},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b"<ul id='list'><li class='item' id='first'>x</li></ul>", 'cookies': [], 'location': ''}, 'selector': '#first'}, 'expect_codes': []},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b"<ul id='list'><li class='item' id='first'>x</li></ul>", 'cookies': [], 'location': ''}, 'selector': 'li.item'}, 'expect_codes': []},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b"<ul id='list'><li class='item' id='first'>x</li></ul>", 'cookies': [], 'location': ''}, 'selector': '.missing'}, 'expect_codes': ['body_selector_absent']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b"<ul id='list'><li class='item' id='first'>x</li></ul>", 'cookies': [], 'location': ''}, 'selector': 'span'}, 'expect_codes': ['body_selector_absent']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b"<ul id='list'><li class='item' id='first'>x</li></ul>", 'cookies': [], 'location': ''}, 'selector': '#nope'}, 'expect_codes': ['body_selector_absent']},
    {'given': {'response': {'status': 200, 'headers': {}, 'charset': 'utf-8', 'body': b"<ul id='list'><li class='item' id='first'>x</li></ul>", 'cookies': [], 'location': ''}, 'selector': 'div.item'}, 'expect_codes': ['body_selector_absent']},
]


def probe_assert_body_html_selector():
    """assert_body_html_selector returns the empty list when the property holds, and one body_selector_absent Finding of kind failure when it does not, across every violation branch it distinguishes."""
    bad = []
    for case in _CASES:
        got = assert_body_html_selector(**case["given"])
        if not isinstance(got, list):
            bad.append(f"assert_body_html_selector({case['given']}) -> {got!r}, expected a list")
            continue
        codes = [f["code"] for f in got]
        if codes != case["expect_codes"]:
            bad.append(
                f"assert_body_html_selector({case['given']}) -> codes {codes}, expected {case['expect_codes']}"
            )
            continue
        for f in got:
            if f["kind"] != "failure":
                bad.append(
                    f"assert_body_html_selector finding {f['code']!r} has kind {f['kind']!r}, expected 'failure'"
                )
    return bad


def run():
    bad = probe_assert_body_html_selector()
    for line in bad:
        print(line)
    print(f"probe_assert_body_html_selector: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

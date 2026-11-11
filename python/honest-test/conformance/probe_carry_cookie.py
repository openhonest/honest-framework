"""Conformance fragment for the carry_cookie scenario (honest-test.feature).

Scenario: carry_cookie carries the previous response's Set-Cookie into the next request's Cookie
  Then it returns a new Request whose Cookie carries the session value the previous response set.

Cases are data; one pure probe feeds them to the real honest_test.carry_cookie and returns a
list of failure strings (empty when every case holds). No classes, no mocks.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import carry_cookie

_PREVIOUS = {
    "status": 200,
    "headers": {},
    "charset": "utf-8",
    "body": b"",
    "cookies": [{"name": "session", "value": "abc", "attributes": {}}],
    "location": "",
}
_REQUEST = {"headers": {}, "cookies": {}, "body": "", "content_type": ""}


def probe_carry_cookie():
    """carry_cookie returns a new Request whose cookies carry the previous response's session value, leaving the Request it was handed unchanged."""
    bad = []
    request = dict(_REQUEST)
    got = carry_cookie(_PREVIOUS, request)
    if not isinstance(got, dict):
        bad.append(f"carry_cookie -> {got!r}, expected a Request record")
        return bad
    if got.get("cookies", {}).get("session") != "abc":
        bad.append(f"carry_cookie did not carry session=abc; got cookies {got.get('cookies')!r}")
    if request != _REQUEST:
        bad.append(f"carry_cookie mutated the Request it was handed: {request!r}")
    return bad


def run():
    bad = probe_carry_cookie()
    for line in bad:
        print(line)
    print(f"probe_carry_cookie: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

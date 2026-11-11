"""Conformance fragment for the with_cookie scenario (honest-test.feature).

Scenario: with_cookie adds a cookie to a request under construction
  Then it returns a new Request with cookies set, and the original Request unchanged.

Cases are data; one pure probe feeds them to the real honest_test.with_cookie and returns a
list of failure strings (empty when every case holds). No classes, no mocks.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import with_cookie

_EMPTY = {"headers": {}, "cookies": {}, "body": "", "content_type": ""}


def probe_with_cookie():
    """with_cookie returns a new Request with cookies['session'] set to 'abc', leaving the Request it was handed unchanged."""
    bad = []
    request = dict(_EMPTY)
    got = with_cookie(request, name='session', value='abc')
    if not isinstance(got, dict):
        bad.append(f"with_cookie -> {got!r}, expected a Request record")
        return bad
    if got.get('cookies', {}).get('session') != 'abc':
        bad.append(f"with_cookie did not set cookies['session'] to 'abc'; got {got.get('cookies')!r}")
    if request != _EMPTY:
        bad.append(f"with_cookie mutated the Request it was handed: {request!r}")
    return bad


def run():
    bad = probe_with_cookie()
    for line in bad:
        print(line)
    print(f"probe_with_cookie: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

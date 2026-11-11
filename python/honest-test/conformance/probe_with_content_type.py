"""Conformance fragment for the with_content_type scenario (honest-test.feature).

Scenario: with_content_type sets the Content-Type of a request under construction
  Then it returns a new Request with content_type set, and the original Request unchanged.

Cases are data; one pure probe feeds them to the real honest_test.with_content_type and returns a
list of failure strings (empty when every case holds). No classes, no mocks.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import with_content_type

_EMPTY = {"headers": {}, "cookies": {}, "body": "", "content_type": ""}


def probe_with_content_type():
    """with_content_type returns a new Request with content_type set to 'application/json', leaving the Request it was handed unchanged."""
    bad = []
    request = dict(_EMPTY)
    got = with_content_type(request, mime_type='application/json')
    if not isinstance(got, dict):
        bad.append(f"with_content_type -> {got!r}, expected a Request record")
        return bad
    if got.get('content_type') != 'application/json':
        bad.append(f"with_content_type did not set content_type to 'application/json'; got {got.get('content_type')!r}")
    if request != _EMPTY:
        bad.append(f"with_content_type mutated the Request it was handed: {request!r}")
    return bad


def run():
    bad = probe_with_content_type()
    for line in bad:
        print(line)
    print(f"probe_with_content_type: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

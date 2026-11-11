"""Conformance fragment for the with_body scenario (honest-test.feature).

Scenario: with_body sets the body of a request under construction
  Then it returns a new Request with body set, and the original Request unchanged.

Cases are data; one pure probe feeds them to the real honest_test.with_body and returns a
list of failure strings (empty when every case holds). No classes, no mocks.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import with_body

_EMPTY = {"headers": {}, "cookies": {}, "body": "", "content_type": ""}


def probe_with_body():
    """with_body returns a new Request with body set to 'payload', leaving the Request it was handed unchanged."""
    bad = []
    request = dict(_EMPTY)
    got = with_body(request, content='payload')
    if not isinstance(got, dict):
        bad.append(f"with_body -> {got!r}, expected a Request record")
        return bad
    if got.get('body') != 'payload':
        bad.append(f"with_body did not set body to 'payload'; got {got.get('body')!r}")
    if request != _EMPTY:
        bad.append(f"with_body mutated the Request it was handed: {request!r}")
    return bad


def run():
    bad = probe_with_body()
    for line in bad:
        print(line)
    print(f"probe_with_body: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

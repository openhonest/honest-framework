"""Conformance fragment for the with_header scenario (honest-test.feature).

Scenario: with_header adds a header to a request under construction
  Then it returns a new Request with headers set, and the original Request unchanged.

Cases are data; one pure probe feeds them to the real honest_test.with_header and returns a
list of failure strings (empty when every case holds). No classes, no mocks.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import with_header

_EMPTY = {"headers": {}, "cookies": {}, "body": "", "content_type": ""}


def probe_with_header():
    """with_header returns a new Request with headers['X-Trace'] set to 'abc123', leaving the Request it was handed unchanged."""
    bad = []
    request = dict(_EMPTY)
    got = with_header(request, name='X-Trace', value='abc123')
    if not isinstance(got, dict):
        bad.append(f"with_header -> {got!r}, expected a Request record")
        return bad
    if got.get('headers', {}).get('X-Trace') != 'abc123':
        bad.append(f"with_header did not set headers['X-Trace'] to 'abc123'; got {got.get('headers')!r}")
    if request != _EMPTY:
        bad.append(f"with_header mutated the Request it was handed: {request!r}")
    return bad


def run():
    bad = probe_with_header()
    for line in bad:
        print(line)
    print(f"probe_with_header: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

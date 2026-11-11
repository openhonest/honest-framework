"""Conformance fragment for the reuse_session scenario (honest-test.feature).

Scenario: reuse_session reuses the session from the previous response in the next request
  Then it returns a new Request carrying the session cookie value from the previous response.

Cases are data; one pure probe feeds them to the real honest_test.reuse_session and returns a
list of failure strings (empty when every case holds). No classes, no mocks.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import reuse_session

_PREVIOUS = {
    "status": 200,
    "headers": {},
    "charset": "utf-8",
    "body": b"",
    "cookies": [{"name": "session", "value": "s3cr3t", "attributes": {}}],
    "location": "",
}
_REQUEST = {"headers": {}, "cookies": {}, "body": "", "content_type": ""}


def probe_reuse_session():
    """reuse_session returns a new Request carrying the previous response's session value, leaving the Request it was handed unchanged."""
    bad = []
    request = dict(_REQUEST)
    got = reuse_session(_PREVIOUS, request)
    if not isinstance(got, dict):
        bad.append(f"reuse_session -> {got!r}, expected a Request record")
        return bad
    if got.get("cookies", {}).get("session") != "s3cr3t":
        bad.append(f"reuse_session did not reuse session=s3cr3t; got cookies {got.get('cookies')!r}")
    if request != _REQUEST:
        bad.append(f"reuse_session mutated the Request it was handed: {request!r}")
    return bad


def run():
    bad = probe_reuse_session()
    for line in bad:
        print(line)
    print(f"probe_reuse_session: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

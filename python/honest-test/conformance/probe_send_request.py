"""Conformance fragment for the send_request scenario (honest-test.feature).

Scenario: send_request sends an accumulated request through the injected client and records the response
  Then it calls the injected client with the method, path and request, and returns the neutral Response the client filled.

Cases are data; one pure probe feeds them to the real honest_test.send_request and returns a
list of failure strings (empty when every case holds). No classes, no mocks.

Its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import send_request

# The injected client: a real recording callable, not a mock. It records the call it
# received and returns a canned neutral Response. honest-test does no I/O of its own;
# the client is the boundary, injected as a Callable exactly as evaluate_case injects
# the functions under test.
_CANNED = {
    "status": 201,
    "headers": {"Content-Type": "application/json"},
    "charset": "utf-8",
    "body": b'{"id": 1}',
    "cookies": [],
    "location": "/users/1",
}
_REQUEST = {"headers": {}, "cookies": {}, "body": "name=ada", "content_type": "application/x-www-form-urlencoded"}


def probe_send_request():
    """send_request calls the injected client with the method, path and request, and returns the Response the client produced, doing no I/O of its own."""
    bad = []
    seen = []

    def client(method, path, request):
        seen.append((method, path, request))
        return _CANNED

    got = send_request(client, "POST", "/users", _REQUEST)
    if got != _CANNED:
        bad.append(f"send_request -> {got!r}, expected the Response the client returned, {_CANNED!r}")
    if seen != [("POST", "/users", _REQUEST)]:
        bad.append(f"send_request called the client as {seen!r}, expected one call ('POST', '/users', request)")
    return bad


def run():
    bad = probe_send_request()
    for line in bad:
        print(line)
    print(f"probe_send_request: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

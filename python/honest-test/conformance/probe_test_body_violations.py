"""honest-test conformance: test_body_violations, the test-body honesty verdict.

test_body_violations reads a test module's source and returns one rejection
Finding per statement that rebinds a call target at runtime — a monkeypatch
fixture, a mock.patch, a setattr on an imported symbol, or an attribute-assignment
rebind — each carrying the site's location; an honest body returns the empty list
(.hd test_body_violations note; spec §4.8; feature "test_body_violations returns
one rejection per runtime rebinding").

No classes, no mocks. Each source is a real string; the function called is the
real honest_test.test_body_violations. A Finding is a dict carrying kind, code,
message and location (.hd type Finding).
"""

from honest_test import test_body_violations


_HONEST = '''
def test_double():
    assert double(2) == 4
'''

_MONKEYPATCH = '''
def test_run(monkeypatch):
    monkeypatch.setattr(mymod, "helper", lambda: 1)
    assert mymod.run() == 1
'''

_MOCK_PATCH = '''
from unittest import mock

def test_run():
    with mock.patch("mymod.helper") as patched:
        patched.return_value = 1
        assert mymod.run() == 1
'''

_SETATTR = '''
import mymod

def test_run():
    setattr(mymod, "helper", lambda: 1)
    assert mymod.run() == 1
'''

_ATTR_REBIND = '''
import mymod

def test_run():
    mymod.helper = lambda: 1
    assert mymod.run() == 1
'''

_DISHONEST = {
    "monkeypatch fixture": _MONKEYPATCH,
    "mock.patch": _MOCK_PATCH,
    "setattr on an import": _SETATTR,
    "attribute-assignment rebind": _ATTR_REBIND,
}


def _rejections(findings):
    return [
        finding
        for finding in findings
        if isinstance(finding, dict)
        and finding.get("code") == "test_body_dishonest"
        and finding.get("kind") == "rejection"
    ]


def probe_test_body_violations():
    """An honest pure test body returns no findings; each of the four runtime
    rebindings returns at least one test_body_dishonest rejection whose kind is
    rejection and whose location names a source site."""
    bad = []

    honest = test_body_violations(_HONEST)
    if not isinstance(honest, list):
        bad.append(f"test_body_violations should return a list, got {honest!r}")
    elif honest != []:
        bad.append(f"an honest pure test body should return no findings, got {honest}")

    for label, source in _DISHONEST.items():
        findings = test_body_violations(source)
        if not isinstance(findings, list):
            bad.append(f"{label}: test_body_violations should return a list, got {findings!r}")
            continue
        rejections = _rejections(findings)
        if not rejections:
            bad.append(f"{label}: should return a test_body_dishonest rejection, got {findings}")
            continue
        for rejection in rejections:
            location = rejection.get("location")
            if not isinstance(location, str) or not location:
                bad.append(f"{label}: a rejection should carry the rebinding site's location, got {rejection}")
            if not rejection.get("message"):
                bad.append(f"{label}: a rejection should carry a message naming the fix, got {rejection}")

    return bad


def run():
    messages = probe_test_body_violations()
    for message in messages:
        print(f"FAIL probe_test_body_violations: {message}")
    print(f"probe_test_body_violations: {'PASS' if not messages else str(len(messages)) + ' failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())

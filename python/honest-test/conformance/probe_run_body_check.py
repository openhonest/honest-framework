"""honest-test conformance: run_body_check, the collection-time orchestrator.

run_body_check takes one collected test module's source, runs test_body_violations
over it, and returns the rejections for the collection door to act on — empty when
the test body is honest (.hd run_body_check note; feature "run_body_check runs the
test-body verdict over one collected module's source"). This probe drives it on an
honest body and on a monkeypatch body and checks the verdict it passes through.

No classes, no mocks. Each source is a real string; the function called is the real
honest_test.run_body_check. A Finding is a dict carrying kind, code, message and
location (.hd type Finding).
"""

from honest_test import run_body_check


_HONEST = '''
def test_double():
    assert double(2) == 4
'''

_DISHONEST = '''
def test_run(monkeypatch):
    monkeypatch.setattr(mymod, "helper", lambda: 1)
    assert mymod.run() == 1
'''


def probe_run_body_check():
    """An honest body yields no rejections; a body that rebinds a call target at
    runtime yields a test_body_dishonest rejection, passed through from the pure
    verdict unchanged."""
    bad = []

    honest = run_body_check(_HONEST)
    if not isinstance(honest, list):
        bad.append(f"run_body_check should return a list, got {honest!r}")
    elif honest != []:
        bad.append(f"an honest test body should collect clean, got {honest}")

    findings = run_body_check(_DISHONEST)
    if not isinstance(findings, list):
        bad.append(f"run_body_check should return a list, got {findings!r}")
    else:
        rejected = any(
            isinstance(finding, dict)
            and finding.get("code") == "test_body_dishonest"
            and finding.get("kind") == "rejection"
            for finding in findings
        )
        if not rejected:
            bad.append(f"a monkeypatch test body should yield a test_body_dishonest rejection, got {findings}")

    return bad


def run():
    messages = probe_run_body_check()
    for message in messages:
        print(f"FAIL probe_run_body_check: {message}")
    print(f"probe_run_body_check: {'PASS' if not messages else str(len(messages)) + ' failed'}")
    return 0 if not messages else 1


if __name__ == "__main__":
    raise SystemExit(run())

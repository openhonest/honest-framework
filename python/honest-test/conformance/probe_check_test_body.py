"""Conformance fragment for the check_test_body scenario (honest-test.feature).

Scenario: check_test_body the pytest collection hook reads one test module and
refuses a dishonest body.
  Then it reads the collected module's source through the injected collector,
  whose path read_text returns the source, and touches nothing else on the
  collector.
  And it hands that source to run_body_check for the pure verdict and gets back
  the list of rejection Findings.
  And it returns that list, empty when the module collected clean.
  And it raises collection_failure when the list is non-empty, naming each
  rebinding site, so a test body that rebinds a call target at runtime does not
  run.

Cases are data; one pure probe feeds them to the real honest_test.check_test_body
and returns a list of failure strings (empty when every case holds). The collector
is a real injected boundary input, not a mock: per the .hd and section 4.8 the read
is substituted by passing a stand-in collector carrying a path whose read_text
returns the source — not by patching. The stand-in is built below from
types.SimpleNamespace so `collector.path.read_text()` yields the module source.

This is its own fragment file so the other scenarios' fragments never collide with
it. run_conformance.py / laws_htest.py are untouched.
"""

from types import SimpleNamespace

from honest_test import check_test_body

# An honest test module: a pure assertion, no runtime rebinding of any call target.
_HONEST_SOURCE = """\
def test_add_two_numbers():
    assert add(2, 3) == 5
"""

# A dishonest test module: a monkeypatch fixture rebinds a call target at runtime,
# the exact construct section 4.8 refuses — so check_test_body must raise.
_DISHONEST_SOURCE = """\
def test_run_fetches(monkeypatch):
    monkeypatch.setattr(service, "fetch", lambda: 42)
    assert service.run() == 42
"""

_CASES = [
    # The clean path: an honest body collects, check_test_body returns [] and does
    # not raise. This is the explicit absence case (empty rejection list).
    {
        "source": _HONEST_SOURCE,
        "expect_raise": False,
        "expect_return": [],
    },
    # The refusal path: a dishonest body raises collection_failure, and the raise
    # carries code test_body_dishonest naming the rebinding site. A stub that only
    # `return []` fails this case because it never raises.
    {
        "source": _DISHONEST_SOURCE,
        "expect_raise": True,
        "expect_code": "test_body_dishonest",
    },
]


def _collector(source):
    """A stand-in pytest collector whose path.read_text() returns the source."""
    return SimpleNamespace(path=SimpleNamespace(read_text=lambda: source))


def _raise_evidence(exc):
    """Every string the raised exception exposes, for the code-presence check."""
    parts = [repr(exc), str(exc)]
    parts.extend(str(arg) for arg in getattr(exc, "args", ()))
    for attr in ("findings", "rejections", "faults", "code", "codes"):
        value = getattr(exc, attr, None)
        if value is not None:
            parts.append(repr(value))
    return " ".join(parts)


def probe_check_test_body():
    """check_test_body returns [] for an honest body and raises collection_failure, carrying code test_body_dishonest, for a body that rebinds a call target at runtime."""
    bad = []
    for case in _CASES:
        collector = _collector(case["source"])
        if case["expect_raise"]:
            try:
                got = check_test_body(collector)
            except Exception as exc:
                evidence = _raise_evidence(exc)
                if case["expect_code"] not in evidence:
                    bad.append(
                        f"check_test_body raised on a dishonest body but the raise did "
                        f"not carry code {case['expect_code']!r}: {evidence}"
                    )
            else:
                bad.append(
                    f"check_test_body returned {got!r} on a dishonest body, "
                    f"expected it to raise collection_failure"
                )
        else:
            try:
                got = check_test_body(collector)
            except Exception as exc:
                bad.append(
                    f"check_test_body raised {exc!r} on an honest body, "
                    f"expected it to return {case['expect_return']!r}"
                )
            else:
                if got != case["expect_return"]:
                    bad.append(
                        f"check_test_body(honest body) -> {got!r}, "
                        f"expected {case['expect_return']!r}"
                    )
    return bad


def run():
    bad = probe_check_test_body()
    for line in bad:
        print(line)
    print(f"probe_check_test_body: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

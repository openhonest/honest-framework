# scenario: check_test_body refuses a test body that rebinds a call target
# inherits: hd=python/honest-test/honest-test.hd::check_test_body -> feature=specs/features/honest-test.feature::check_test_body refuses a test body that rebinds a call target
"""Probe for honest-test.check_test_body — the pytest collection hook (.hd, section 4.8).

check_test_body reads the collected test module's source through the injected
collector, hands it to run_body_check for the pure verdict, and returns the list of
rejections. It returns the empty list when the body is honest and raises
collection_failure when the list is non-empty, so a test body that rebinds a call
target at runtime does not run. The collector is a real stand-in: an object carrying
a `path` whose read_text returns the source, pointed at a real temporary file (spec
section 4.8).
"""

import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from honest_test import check_test_body, test_body_violations


def _collector_over(source):
    """A stand-in collector carrying a real path whose read_text returns the source.
    It is a real object pointed at a real file, not a mock: the injected-collector
    pattern the spec names (section 4.8)."""
    fd, path = tempfile.mkstemp(suffix="_test.py")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(source)
    return SimpleNamespace(path=Path(path)), path


def probe_check_test_body():
    """check_test_body returns [] for an honest test body and raises on a body that
    rebinds a call target at runtime."""
    bad = []

    honest = (
        "def test_sum():\n"
        "    assert add(2, 3) == 5\n"
    )
    collector, path = _collector_over(honest)
    try:
        got = check_test_body(collector)
        if not isinstance(got, list):
            bad.append(f"check_test_body returned {type(got).__name__} for an honest body, expected a list")
        elif got != []:
            bad.append(f"check_test_body returned {got!r} for an honest body, expected []")
    except Exception as e:  # noqa: BLE001
        bad.append(f"check_test_body raised on an honest test body, expected []: {e!r}")
    finally:
        os.unlink(path)

    # A monkeypatch rebind is a dishonest body: collection must fail.
    dishonest = (
        "def test_patched(monkeypatch):\n"
        '    monkeypatch.setattr(service, "fetch", lambda: 1)\n'
        "    assert service.run() == 1\n"
    )
    collector, path = _collector_over(dishonest)
    try:
        got = check_test_body(collector)
        bad.append(f"check_test_body returned {got!r} for a monkeypatch body, expected it to raise collection_failure")
    except Exception as error:
        if "collection_failure" not in str(error):
            bad.append(f"expected the declared collection_failure, got {error!r}")
    finally:
        os.unlink(path)

    # A mock.patch rebind is likewise dishonest: collection must fail.
    mocked = (
        "from unittest import mock\n"
        "def test_mocked():\n"
        '    with mock.patch("service.fetch", return_value=1):\n'
        "        assert service.run() == 1\n"
    )
    collector, path = _collector_over(mocked)
    try:
        got = check_test_body(collector)
        bad.append(f"check_test_body returned {got!r} for a mock.patch body, expected it to raise collection_failure")
    except Exception as error:
        if "collection_failure" not in str(error):
            bad.append(f"expected the declared collection_failure, got {error!r}")
    finally:
        os.unlink(path)

    two_sites = (
        "def test_rebound_twice(monkeypatch):\n"
        '    monkeypatch.setattr(service, "fetch", lambda: 1)\n'
        "\n"
        '    monkeypatch.setattr(service, "fetch", lambda: 1)\n'
    )
    verdict = test_body_violations(two_sites)
    locations = {finding["location"] for finding in verdict}
    if len(verdict) != 2 or len(locations) != 2 or "" in locations:
        bad.append(f"expected two distinct rebinding sites from the source verdict, got {verdict!r}")
    collector, path = _collector_over(two_sites)
    try:
        got = check_test_body(collector)
        bad.append(f"check_test_body returned {got!r} for two rebindings, expected collection_failure")
    except Exception as error:
        reported = str(error)
        missing = sorted(site for site in locations if site not in reported)
        if "collection_failure" not in reported or missing:
            bad.append(f"expected collection_failure identifying both rebinding sites, missing {missing!r}: {reported!r}")
    finally:
        os.unlink(path)

    return bad


def run():
    failures = probe_check_test_body()
    for message in failures:
        print(f"FAIL check_test_body: {message}")
    print(f"check_test_body probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)

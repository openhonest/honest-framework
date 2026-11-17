"""honest-test conformance: coverage_ratio — one dimension's arithmetic.

coverage_ratio(exercised, total) returns a Coverage {total, exercised, pct}:
it carries exercised and total back unchanged and computes their whole-number
percentage (spec §9.1). This probe asserts the arithmetic on known inputs whose
percentage is a whole number either way it rounds.

No classes, no mocks. It calls the real honest_test.coverage_ratio and reads the
returned record by shape.
"""

from honest_test import coverage_ratio


def _check(exercised, total, want_pct):
    """One known ratio: the record must carry exercised and total unchanged and
    report the whole-number percentage."""
    bad = []
    got = coverage_ratio(exercised, total)
    if not isinstance(got, dict):
        return [f"coverage_ratio({exercised}, {total}) -> {got!r}, expected a Coverage dict"]
    if got.get("exercised") != exercised:
        bad.append(f"coverage_ratio({exercised}, {total}).exercised = {got.get('exercised')!r}, expected {exercised}")
    if got.get("total") != total:
        bad.append(f"coverage_ratio({exercised}, {total}).total = {got.get('total')!r}, expected {total}")
    if got.get("pct") != want_pct:
        bad.append(f"coverage_ratio({exercised}, {total}).pct = {got.get('pct')!r}, expected {want_pct}")
    return bad


def probe_coverage_ratio():
    bad = []
    # Each percentage is a whole number under floor and round alike.
    bad += _check(5, 5, 100)
    bad += _check(3, 4, 75)
    bad += _check(0, 4, 0)
    bad += _check(1, 4, 25)
    bad += _check(1, 3, 33)
    return bad


def run():
    messages = probe_coverage_ratio()
    if messages:
        print(f"FAIL HTEST-probe [coverage_ratio]: {messages}")
    print(f"coverage_ratio: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())

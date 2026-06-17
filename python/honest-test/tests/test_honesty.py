"""honest-test §4 honesty harness: purity, mutation, idempotency."""
from honest_test.honesty import (
    detect_mutation,
    honesty_suite,
    verify_idempotency,
    verify_purity,
)


def _pure(m):
    return {"ok": {**m, "y": 2}}


def _mutating(m):
    m["x"] = 1
    return {"ok": m}


def _impure(m, _counter=[0]):
    _counter[0] += 1
    return {"ok": {**m, "n": _counter[0]}}


def _boundary(m, _counter=[0]):
    _counter[0] += 1
    return {"ok": {**m, "n": _counter[0]}}


_boundary._link_meta = {"boundary": True}


def test_pure_link_passes_all():
    m = {"a": 1}
    assert verify_purity(_pure, m) is None
    assert detect_mutation(_pure, m) is None
    assert verify_idempotency(_pure, m) is None
    assert honesty_suite(_pure, [{"a": 1}, {"a": 2}]) == []


def test_mutation_detected():
    f = detect_mutation(_mutating, {"a": 1})
    assert f is not None and f["kind"] == "manifest_mutated"


def test_impurity_detected():
    f = verify_purity(_impure, {"a": 1})
    assert f is not None and f["kind"] == "non_deterministic"


def test_idempotency_failure_detected():
    f = verify_idempotency(_impure, {"a": 1})
    assert f is not None and f["kind"] == "not_idempotent"


def test_boundary_link_exempt_from_purity():
    # boundary link returns different results but is exempt.
    assert verify_purity(_boundary, {"a": 1}) is None
    assert verify_idempotency(_boundary, {"a": 1}) is None


def test_errored_link_reported_as_data():
    def boom(m):
        raise ValueError("kaboom")
    f = verify_purity(boom, {"a": 1})
    assert f is not None and f["kind"] == "errored"

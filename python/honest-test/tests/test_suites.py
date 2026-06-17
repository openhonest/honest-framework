"""Tests for each suite."""
from honest_test import (
    adversarial_neighbors,
    classification_suite,
    enumerate_set_members,
    verify_idempotency,
    verify_mutation,
    verify_purity,
)


def test_enumerate_empty():
    assert list(enumerate_set_members({})) == [{}]


def test_enumerate_single_set():
    assert list(enumerate_set_members({"kind": ["a", "b"]})) == [
        {"kind": "a"}, {"kind": "b"},
    ]


def test_enumerate_cartesian():
    out = list(enumerate_set_members({"x": ["1", "2"], "y": ["a", "b"]}))
    assert len(out) == 4


# --- purity ---------------------------------------------------------------


def test_verify_purity_pure_fn_passes():
    def add(a, b): return int(a) + int(b)
    suite = verify_purity(add, {"a": ["1", "2"], "b": ["3", "4"]})
    assert suite["total_failed"] == 0


def test_verify_purity_catches_impurity():
    counter = {"n": 0}
    def impure(x):
        counter["n"] += 1
        return counter["n"]
    suite = verify_purity(impure, {"x": ["1"]}, runs=2)
    assert suite["total_failed"] >= 1


# --- mutation -------------------------------------------------------------


def test_verify_mutation_pure_fn_passes():
    def pure(lst): return lst + [1]
    suite = verify_mutation(pure, {"lst": [[1, 2], [3, 4]]})
    assert suite["total_failed"] == 0


def test_verify_mutation_catches_mutation():
    def mutating(lst):
        lst.append(99)
        return lst
    suite = verify_mutation(mutating, {"lst": [[1, 2], [3, 4]]})
    assert suite["total_failed"] == 2


# --- idempotency ----------------------------------------------------------


def test_verify_idempotency_passes_for_sorted():
    def normalize(s): return "".join(sorted(s))
    suite = verify_idempotency(normalize, {"s": ["abc", "cba", "bca"]})
    assert suite["total_failed"] == 0


def test_verify_idempotency_catches_non_idempotent():
    def doubler(n): return n + 1
    suite = verify_idempotency(doubler, {"n": [0, 1, 2]})
    assert suite["total_failed"] == 3


# --- classification -------------------------------------------------------


def test_classification_suite_all_ok():
    def classify(m):
        return {"type": "known", "value": m, "slot": ""}
    suite = classification_suite(classify, ["a", "b", "c"])
    assert suite["total_failed"] == 0


def test_classification_suite_flags_rejection():
    def half(m):
        if m == "good":
            return {"type": "ok", "value": m, "slot": ""}
        return {"reason": "unknown", "value": m, "attempted": []}
    suite = classification_suite(half, ["good", "bad"])
    assert suite["total_failed"] == 1


# --- adversarial ----------------------------------------------------------


def test_adversarial_neighbors_generated():
    neighbors = adversarial_neighbors("hello")
    # Must include whitespace padding and case change
    assert " hello" in neighbors
    assert "hello " in neighbors
    assert "HELLO" in neighbors
    # Must not include the original
    assert "hello" not in neighbors


def test_adversarial_neighbors_empty_on_empty():
    assert adversarial_neighbors("") == []

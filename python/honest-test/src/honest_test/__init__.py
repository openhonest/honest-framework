"""honest-test — exhaustive verification against bounded vocabularies.

Runs a pure function across every point in its declared test space (the
Cartesian product of its vocabulary's sets) and verifies properties that
are invariant across all inputs.

- `verify_purity`:       same inputs → same outputs across repeated calls.
- `verify_mutation`:     the function does not mutate its inputs.
- `verify_idempotency`:  `f(f(x)) == f(x)` where applicable.
- `classification_suite`: every set member is classified without rejection.
- `adversarial_neighbors`: near-miss inputs (typos, whitespace) are rejected.
"""
from honest_test.enumerate import enumerate_set_members
from honest_test.suites import (
    adversarial_neighbors,
    classification_suite,
    verify_idempotency,
    verify_mutation,
    verify_purity,
)
from honest_test.types import (
    Coverage,
    TestCase,
    TestResult,
    TestSuite,
)

__all__ = [
    "Coverage",
    "TestCase",
    "TestResult",
    "TestSuite",
    "adversarial_neighbors",
    "classification_suite",
    "enumerate_set_members",
    "verify_idempotency",
    "verify_mutation",
    "verify_purity",
]

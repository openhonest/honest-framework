"""Test suites: purity, mutation, idempotency, classification, adversarial."""
from __future__ import annotations

import copy
from typing import Any, Callable

from honest_test.enumerate import enumerate_set_members
from honest_test.types import TestResult, TestSuite


# --- verify_purity ---------------------------------------------------------


def verify_purity(
    fn: Callable[..., Any],
    vocab: dict[str, list[str]],
    runs: int = 3,
) -> TestSuite:
    """For every input in the vocabulary's Cartesian product, call fn `runs`
    times and verify the result is identical across calls.
    """
    results: list[TestResult] = []
    for inputs in enumerate_set_members(vocab):
        outputs = [fn(**inputs) for _ in range(runs)]
        if all(o == outputs[0] for o in outputs):
            results.append(TestResult(
                name=f"purity[{inputs}]",
                status="ok",
                detail="",
            ))
        else:
            results.append(TestResult(
                name=f"purity[{inputs}]",
                status="failed",
                detail=f"outputs differ across runs: {outputs}",
            ))
    return _summarise("verify_purity", results)


# --- verify_mutation -------------------------------------------------------


def verify_mutation(
    fn: Callable[..., Any],
    vocab: dict[str, list[Any]],
) -> TestSuite:
    """Call fn with copies of the inputs; verify the originals are unchanged."""
    results: list[TestResult] = []
    for inputs in enumerate_set_members(vocab):
        originals = {k: copy.deepcopy(v) for k, v in inputs.items()}
        try:
            fn(**inputs)
        except Exception as exc:
            results.append(TestResult(
                name=f"mutation[{inputs}]",
                status="errored",
                detail=f"{type(exc).__name__}: {exc}",
            ))
            continue
        # Compare post-call inputs to pre-call originals.
        mutated = [k for k, v in inputs.items() if v != originals[k]]
        if mutated:
            results.append(TestResult(
                name=f"mutation[{inputs}]",
                status="failed",
                detail=f"inputs mutated: {mutated}",
            ))
        else:
            results.append(TestResult(
                name=f"mutation[{inputs}]",
                status="ok",
                detail="",
            ))
    return _summarise("verify_mutation", results)


# --- verify_idempotency ----------------------------------------------------


def verify_idempotency(
    fn: Callable[[Any], Any],
    vocab: dict[str, list[Any]],
) -> TestSuite:
    """Verify `fn(fn(x)) == fn(x)` for every enumerated x.

    Requires fn to be unary (one argument). Works best on
    normaliser-shaped functions.
    """
    results: list[TestResult] = []
    for inputs in enumerate_set_members(vocab):
        if len(inputs) != 1:
            results.append(TestResult(
                name=f"idempotency[{inputs}]",
                status="errored",
                detail="verify_idempotency requires a single-argument fn; vocab had multiple sets",
            ))
            continue
        x = next(iter(inputs.values()))
        try:
            once = fn(x)
            twice = fn(once)
        except Exception as exc:
            results.append(TestResult(
                name=f"idempotency[{inputs}]",
                status="errored",
                detail=f"{type(exc).__name__}: {exc}",
            ))
            continue
        if once == twice:
            results.append(TestResult(
                name=f"idempotency[{inputs}]",
                status="ok",
                detail="",
            ))
        else:
            results.append(TestResult(
                name=f"idempotency[{inputs}]",
                status="failed",
                detail=f"fn(fn(x)) != fn(x): fn(x)={once!r} fn(fn(x))={twice!r}",
            ))
    return _summarise("verify_idempotency", results)


# --- classification_suite --------------------------------------------------


def classification_suite(
    classify_fn: Callable[[str], Any],
    set_members: list[str],
    expected_type_for: Callable[[str], str] | None = None,
) -> TestSuite:
    """For every member of a set, run classify_fn(member) and verify the
    result is a Ticket (not a Rejection). Optionally verify the type
    assignment matches `expected_type_for(member)`.
    """
    results: list[TestResult] = []
    for member in set_members:
        result = classify_fn(member)
        is_rejection = isinstance(result, dict) and "reason" in result
        if is_rejection:
            results.append(TestResult(
                name=f"classify[{member!r}]",
                status="failed",
                detail=f"expected ticket, got rejection: {result}",
            ))
            continue
        if expected_type_for:
            expected = expected_type_for(member)
            got = result.get("type") if isinstance(result, dict) else None
            if got != expected:
                results.append(TestResult(
                    name=f"classify[{member!r}]",
                    status="failed",
                    detail=f"expected type {expected!r}, got {got!r}",
                ))
                continue
        results.append(TestResult(
            name=f"classify[{member!r}]",
            status="ok",
            detail="",
        ))
    return _summarise("classification_suite", results)


# --- adversarial_neighbors -------------------------------------------------


def adversarial_neighbors(member: str) -> list[str]:
    """Generate near-miss variants of a string member:
        - whitespace padded
        - upper/lower case
        - one-character typo
        - leading/trailing punctuation
    """
    if not member:
        return []
    neighbors = [
        f" {member}",
        f"{member} ",
        member.upper() if member.islower() else member.lower(),
        member[:-1] + "!",
        member + "x",
    ]
    # Dedupe while preserving order.
    seen = set()
    unique = []
    for n in neighbors:
        if n not in seen and n != member:
            seen.add(n)
            unique.append(n)
    return unique


# --- helpers ---------------------------------------------------------------


def _summarise(name: str, results: list[TestResult]) -> TestSuite:
    passed = sum(1 for r in results if r["status"] == "ok")
    failed = len(results) - passed
    return TestSuite(
        name=name, results=results,
        total_passed=passed, total_failed=failed,
    )

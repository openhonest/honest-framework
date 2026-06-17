"""Honesty tests (honest-test spec §4).

Verify that a @link behaves per Honest Code principles at runtime: same input
-> same output (purity), input manifest unchanged (mutation), same result on
repeat (idempotency). Derived entirely from the link declaration; the developer
writes nothing. Failures are returned as data.

A link is `manifest -> Result`. Boundary links (`_link_meta.boundary == True`,
set by honest-type's @link decorator) are exempt from purity/idempotency — I/O
at a declared boundary is expected to have effects. Boundary/non-determinism
instrumentation (§4.4-4.5, monkeypatching) and auth honesty (§4.7, needs
honest-auth) land in a later unit.
"""
from __future__ import annotations

import copy


def _name(link) -> str:
    return getattr(link, "__name__", "<link>")


def _is_boundary(link) -> bool:
    meta = getattr(link, "_link_meta", None)
    return bool(meta and meta.get("boundary"))


def verify_purity(link, manifest):
    """Same input, same output, twice (spec §4.1). Returns a failure or None."""
    if _is_boundary(link):
        return None
    try:
        first = link(copy.deepcopy(manifest))
        second = link(copy.deepcopy(manifest))
    except Exception as exc:
        return {"kind": "errored", "check": "purity", "link": _name(link),
                "detail": f"{type(exc).__name__}: {exc}"}
    if first != second:
        return {"kind": "non_deterministic", "check": "purity", "link": _name(link),
                "detail": f"{first!r} != {second!r}"}
    return None


def detect_mutation(link, manifest):
    """The link must not modify its input manifest (spec §4.2)."""
    before = copy.deepcopy(manifest)
    subject = copy.deepcopy(manifest)
    try:
        link(subject)
    except Exception as exc:
        return {"kind": "errored", "check": "mutation", "link": _name(link),
                "detail": f"{type(exc).__name__}: {exc}"}
    if subject != before:
        return {"kind": "manifest_mutated", "check": "mutation", "link": _name(link),
                "detail": f"{before!r} -> {subject!r}"}
    return None


def verify_idempotency(link, manifest):
    """Same result when run twice on identical input (spec §4.3)."""
    if _is_boundary(link):
        return None
    try:
        first = link(copy.deepcopy(manifest))
        second = link(copy.deepcopy(manifest))
    except Exception as exc:
        return {"kind": "errored", "check": "idempotency", "link": _name(link),
                "detail": f"{type(exc).__name__}: {exc}"}
    if first != second:
        return {"kind": "not_idempotent", "check": "idempotency", "link": _name(link),
                "detail": f"{first!r} != {second!r}"}
    return None


_HONESTY_CHECKS = [verify_purity, detect_mutation, verify_idempotency]


def honesty_suite(link, manifests) -> list:
    """Run every honesty check over every test manifest. Returns failures."""
    failures = []
    for manifest in manifests:
        for check in _HONESTY_CHECKS:
            failure = check(link, manifest)
            if failure is not None:
                failures.append({**failure, "manifest": manifest})
    return failures

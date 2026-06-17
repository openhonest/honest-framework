"""Chain execution model (spec §10).

A link is a function manifest -> Result (`ok`/`err`). The chain is itself a
link: it composes. `execute_chain` short-circuits on the first fault;
`validate_all` runs every link against the same manifest and accumulates all
results. Async links are supported via `execute_chain_async`.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable

from honest_type.result import err, fault, is_err, is_ok, ok


def link(accepts=None, binds=None, boundary: bool = False):
    """Decorator attaching vocabulary metadata for honest-check (spec §10.5).
    It does not alter runtime behavior or scope the manifest. `boundary=True`
    marks an intentional I/O boundary (suppresses honest-test purity warning)."""
    def decorate(fn: Callable) -> Callable:
        fn._link_meta = {"accepts": accepts, "binds": binds, "boundary": boundary}
        return fn
    return decorate


def _link_name(fn: Callable) -> str:
    return getattr(fn, "__name__", "<anonymous link>")


def _check_result(result, fn, current):
    """Return None if `result` is a valid ok, else an err to short-circuit."""
    if is_err(result):
        return result
    if not is_ok(result):
        return err(fault(
            "non_result_return",
            "Link returned neither ok nor err",
            category="server",
            link=_link_name(fn),
            input=current,
        ))
    return None


def execute_chain(links: list, initial_manifest) -> dict:
    """Run links in sequence, short-circuit on the first fault (spec §10.3).
    The chain returns a Result, so it composes as a link."""
    current = initial_manifest
    for fn in links:
        result = fn(current)
        short = _check_result(result, fn, current)
        if short is not None:
            return short
        current = result["ok"]
    return ok(current)


async def execute_chain_async(links: list, initial_manifest) -> dict:
    """Async-capable executor (spec §10.6). Awaits any link whose result is a
    coroutine; otherwise identical to execute_chain."""
    current = initial_manifest
    for fn in links:
        result = fn(current)
        if inspect.isawaitable(result):
            result = await result
        short = _check_result(result, fn, current)
        if short is not None:
            return short
        current = result["ok"]
    return ok(current)


def chain(*links: Callable) -> Callable:
    """Compose links into a single link (spec §10.7). The returned link runs
    execute_chain and propagates the first fault."""
    def run(manifest) -> dict:
        return execute_chain(list(links), manifest)
    run.__name__ = "chain"
    return run


def validate_all(*links: Callable) -> Callable:
    """Accumulating combinator (spec §10.4). Runs every link against the same
    manifest; on any fault returns `validation_failed` carrying every result
    (ok and err both). Returns a link, so it composes."""
    def run(manifest) -> dict:
        results = []
        any_err = False
        for fn in links:
            result = fn(manifest)
            results.append(result)
            if is_err(result):
                any_err = True
        if any_err:
            return err(fault(
                "validation_failed",
                "One or more validation checks failed",
                category="client",
                results=results,
            ))
        return ok(manifest)
    run.__name__ = "validate_all"
    return run

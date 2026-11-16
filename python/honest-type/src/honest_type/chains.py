"""Chain execution model (section 12).

A link is a pure function manifest -> (manifest | Fault): it returns its value on success,
or a Fault on failure (section 12.1) — a bare union, no envelope. The chain executor tells the
value from the fault with the Fault recognizer, `is_fault`. A chain is itself a link: it composes.
`execute_chain` is the short-circuit runner; `chain()` and `validate_all()` wrap a group of links
into a single composable link.

This module is pure. It never catches exceptions — an unhandled exception from a link
propagates to the boundary (section 12.8); the boundary (`catch_at_boundary`) is the one
place that catches.
"""

import inspect
from functools import reduce

from honest_type._util import _pick
from honest_type.types import fault, is_fault


def link(accepts=None, binds=None, boundary=False, authorizes=False, emits=None):
    """Declare a link (section 12.5). Attaches vocabulary/role metadata to a function for
    honest-check introspection and honest-test generation. The function stays callable and
    its runtime behaviour is unchanged — the decorator records intent, it never scopes or
    filters the manifest. Metadata is read with link_meta(); see is_link()."""

    def declare(fn):
        fn.__honest_link__ = {
            "name": fn.__name__,
            "accepts": accepts,
            "binds": binds,
            "boundary": boundary,
            "authorizes": authorizes,
            "emits": emits,
        }
        return fn

    return declare


def is_link(fn) -> bool:
    """True if fn was declared with @link()."""
    return hasattr(fn, "__honest_link__")


def link_meta(fn) -> dict:
    """A declared link's metadata (section 12.5): name, accepts, binds, boundary, authorizes,
    emits. Empty for an undeclared function."""
    return getattr(fn, "__honest_link__", {})


def _advance_fault(result) -> dict:
    """The fault row of a chain step (section 12.3): stop and carry the Fault out unchanged."""
    return {"stopped": result}


def _advance_value(result) -> dict:
    """The value row of a chain step (section 12.3): carry the manifest forward and keep running."""
    return {"running": result}


_ADVANCE = {True: _advance_fault, False: _advance_value}


def _advance_verdict(result) -> dict:
    """One chain step as data (section 12.3): the Fault recognizer closes the outcome to two members,
    the value or a Fault, so the next fold state is a two-row table read by is_fault — no branch."""
    return _ADVANCE[is_fault(result)](result)


def _fold_step(state, link) -> dict:
    """One sync fold step: pass a stopped state through untouched, else run the link against the
    running manifest and take its verdict. The stopped arm never calls the link."""
    return _pick(
        "stopped" in state,
        lambda: state,
        lambda: _advance_verdict(link(state["running"])),
    )


def _fold_result(state) -> dict:
    """The final return of a fold: the Fault that stopped it, or the last running manifest — bare,
    no envelope (section 12.3)."""
    return _pick("stopped" in state, lambda: state["stopped"], lambda: state["running"])


def execute_chain(links, initial_manifest) -> dict:
    """Run links in sequence, short-circuiting on the first Fault (section 12.3), recognized by
    is_fault rather than by an envelope key. Returns the final manifest or the first Fault, both bare."""
    return _fold_result(reduce(_fold_step, links, {"running": initial_manifest}))


async def _await_it(value):
    return await value


async def _return_it(value):
    return value


_AWAIT_BY_KIND = {True: _await_it, False: _return_it}


async def _maybe_await(value):
    """Await value when it is awaitable (an async link's coroutine), else return it unchanged
    (a sync link's return). Dispatched on awaitability, no branch (sections 12.3, 12.6)."""
    return await _AWAIT_BY_KIND[inspect.isawaitable(value)](value)


async def _fold_step_async_running(state, link) -> dict:
    """The running arm of an async fold step: run and await the link, then take its verdict."""
    return _advance_verdict(await _maybe_await(link(state["running"])))


async def _fold_step_async_stopped(state, link) -> dict:
    """The stopped arm of an async fold step: pass the stopped state through; the link never runs."""
    return state


_FOLD_STEP_ASYNC = {True: _fold_step_async_stopped, False: _fold_step_async_running}


async def _fold_step_async(state, link) -> dict:
    """One async fold step, dispatched on whether the fold has already stopped (no branch)."""
    return await _FOLD_STEP_ASYNC["stopped" in state](state, link)


async def execute_chain_async(links, initial_manifest) -> dict:
    """Run links in sequence, awaiting any async link, short-circuiting on the first Fault (sections
    12.3, 12.6). An async link returns a coroutine resolving to a manifest or a Fault; a sync link
    returns it directly. Returns the final manifest or the first Fault, both bare."""
    state = {"running": initial_manifest}
    for link in links:
        state = await _fold_step_async(state, link)
    return _fold_result(state)


def _async_composed(async_run, links):
    """A composed link that is itself a coroutine function: it awaits async_run over the links."""
    async def run(manifest):
        return await async_run(list(links), manifest)

    return run


def _sync_composed(sync_run, links):
    """A composed link that runs synchronously over the links."""
    def run(manifest):
        return sync_run(list(links), manifest)

    return run


def _combinator(sync_run, async_run, links):
    """The sync/async dispatch chain and validate_all share: when any link is async the composed
    link is a coroutine function that awaits async_run, otherwise it runs sync_run; either way it
    returns the composed link. chain and validate_all differ only in the runner pair they supply, so
    the dispatch lives here once and takes the runners as data."""
    return _pick(
        any(map(inspect.iscoroutinefunction, links)),
        lambda: _async_composed(async_run, links),
        lambda: _sync_composed(sync_run, links),
    )


def chain(*links):
    """Compose links into a single link (sections 12.6, 12.7): manifest -> (manifest | Fault),
    short-circuit. A
    chain containing any async link is itself async (its run awaits through execute_chain_async); a
    chain of all sync links is sync. Composition preserves this — an async chain is a coroutine
    function, so a parent chain that contains it is async too."""
    return _combinator(execute_chain, execute_chain_async, links)


def _run_validate_all(links, manifest) -> dict:
    """Run every link against the same manifest, accumulating (section 12.4). Any Fault makes
    the whole a validation_failed fault carrying every result — values and Faults alike — in results."""
    results = [link(manifest) for link in links]
    return _pick(
        any(is_fault(result) for result in results),
        lambda: fault("validation_failed", "one or more validation checks failed", "client", results, {}),
        lambda: manifest,
    )


async def _run_validate_all_async(links, manifest) -> dict:
    """Run every link against the same manifest, awaiting any async link, accumulating (sections
    12.4, 12.6). Any Fault makes the whole a validation_failed fault carrying every result."""
    results = []
    for link in links:
        results.append(await _maybe_await(link(manifest)))
    return _pick(
        any(is_fault(result) for result in results),
        lambda: fault("validation_failed", "one or more validation checks failed", "client", results, {}),
        lambda: manifest,
    )


def validate_all(*links):
    """An accumulating combinator as a composable link (sections 12.4, 12.6, 12.7): all links run
    against the same manifest; the complete picture is preserved on failure. Async when any link is
    async."""
    return _combinator(_run_validate_all, _run_validate_all_async, links)

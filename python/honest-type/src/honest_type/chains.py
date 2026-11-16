"""Chain execution model (section 10).

A link is a pure function manifest -> Result, where a Result is `ok(manifest)` or
`err(fault)` (section 10.1) — the only two shapes a link may return. A chain is itself
a link: it composes. `execute_chain` is the short-circuit runner; `chain()` and
`validate_all()` wrap a group of links into a single composable link.

This module is pure. It never catches exceptions — an unhandled exception from a link
propagates to the boundary (section 10.8); the boundary (`catch_at_boundary`) is the one
place that catches.
"""

import inspect
from functools import reduce

from honest_type._util import _choose, _pick, _read_or
from honest_type.types import err, fault, ok


def link(accepts=None, binds=None, boundary=False, authorizes=False, emits=None):
    """Declare a link (section 10.5). Attaches vocabulary/role metadata to a function for
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
    """A declared link's metadata (section 10.5): name, accepts, binds, boundary, authorizes,
    emits. Empty for an undeclared function."""
    return getattr(fn, "__honest_link__", {})


def _advance_running(link, result, current) -> dict:
    """The ok row of a chain step: unwrap the manifest and keep running."""
    return {"running": result["ok"]}


def _advance_err(link, result, current) -> dict:
    """The err row of a chain step: stop and carry the err Result out unchanged."""
    return {"stopped": result}


def _advance_non_result(link, result, current) -> dict:
    """The no-match row of a chain step (section 10.3): a link returned neither ok nor err, so stop
    with a non_result_return server fault naming the link and the manifest it was given."""
    return {"stopped": err(fault(
        "non_result_return",
        f"{getattr(link, '__name__', None)} returned neither ok nor err; it was given {current!r}",
        "server", [], {"link": getattr(link, "__name__", None)},
    ))}


_ADVANCE = {"err": _advance_err, "ok": _advance_running}


def _advance_verdict(link, result, current) -> dict:
    """One chain step as data (section 10.3): classify a link's return as err, ok, or neither, and
    return the next fold state. err and ok are table rows; neither hits the no-match row."""
    kind = _choose("err" in result, "err", _choose("ok" in result, "ok", "neither"))
    return _read_or(_ADVANCE, kind, _advance_non_result)(link, result, current)


def _fold_step(state, link) -> dict:
    """One sync fold step: pass a stopped state through untouched, else run the link against the
    running manifest and take its verdict. The stopped arm never calls the link."""
    return _pick(
        "stopped" in state,
        lambda: state,
        lambda: _advance_verdict(link, link(state["running"]), state["running"]),
    )


def _fold_result(state) -> dict:
    """The final Result of a fold: the err that stopped it, or ok(the last running manifest)."""
    return _pick("stopped" in state, lambda: state["stopped"], lambda: ok(state["running"]))


def execute_chain(links, initial_manifest) -> dict:
    """Run links in sequence, short-circuiting on the first err (section 10.3). A link that
    returns neither ok nor err is a server fault (non_result_return)."""
    return _fold_result(reduce(_fold_step, links, {"running": initial_manifest}))


async def _await_it(value):
    return await value


async def _return_it(value):
    return value


_AWAIT_BY_KIND = {True: _await_it, False: _return_it}


async def _maybe_await(value):
    """Await value when it is awaitable (an async link's coroutine), else return it unchanged
    (a sync link's Result). Dispatched on awaitability, no branch (sections 10.3, 10.6)."""
    return await _AWAIT_BY_KIND[inspect.isawaitable(value)](value)


async def _fold_step_async_running(state, link) -> dict:
    """The running arm of an async fold step: run and await the link, then take its verdict."""
    return _advance_verdict(link, await _maybe_await(link(state["running"])), state["running"])


async def _fold_step_async_stopped(state, link) -> dict:
    """The stopped arm of an async fold step: pass the stopped state through; the link never runs."""
    return state


_FOLD_STEP_ASYNC = {True: _fold_step_async_stopped, False: _fold_step_async_running}


async def _fold_step_async(state, link) -> dict:
    """One async fold step, dispatched on whether the fold has already stopped (no branch)."""
    return await _FOLD_STEP_ASYNC["stopped" in state](state, link)


async def execute_chain_async(links, initial_manifest) -> dict:
    """Run links in sequence, awaiting any async link, short-circuiting on the first err (sections
    10.3, 10.6). An async link returns a coroutine resolving to a Result; a sync link returns the
    Result directly. A link that returns neither ok nor err is a server fault (non_result_return)."""
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
    """Compose links into a single link (sections 10.6, 10.7): manifest -> Result, short-circuit. A
    chain containing any async link is itself async (its run awaits through execute_chain_async); a
    chain of all sync links is sync. Composition preserves this — an async chain is a coroutine
    function, so a parent chain that contains it is async too."""
    return _combinator(execute_chain, execute_chain_async, links)


def _run_validate_all(links, manifest) -> dict:
    """Run every link against the same manifest, accumulating (section 10.4). Any err makes
    the whole a validation_failed fault carrying every result, ok and err alike."""
    results = [link(manifest) for link in links]
    return _pick(
        any("err" in result for result in results),
        lambda: err(fault("validation_failed", "one or more validation checks failed", "client", results, {})),
        lambda: ok(manifest),
    )


async def _run_validate_all_async(links, manifest) -> dict:
    """Run every link against the same manifest, awaiting any async link, accumulating (sections
    10.4, 10.6). Any err makes the whole a validation_failed fault carrying every result."""
    results = []
    for link in links:
        results.append(await _maybe_await(link(manifest)))
    return _pick(
        any("err" in result for result in results),
        lambda: err(fault("validation_failed", "one or more validation checks failed", "client", results, {})),
        lambda: ok(manifest),
    )


def validate_all(*links):
    """An accumulating combinator as a composable link (sections 10.4, 10.6, 10.7): all links run
    against the same manifest; the complete picture is preserved on failure. Async when any link is
    async."""
    return _combinator(_run_validate_all, _run_validate_all_async, links)

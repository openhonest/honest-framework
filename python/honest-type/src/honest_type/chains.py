"""Chain execution model (section 10).

A link is a pure function manifest -> Result, where a Result is `ok(manifest)` or
`err(fault)` (section 10.1) — the only two shapes a link may return. A chain is itself
a link: it composes. `execute_chain` is the short-circuit runner; `chain()` and
`validate_all()` wrap a group of links into a single composable link.

This module is pure. It never catches exceptions — an unhandled exception from a link
propagates to the boundary (section 10.8); the boundary (`catch_at_boundary`) is the one
place that catches.
"""

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


def execute_chain(links, initial_manifest) -> dict:
    """Run links in sequence, short-circuiting on the first err (section 10.3). A link that
    returns neither ok nor err is a server fault (non_result_return)."""
    current = initial_manifest
    for link in links:
        result = link(current)
        if "err" in result:
            return result
        if "ok" not in result:
            return err(
                fault(
                    "non_result_return",
                    "Link returned neither ok nor err",
                    "server",
                    {"input": current},
                )
            )
        current = result["ok"]
    return ok(current)


def chain(*links):
    """Compose links into a single link (section 10.7): manifest -> Result, short-circuit."""

    def run(manifest):
        return execute_chain(list(links), manifest)

    return run


def _run_validate_all(links, manifest) -> dict:
    """Run every link against the same manifest, accumulating (section 10.4). Any err makes
    the whole a validation_failed fault carrying every result, ok and err alike."""
    results = [link(manifest) for link in links]
    if any("err" in result for result in results):
        return err(
            fault(
                "validation_failed",
                "One or more validation checks failed",
                "client",
                {"results": results},
            )
        )
    return ok(manifest)


def validate_all(*links):
    """An accumulating combinator as a composable link (sections 10.4, 10.7): all links run
    against the same manifest; the complete picture is preserved on failure."""

    def run(manifest):
        return _run_validate_all(list(links), manifest)

    return run

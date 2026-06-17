"""Chain composition — ordered sequences of Links.

`pipe(f, g, h)(x)` returns `h(g(f(x)))`. `compose_chain` folds a list of
Links into a single callable. `run_chain` executes a Chain against an
input and returns the final output or a Fault.

Pure. No mutation. No classes.
"""
from __future__ import annotations

from typing import Any, Callable

from honest_type.manifest import emit_fault
from honest_type.types import Chain, Fault, Link, Vocabulary


def pipe(*fns: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Left-to-right function composition. `pipe(f, g)(x) == g(f(x))`."""
    def composed(x: Any) -> Any:
        out = x
        for fn in fns:
            out = fn(out)
        return out
    return composed


def chain(name: str, links: list[Link]) -> Chain:
    """Pure constructor."""
    return Chain(name=name, links=list(links))


def compose_chain(ch: Chain) -> Callable[[Any], Any]:
    """Fold a Chain into a single callable by piping its links' `fn`s."""
    return pipe(*(link["fn"] for link in ch["links"]))


def run_chain(ch: Chain, input_value: Any) -> Any | Fault:
    """Execute the chain. Catch any raised exception at this boundary and
    return a Fault. This is the ONE place the framework converts
    exceptions to data.
    """
    try:
        composed = compose_chain(ch)
        return composed(input_value)
    except Exception as exc:
        return emit_fault(
            code=type(exc).__name__,
            category="server",
            message=str(exc),
        )


def link(
    name: str,
    role: str,
    fn: Callable[..., Any],
    vocabulary: Vocabulary,
    input_types: list[str] | None = None,
    output_types: list[str] | None = None,
) -> Link:
    """Pure constructor for a Link."""
    return Link(
        name=name,
        role=role,
        fn=fn,
        vocabulary=vocabulary,
        input_types=list(input_types or []),
        output_types=list(output_types or []),
    )

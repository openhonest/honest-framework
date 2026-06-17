"""Step definitions for features/smoke.feature.

Pure handlers. Each takes a context dict + named captures, returns new ctx.
"""
from honest_gherkin import register_step


def _the_number(ctx, n):
    return {**ctx, "n": n}


def _double_it(ctx):
    return {**ctx, "n": ctx["n"] * 2}


def _halve_it(ctx):
    return {**ctx, "n": ctx["n"] // 2}


def _result_is(ctx, expected):
    assert ctx["n"] == expected, f"expected {expected}, got {ctx['n']}"
    return ctx


def register(registry):
    registry = register_step(registry, "given", r"the number {n:int}", _the_number)
    registry = register_step(registry, "when",  r"I double it", _double_it)
    registry = register_step(registry, "when",  r"I halve it",  _halve_it)
    registry = register_step(registry, "then",  r"the result is {expected:int}", _result_is)
    return registry

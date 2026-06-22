"""A sample step module (conformance fixture): exercises the section 8.2 register(registry) contract
for the I/O-boundary probe. Not part of the package and not coverage-measured — it is the realistic
counterpart a real adopter would write, used to drive run_feature_file and the CLI end to end."""

from honest_gherkin import register_step


def _given_number(context, n):
    return {**context, "total": context.get("total", 0) + n}


def _then_total(context, total):
    assert context.get("total", 0) == total
    return context


def register(registry):
    """Thread the registry through this module's step patterns (section 8.2)."""
    registry = register_step(registry, "given", "the number {n:int}", _given_number)
    registry = register_step(registry, "then", "the running total is {total:int}", _then_total)
    return registry

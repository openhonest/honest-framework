"""Set enumeration (section 3.2).

The vocabulary declaration is the test specification. Every bounded Set type contributes
its members; the test space is the full cartesian product of those Sets — exhaustive, no
sampling. A maybe-bound type contributes Nothing (None) as one extra case.
"""

from itertools import product

from honest_type.recognizers import is_bounded, members
from honest_type.vocabulary import is_maybe


def _options(type_name, recognizer, bind):
    """The values a type contributes to the product: its sorted Set members, plus Nothing
    (None) when the type is maybe-bound (section 3.2)."""
    values = sorted(members(recognizer))
    if bind is not None and is_maybe(bind.get(type_name)):
        return [*values, None]
    return values


def enumerate_sets(vocab, bind=None):
    """Every combination of bounded Set members — the full cartesian product (section 3.2).
    Returns a list of proto-manifests {type_name: value}. Predicate (unbounded) types do
    not participate; they are generated separately by strategy (sections 3.3 onward)."""
    bounded = {name: rec for name, rec in vocab["base_types"].items() if is_bounded(rec)}
    names = sorted(bounded)
    option_lists = [_options(name, bounded[name], bind) for name in names]
    return [dict(zip(names, combination)) for combination in product(*option_lists)]

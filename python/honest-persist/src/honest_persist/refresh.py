"""refreshes_from_declared: which declared views asked to be refreshed on a clock, and on what terms.

One of the three freshnesses is answered by a clock; this picks out the views that asked for that one so
the host can schedule them. Ported from declaro-persistum, adapted to honest-persist's bare-union Fault.
A view that asked to be refreshed and named no cadence or no allowance is refused by name: filling either
in would be this package deciding how stale the host's data may be, which is the host's call.
"""

from honest_persist._util import _read_or
from honest_persist.types import refused

_ASKED_FOR_A_CLOCK = "refreshed when asked"
_WHAT_IT_MUST_NAME = {
    "cadence": "how often to refresh it",
    "attempts_allowed": "how many failed refreshes to accept before giving up",
}


_wants_a_clock = lambda view: view["freshness"] == _ASKED_FOR_A_CLOCK


_what_it_left_out = lambda view: list(filter(lambda field: view.get(field) is None, _WHAT_IT_MUST_NAME))


_nothing_was_left_out = lambda _incomplete, wanted: wanted


def _refuse_incomplete(incomplete, _wanted):
    named = "; ".join(
        f"the view {name} asks to be refreshed and does not say "
        + " or ".join(_read_or(_WHAT_IT_MUST_NAME, field, lambda: "") for field in missing)
        for name, missing in incomplete
    )
    return refused(
        "refresh_view_incomplete",
        f"{named}. Give each of those views a cadence and an allowance, or change its freshness to one a "
        f"clock does not answer.",
        {"views": [name for name, _missing in incomplete]},
    )


_REFRESH_ANSWER = {False: _nothing_was_left_out, True: _refuse_incomplete}


def refreshes_from_declared(declared):
    """The views that asked to be refreshed on a clock, or the reason there are none (declaration
    refreshes_from_declared). Keeps only the `refreshed when asked` views, and refuses one that names no
    cadence or no allowance."""
    on_a_clock = list(filter(_wants_a_clock, declared["views"]))
    with_missing = [(view["name"], _what_it_left_out(view)) for view in on_a_clock]
    incomplete = list(filter(lambda nm: nm[1] != [], with_missing))
    return _REFRESH_ANSWER[incomplete != []](incomplete, on_a_clock)

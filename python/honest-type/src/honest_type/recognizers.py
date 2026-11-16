"""Recognizers (section, Core Concepts; section 9.1).

A recognizer is tagged data, not behaviour: `{"kind": "set"|"insensitive"|"predicate", ...}`.
`recognize(token, recognizer)` dispatches on kind through a table — no branching. A raw
set passed to `vocabulary()` is normalized to a Set recognizer; `predicate()` and
`insensitive()` build the other two kinds.
"""

from typing import Any, Callable

from honest_type._util import _pick, _read_or
from honest_type.types import fault


def predicate(fn: Callable[[str], bool]) -> dict:
    """An open-ended recognizer wrapping a String -> Boolean callable."""
    return {"kind": "predicate", "fn": fn}


def insensitive(members) -> dict:
    """A case-insensitive Set recognizer (section 9.1): members and tokens compared lowercased."""
    return {"kind": "insensitive", "members": frozenset(m.lower() for m in members)}


def normalize(declaration) -> dict:
    """Coerce a vocabulary declaration to a recognizer. A raw set/frozenset becomes a Set
    recognizer; an already-tagged recognizer (predicate/insensitive) passes through."""
    return _pick(
        hasattr(declaration, "get") and declaration.get("kind"),
        lambda: declaration,
        lambda: {"kind": "set", "members": frozenset(declaration)},
    )


def _match_set(token: str, recognizer: dict) -> bool:
    return token in recognizer["members"]


def _match_insensitive(token: str, recognizer: dict) -> bool:
    return token.lower() in recognizer["members"]


def _match_predicate(token: str, recognizer: dict) -> bool:
    return recognizer["fn"](token)  # may raise -> the predicate-invocation boundary handles it (classify)


def _match_unknown(token: str, recognizer: dict) -> dict:
    """The no-match row of the kind dispatch (spec 13.7): reached only when the recognizer's
    kind names no matcher, it returns a server fault naming the accepted kinds rather than
    letting the lookup miss in silence."""
    kind = recognizer["kind"]
    return fault(
        "unknown_recognizer_kind",
        f"recognize got an unknown recognizer kind {kind!r}; "
        f"the accepted kinds are {', '.join(_MATCHERS)}; no matcher ran",
        "server", [], {"accepted": list(_MATCHERS), "arrived": kind},
    )


_MATCHERS = {"set": _match_set, "insensitive": _match_insensitive, "predicate": _match_predicate}


def recognize(token: str, recognizer: dict) -> bool | dict:
    """True if `token` matches `recognizer`, dispatched on the recognizer's kind through a table.
    An unknown kind hits the terminal no-match matcher and returns a server fault naming the
    accepted kinds (spec 13.7), rather than letting the lookup miss in silence."""
    return _read_or(_MATCHERS, recognizer["kind"], _match_unknown)(token, recognizer)


def is_bounded(recognizer: dict) -> bool:
    """True if the recognizer enumerates a finite Set (set / insensitive), false for predicates."""
    return recognizer["kind"] in ("set", "insensitive")


def members(recognizer: dict) -> frozenset:
    """The Set members of a bounded recognizer; empty for predicates (section, bounded enumeration)."""
    return _read_or(recognizer, "members", frozenset())

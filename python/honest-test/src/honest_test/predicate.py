"""Predicate classification (honest-test spec §2).

Classify a predicate recognizer to pick its generation strategy. honest-type
predicate recognizers carry a Python callable; we read its source and detect
the strategy markers. Source-introspection (not execution) — best-effort, and
falls back to "external" when the source is unavailable.
"""
from __future__ import annotations

import inspect

# marker substring -> strategy class, checked in priority order (spec §2 table)
_MARKERS = [
    (("re.match", "re.fullmatch", "re.compile", "re.search"), "regex"),
    (("len(",), "length"),
    (("int(", "float("), "numeric"),
    ((".isdigit", ".isalpha", ".isupper", ".islower", ".isalnum"), "charclass"),
]


def classify_predicate(fn) -> str:
    """Return one of: regex | length | numeric | charclass | external | unknown."""
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        return "external"
    for markers, strategy in _MARKERS:
        if any(m in source for m in markers):
            return strategy
    return "unknown"

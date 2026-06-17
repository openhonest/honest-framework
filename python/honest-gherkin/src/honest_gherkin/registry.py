"""Step registry: map (kind, pattern) → handler. Pure functions.

Patterns are regex strings. We support `{name}` and `{name:int}` /
`{name:float}` shorthand that gets compiled to named regex captures with
optional type coercion at bind time.

No global state. The registry is a plain dict; `register_step` returns a
new registry. Callers thread it through.
"""
from __future__ import annotations

import re

from honest_gherkin.types import (
    FAULT_AMBIGUOUS_STEP,
    FAULT_STEP_UNMATCHED,
    Step,
    StepHandler,
    StepMatch,
    StepPattern,
    StepRegistry,
)


# --- Constructors ----------------------------------------------------------


def empty_registry() -> StepRegistry:
    return StepRegistry(patterns=[])


def register_step(
    registry: StepRegistry,
    kind: str,
    pattern: str,
    handler: StepHandler,
) -> StepRegistry:
    """Add a pattern + handler. Returns a new StepRegistry."""
    entry: StepPattern = {
        "kind": kind,
        "pattern": pattern,
        "handler": handler,
    }
    return StepRegistry(patterns=registry["patterns"] + [entry])


# --- Pattern compilation ---------------------------------------------------


# Dispatch table: placeholder type suffix → regex fragment + coercion.
_PLACEHOLDER_TYPES: dict[str, tuple[str, type]] = {
    "str":   (r'(?P<NAME>[^"]+?)', str),
    "int":   (r'(?P<NAME>-?\d+)',   int),
    "float": (r'(?P<NAME>-?\d+\.\d+)', float),
}


_PLACEHOLDER_RE = re.compile(r"\{(?P<name>\w+)(?::(?P<typ>\w+))?\}")


def compile_pattern(pattern: str) -> tuple[re.Pattern[str], dict[str, type]]:
    """Translate a `{name}` / `{name:int}` pattern into a compiled regex.

    Returns (compiled_regex, coercions) where coercions[name] is the target
    type to coerce the captured string to.
    """
    coercions: dict[str, type] = {}

    def _repl(m: re.Match[str]) -> str:
        name = m.group("name")
        typ_name = m.group("typ") or "str"
        if typ_name not in _PLACEHOLDER_TYPES:
            raise ValueError(
                f"unknown placeholder type: {typ_name!r} in pattern {pattern!r}"
            )
        fragment, coercer = _PLACEHOLDER_TYPES[typ_name]
        coercions[name] = coercer
        return fragment.replace("NAME", name)

    regex_src = _PLACEHOLDER_RE.sub(_repl, pattern)
    return re.compile(f"^{regex_src}$"), coercions


# --- Matching --------------------------------------------------------------


class StepUnmatchedError(Exception):
    pass


class AmbiguousStepError(Exception):
    pass


def match_step(step: Step, registry: StepRegistry) -> StepMatch:
    """Return the unique StepMatch for a step.

    Raises StepUnmatchedError (fault_code=step_unmatched) if nothing matches.
    Raises AmbiguousStepError (fault_code=ambiguous_step) if >1 matches.
    """
    matches: list[tuple[StepPattern, re.Match[str], dict[str, type]]] = []
    for pat in registry["patterns"]:
        if pat["kind"] != step["kind"] and step["kind"] in ("and", "but"):
            # and/but steps inherit the resolved kind elsewhere; still try
            # to match as the literal kind first. Fall through.
            pass
        compiled, coercions = compile_pattern(pat["pattern"])
        m = compiled.match(step["text"])
        if m is not None:
            matches.append((pat, m, coercions))

    if not matches:
        raise StepUnmatchedError(
            f"{FAULT_STEP_UNMATCHED}: {step['kind']!r} {step['text']!r}"
        )
    if len(matches) > 1:
        patterns = ", ".join(repr(m[0]["pattern"]) for m in matches)
        raise AmbiguousStepError(
            f"{FAULT_AMBIGUOUS_STEP}: {step['text']!r} matched: {patterns}"
        )

    pattern, regex_match, coercions = matches[0]
    raw_captures = regex_match.groupdict()
    coerced: dict[str, str] = {}
    for name, raw_value in raw_captures.items():
        if raw_value is None:
            continue
        coercer = coercions.get(name, str)
        coerced[name] = coercer(raw_value)  # type: ignore[assignment]
    return StepMatch(pattern=pattern, captures=coerced)

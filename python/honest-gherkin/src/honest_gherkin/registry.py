"""The step registry and matching (section 5, 5.1): registration is a value, matching is a Result.

A StepRegistry is a value built up by register_step — there is no module-global registry and no
decorator (section 10.5), so two test runs can never share registration state. match_step compiles
each registered pattern, attempts a full-text match against the step text, and returns a Result:
exactly one match -> ok(StepMatch) with captures coerced per the pattern's recorded types; no
match -> err(step_unmatched); more than one -> err(ambiguous_step). A pattern that fails to compile
cannot match, so it is skipped rather than raised. match_step never invokes the handler; that is the
runner's job. Pure throughout; faults are data.
"""

import re

from honest_type import err, ok

from honest_gherkin.compile import PLACEHOLDER_TYPES, compile_pattern
from honest_gherkin.ir import step_fault


def empty_registry():
    """An empty step registry (section 5): a value with no registered patterns."""
    return {"patterns": []}


def register_step(registry, kind, pattern, handler):
    """Append one step pattern to the registry (section 5). Returns a NEW registry; never mutates
    its argument, so registration carries no shared state."""
    step_pattern = {"kind": kind, "pattern": pattern, "handler": handler}
    return {"patterns": [*registry["patterns"], step_pattern]}


def _coerce_captures(match, captures):
    """Bind each named capture, coercing it to its recorded type via PLACEHOLDER_TYPES (section 5.1)."""
    return {entry["name"]: PLACEHOLDER_TYPES[entry["type"]]["coerce"](match.group(entry["name"])) for entry in captures}


def match_step(step, registry):
    """Match a step against the registry (section 5.1). Returns ok(StepMatch) for exactly one match,
    err(step_unmatched) for none, err(ambiguous_step) for more than one. A non-compiling pattern is
    skipped. Pure; the handler is not invoked here."""
    matches = []
    for step_pattern in registry["patterns"]:
        compiled = compile_pattern(step_pattern["pattern"])
        if "err" in compiled:
            continue
        hit = compiled["ok"]
        binding = re.match(hit["regex"], step["text"])
        if binding is not None:
            matches.append((step_pattern, hit["captures"], binding))
    count = len(matches)
    if count == 0:
        return err(step_fault("step_unmatched", f"no registered step matches: {step['text']!r}", step_text=step["text"]))
    if count > 1:
        competing = ", ".join(repr(p["pattern"]) for p, _, _ in matches)
        return err(step_fault("ambiguous_step", f"step matches more than one pattern: {competing}", step_text=step["text"]))
    step_pattern, captures, binding = matches[0]
    return ok({"pattern": step_pattern, "captures": _coerce_captures(binding, captures)})

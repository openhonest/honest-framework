"""Rule suppression (spec §7).

Comment directives:
    # honest: ignore RULE[, RULE]    inline — suppress on this line only
    # honest: disable RULE[, RULE]   start a disabled region (to EOF or enable)
    # honest: enable RULE[, RULE]    end the disabled region

A file-level disable is just a disable comment with no matching enable (the
region runs to end of file). Every suppressed diagnostic is recorded as an
`info` so suppressions stay visible (spec §7.4).
"""
from __future__ import annotations

from typing import TypedDict

from honest_check.parse import find_by_type, line_of, node_text


class Suppressions(TypedDict):
    inline: set            # (line, rule) — and (line, "*") for ignore-all
    events: dict           # rule -> sorted list of (line, "disable"|"enable")


_DIRECTIVES = ("ignore", "disable", "enable")


def _parse_directive(text: str):
    """Return (directive, [rules]) or (None, []). Rules empty means 'all'."""
    body = text.lstrip("#").strip()
    if not body.lower().startswith("honest:"):
        return None, []
    rest = body[len("honest:"):].strip()
    parts = rest.replace(",", " ").split()
    if not parts:
        return None, []
    directive = parts[0].lower()
    if directive not in _DIRECTIVES:
        return None, []
    rules = [p for p in parts[1:] if p.startswith("HC")]
    return directive, rules


def parse_suppressions(root, src: bytes) -> Suppressions:
    inline: set = set()
    events: dict = {}
    for comment in find_by_type(root, "comment"):
        directive, rules = _parse_directive(node_text(comment, src))
        if directive is None:
            continue
        line = line_of(comment)
        if directive == "ignore":
            if rules:
                for rule in rules:
                    inline.add((line, rule))
            else:
                inline.add((line, "*"))
        else:  # disable / enable
            for rule in rules:
                events.setdefault(rule, []).append((line, directive))
    for rule in events:
        events[rule].sort()
    return {"inline": inline, "events": events}


def is_suppressed(rule: str, line: int, supp: Suppressions) -> bool:
    if (line, rule) in supp["inline"] or (line, "*") in supp["inline"]:
        return True
    state = None
    for event_line, action in supp["events"].get(rule, []):
        if event_line <= line:
            state = action
        else:
            break
    return state == "disable"

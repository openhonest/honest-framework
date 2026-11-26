# scenario: _edge_role_withdrawn faults a function declared an edge
# inherits: hd=python/honest-design/honest-design.hd::_edge_role_withdrawn -> feature=python/honest-design/features/honest-design.feature::_edge_role_withdrawn faults a function declared an edge
import re

_SOURCE = (
    'module example\n'
    '  edge fn find : (root: str) -> str note "finds a value"\n'
)
_EXPECTED_CODE = "edge_role_withdrawn"
_MESSAGE_FACTS = {
    "the withdrawn role": (
        r"\bedge\b",
        r"\b(?:withdrawn|no longer|retired|obsolete|removed)\b",
    ),
    "relocation as a plain function when exactly one module imports it": (
        r"\b(?:one|single|sole|only)\b",
        (
            r"\b(?:to|by|in|inside|within|into) (?:the |its )?(?:one |sole |single |only )?"
            r"(?:(?:importing|calling) module|(?:importer|caller)|module that (?:imports|calls))\b"
            r"|\b(?:importer|caller|(?:importing|calling) module) (?:owns?|keeps?|hosts?)\b"
        ),
        (r"\b(?:plain|ordinary|unadorned)\s+(?:fn|function)\b"
         r"|\b(?:fn|function)\b[^,]*\bwithout a role\b"),
    ),
    "removal for an unreachable function": (
        r"\b(?:remove|delete|drop)\b",
        r"\b(?:nothing|no caller|no path|never call\w*|unreachable|unused)\b",
    ),
    "why an unreachable function cannot be tested": (
        r"\b(?:nothing reaches|no caller|no path|unreachable|never reached)\b",
        (
            r"\b(?:cannot be tested|can't be tested|untestable|no defined finite testability"
            r"|finite testability is undefined)\b"
        ),
    ),
}


def probe_edge_role_withdrawn_legacy():
    from honest_design import read_hd
    from honest_design.validator import _edge_role_withdrawn

    module = read_hd(_SOURCE)["ok"]["modules"][0]
    faults = _edge_role_withdrawn(module)

    codes = [fault["code"] for fault in faults]
    if codes != [_EXPECTED_CODE]:
        return [f"Expected one {_EXPECTED_CODE} diagnostic, received {codes!r}"]
    fault = faults[0]
    context = (fault.get("category"), fault.get("detail", {}).get("function"))
    expected = ("server", "find")
    if context != expected:
        return [f"Expected category and detail.function {expected!r}, received {context!r}"]
    message = fault["message"].casefold()
    clauses = re.split(r"[.!?;:\n]", message)
    return [
        f"Diagnostic does not explain {fact}: {faults[0]['message']!r}"
        for fact, concepts in _MESSAGE_FACTS.items()
        if not any(all(re.search(pattern, clause) for pattern in concepts) for clause in clauses)
    ]

"""The construction-time rules (section 4.1), as data over the declaration graph.

Seven rules fire at construction time: HC003 (recognizer overlap), HC006
(composed type names an unknown base type), HC007 (empty chain), HC011
(catch-all recognizer), and HC-SM01/HC-SM02/HC-SM05 (state-machine vocabulary
violations). Each reads the graph honest_check.graph builds (section 3.4), never
the raw AST, and each returns Diagnostics as data: a violation is never thrown
(P24, a fault travels in the return value).

The rules are rows in a registry the pure core folds over, not separately
declared functions of the module (P16, the dispatch is a table). Each rule
stamps its Diagnostic's source_location with the construction call node's line
and column, so file:line:col names exactly where the construction sits.
"""

from itertools import combinations

from honest_check.types import Diagnostic


def _diagnostic(rule_id, severity, message, path, line, col, fixable=False) -> Diagnostic:
    return Diagnostic(
        rule_id=rule_id,
        severity=severity,
        message=message,
        source_location=f"{path}:{line}:{col}",
        context="",
        fixable=fixable,
    )


def check_hc007(graph, path: str) -> list[Diagnostic]:
    """HC007 — an empty chain: a chain() constructed with no links (section 4.1,
    check_HC007: len(chain.links) == 0)."""
    findings = []
    for chain in graph["chains"]:
        if chain["link_count"] == 0:
            findings.append(
                _diagnostic(
                    "HC007",
                    "error",
                    f"chain {chain['name']!r} has no links: an empty chain "
                    f"transforms nothing and is dishonest (HC007)",
                    path,
                    chain["line"],
                    chain["col"],
                )
            )
    return findings


def check_hc003(graph, path: str) -> list[Diagnostic]:
    """HC003 — recognizer overlap within a vocabulary (section 4.1, check_HC003).
    Two Set recognizers sharing a value overlap, a decidable error. Any pair that
    involves a predicate cannot be decided statically (honest-check never runs
    the predicate), so it emits info and defers the decision to honest-test."""
    findings = []
    for vocab in graph["vocabularies"]:
        base = vocab["base_types"]
        for name_a, name_b in combinations(base.keys(), 2):
            recog_a = base[name_a]
            recog_b = base[name_b]
            if recog_a["kind"] == "set" and recog_b["kind"] == "set":
                overlap = set(recog_a["members"]) & set(recog_b["members"])
                if overlap:
                    findings.append(
                        _diagnostic(
                            "HC003",
                            "error",
                            f"types {name_a!r} and {name_b!r} share values "
                            f"{sorted(overlap)}: a token cannot be classified to "
                            f"one type (HC003)",
                            path,
                            vocab["line"],
                            vocab["col"],
                        )
                    )
            else:
                findings.append(
                    _diagnostic(
                        "HC003",
                        "info",
                        f"types {name_a!r} and {name_b!r} may overlap on a value: "
                        f"a predicate is involved and honest-check does not run "
                        f"it, so honest-test decides this at test time (HC003)",
                        path,
                        vocab["line"],
                        vocab["col"],
                    )
                )
    return findings


def check_hc006(graph, path: str) -> list[Diagnostic]:
    """HC006 — a composed type requires or captures a base type the vocabulary
    does not declare (section 4.1, check_HC006)."""
    findings = []
    for vocab in graph["vocabularies"]:
        base = vocab["base_types"]
        for comp in vocab["composed_types"]:
            for req_type in comp["requires"]:
                if req_type not in base:
                    findings.append(
                        _diagnostic(
                            "HC006",
                            "error",
                            f"composed type {comp['name']!r} requires base type "
                            f"{req_type!r}, which the vocabulary does not declare "
                            f"(HC006)",
                            path,
                            comp["line"],
                            comp["col"],
                        )
                    )
            if comp["captures"] and comp["captures"] not in base:
                findings.append(
                    _diagnostic(
                        "HC006",
                        "error",
                        f"composed type {comp['name']!r} captures base type "
                        f"{comp['captures']!r}, which the vocabulary does not "
                        f"declare (HC006)",
                        path,
                        comp["line"],
                        comp["col"],
                    )
                )
    return findings


def check_hc011(graph, path: str) -> list[Diagnostic]:
    """HC011 — a catch-all recognizer. A Set is bounded and never a catch-all; a
    predicate may accept nearly everything, but deciding that means running it,
    which honest-check does not do (section 4.1). So each predicate recognizer
    emits info deferring to the vocabulary() constructor and honest-test, which
    sample the fixed corpus and reject a true catch-all before it ships."""
    findings = []
    for vocab in graph["vocabularies"]:
        for type_name, recognizer in vocab["base_types"].items():
            if recognizer["kind"] == "predicate":
                findings.append(
                    _diagnostic(
                        "HC011",
                        "info",
                        f"recognizer {type_name!r} is a predicate honest-check "
                        f"cannot run: whether it is a catch-all is decided by the "
                        f"vocabulary() constructor and honest-test (HC011)",
                        path,
                        vocab["line"],
                        vocab["col"],
                    )
                )
    return findings


def check_state_machine_vocab(graph, path: str) -> list[Diagnostic]:
    """HC-SM01/HC-SM02/HC-SM05 — the state-machine vocabulary violations
    (section 4.1, check_state_machine_vocab). A transition names a from-state not
    in the states vocabulary (HC-SM01) or an event not in the events vocabulary
    (HC-SM02); the initial state is not in the states vocabulary (HC-SM05)."""
    findings = []
    for machine in graph["state_machines"]:
        states = set(machine["states"])
        events = set(machine["events"])
        for state, event in machine["transitions"]:
            if state not in states:
                findings.append(
                    _diagnostic(
                        "HC-SM01",
                        "error",
                        f"transition from-state {state!r} is not in the states "
                        f"vocabulary {sorted(states)} (HC-SM01)",
                        path,
                        machine["line"],
                        machine["col"],
                    )
                )
            if event not in events:
                findings.append(
                    _diagnostic(
                        "HC-SM02",
                        "error",
                        f"transition event {event!r} is not in the events "
                        f"vocabulary {sorted(events)} (HC-SM02)",
                        path,
                        machine["line"],
                        machine["col"],
                    )
                )
        if machine["initial"] not in states:
            findings.append(
                _diagnostic(
                    "HC-SM05",
                    "error",
                    f"initial state {machine['initial']!r} is not in the states "
                    f"vocabulary {sorted(states)} (HC-SM05)",
                    path,
                    machine["line"],
                    machine["col"],
                )
            )
    return findings


# The construction-rule registry: the rules the pure core folds over the graph.
# A tuple, run in full on every graph — not a key lookup — so there is no
# variable-keyed read to guard; each rule decides for itself whether it fires.
_GRAPH_RULES = (
    check_hc003,
    check_hc006,
    check_hc007,
    check_hc011,
    check_state_machine_vocab,
)


def graph_rules():
    """The construction-time rules check_source runs over the declaration graph."""
    return _GRAPH_RULES

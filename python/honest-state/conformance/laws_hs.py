"""honest-state conformance laws: the taxonomy of state kinds, the mutator lookup, and the single-mutator law.

honest-state ships no primitives — the law and the taxonomy are its contribution, as data (§1, §2).
These laws pin the full taxonomy (every kind, store, and mutator of §1.2), the mutator lookup (bounded to
the ten kinds, so every value resolves and there is no miss), the single-mutator law's two questions
(the honest+disjoint test of §1.1 across all four combinations, and the exactly-one-mutator acceptance
test of §1.2), and the DOM decomposition of §1.3 (a region's source dispatched to its classification).
Pure assertions: data in, data out, no mocks.
"""

from honest_state import (
    classify_dom_region,
    mutator_of,
    names_one_mutator,
    second_mutator_legitimate,
    server_state_region,
    side_effect_region,
    state_kinds,
    user_state_region,
)

# The ten rows of the §1.2 taxonomy, each the spec's three columns: the kind word, where it lives,
# and the one mutator allowed to change it. This is the normative table; state_kinds returns exactly it.
_EXPECTED_KINDS = [
    {"kind": "individual_user",   "store": "manifest-declared regions of the DOM",                                         "mutator": "the user (any user-initiated action)"},
    {"kind": "server_sse",        "store": "non-declared regions of the DOM (alerts/notifications)",                       "mutator": "the server / alert source (honest-alerts)"},
    {"kind": "shared_session",    "store": "a shared store (scale-out)",                                                   "mutator": "the auth provider"},
    {"kind": "persisted_domain",  "store": "the database",                                                                "mutator": "an ordinary boundary write (honest-persist insert/update/delete at the I/O boundary)"},
    {"kind": "cache",             "store": "at / preferably across an I/O boundary",                                       "mutator": "refresh-from-source (only write)"},
    {"kind": "transient_request", "store": "the chain (the manifest), in-memory",                                         "mutator": "a link's return value (functional threading)"},
    {"kind": "static_config",     "store": "process memory, frozen at startup",                                           "mutator": "startup (then read-only)"},
    {"kind": "dynamic_config",    "store": "an external flag store",                                                      "mutator": "the flag service (app only reads)"},
    {"kind": "contended_writes",  "store": "on the other side of a queue",                                                "mutator": "the queue's single consumer"},
    {"kind": "composed_value",    "store": "held by the orchestrator in memory, persisted when it must survive a restart", "mutator": "the orchestrator (it applies each pure function's return)"},
]

# The public import surface declared by the .hd entries: the five functions a sibling module or the
# conformance harness reaches. The three dom-region dispatch handlers are internal (the table reaches them).
_PUBLIC = ["state_kinds", "mutator_of", "second_mutator_legitimate", "names_one_mutator", "classify_dom_region"]


def _law_exports():
    import honest_state

    bad = []
    if sorted(getattr(honest_state, "__all__", [])) != sorted(_PUBLIC):
        bad.append(f"__all__ should be exactly the public surface {sorted(_PUBLIC)}: {getattr(honest_state, '__all__', None)}")
    missing = [name for name in _PUBLIC if not hasattr(honest_state, name)]
    if missing:
        bad.append(f"__all__ names not importable: {missing}")
    return bad


def _law_state_kinds():
    bad = []
    if state_kinds() != _EXPECTED_KINDS:
        bad.append(f"state_kinds drifted from the normative §1.2 taxonomy: {state_kinds()}")
    # The §1.2 acceptance test, true by construction: every kind names exactly one mutator.
    if any(not row["mutator"] for row in state_kinds()):
        bad.append("every kind must name exactly one mutator")
    if len(state_kinds()) != 10:
        bad.append(f"the taxonomy has exactly ten kinds: {len(state_kinds())}")
    return bad


def _law_mutator_of():
    bad = []
    # Bounded to the ten StateKindName words, so every value resolves to one row — no miss, no fault.
    if mutator_of("individual_user") != "the user (any user-initiated action)":
        bad.append(f"mutator_of('individual_user') should be the user: {mutator_of('individual_user')}")
    if mutator_of("contended_writes") != "the queue's single consumer":
        bad.append(f"mutator_of('contended_writes') should be the queue's single consumer: {mutator_of('contended_writes')}")
    if mutator_of("composed_value") != "the orchestrator (it applies each pure function's return)":
        bad.append(f"mutator_of('composed_value') should be the orchestrator: {mutator_of('composed_value')}")
    # Every one of the ten kinds resolves to its taxonomy row's mutator.
    for row in _EXPECTED_KINDS:
        if mutator_of(row["kind"]) != row["mutator"]:
            bad.append(f"mutator_of('{row['kind']}') should be {row['mutator']!r}: {mutator_of(row['kind'])}")
    return bad


def _law_second_mutator_legitimate():
    bad = []
    # Legitimate iff honest AND disjoint (§1.1): true only when both hold.
    if second_mutator_legitimate(True, True) is not True:
        bad.append("an honest, disjoint second mutator is legitimate")
    if second_mutator_legitimate(True, False) is not False:
        bad.append("a non-disjoint second mutator is illegitimate")
    if second_mutator_legitimate(False, True) is not False:
        bad.append("a hiding (dishonest) second mutator is illegitimate")
    if second_mutator_legitimate(False, False) is not False:
        bad.append("a dishonest, non-disjoint second mutator is illegitimate")
    return bad


def _law_names_one_mutator():
    bad = []
    # The §1.2 acceptance test: a candidate kind is honest iff it names exactly one mutator.
    if names_one_mutator(["the user (any user-initiated action)"]) is not True:
        bad.append("a candidate naming exactly one mutator passes")
    if names_one_mutator(["the flag service (app only reads)", "the auth provider"]) is not False:
        bad.append("a candidate naming two mutators fails — it is really two kinds")
    if names_one_mutator([]) is not False:
        bad.append("a candidate naming no mutator fails")
    return bad


def _law_classify_dom_region():
    bad = []
    # §1.3: a region's source dispatches to its classification. A manifest-declared region is user state
    # (the user is its single mutator); a server/SSE-driven region is server state (a legitimate second
    # mutator of the DOM, honest and disjoint); everything else is a side effect (a projection, no mutator).
    if classify_dom_region("manifest_declared") != "user_state":
        bad.append(f"a manifest-declared region is user_state: {classify_dom_region('manifest_declared')}")
    if classify_dom_region("server_driven") != "server_state":
        bad.append(f"a server-driven region is server_state: {classify_dom_region('server_driven')}")
    if classify_dom_region("other") != "side_effect":
        bad.append(f"any other region is a side_effect: {classify_dom_region('other')}")
    # The three dispatch handlers each return their one fixed classification word.
    if user_state_region() != "user_state":
        bad.append(f"user_state_region is the constant user_state: {user_state_region()}")
    if server_state_region() != "server_state":
        bad.append(f"server_state_region is the constant server_state: {server_state_region()}")
    if side_effect_region() != "side_effect":
        bad.append(f"side_effect_region is the constant side_effect: {side_effect_region()}")
    return bad


_LAWS = {
    "exports": _law_exports,
    "state_kinds": _law_state_kinds,
    "mutator_of": _law_mutator_of,
    "second_mutator_legitimate": _law_second_mutator_legitimate,
    "names_one_mutator": _law_names_one_mutator,
    "classify_dom_region": _law_classify_dom_region,
}


def run():
    violations = {name: law() for name, law in _LAWS.items()}
    failed = {name: msgs for name, msgs in violations.items() if msgs}
    passed = len(_LAWS) - len(failed)
    for name, msgs in failed.items():
        print(f"FAIL HS-law [{name}]: {msgs}")
    print(f"HS laws: {passed} passed, {len(failed)} failed, {len(_LAWS)} total")
    return 0 if not failed else 1

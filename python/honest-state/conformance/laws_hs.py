"""honest-state conformance laws: the taxonomy of state kinds, the mutator lookup, and the single-mutator law.

honest-state ships no primitives — the law and the taxonomy are its contribution, as data. These laws pin
the full taxonomy (every kind, store, and mutator), the lookup (a known kind and an unknown one), and the
precise honest+disjoint law across all four combinations. Pure assertions: data in, data out.
"""

from honest_state import mutator_of, second_mutator_legitimate, state_kinds

_EXPECTED_KINDS = [
    {"kind": "user", "lives_in": "manifest-declared regions of the DOM", "mutator": "the user"},
    {"kind": "server", "lives_in": "non-declared regions of the DOM", "mutator": "the alert source (honest-alerts)"},
    {"kind": "session", "lives_in": "a shared store (scale-out)", "mutator": "the auth provider"},
    {"kind": "domain", "lives_in": "the database", "mutator": "an ordinary honest-persist boundary write"},
    {"kind": "cache", "lives_in": "at an I/O boundary", "mutator": "refresh-from-source"},
    {"kind": "transient", "lives_in": "the chain manifest, in-memory", "mutator": "a link's return value"},
    {"kind": "static_config", "lives_in": "process memory, frozen at startup", "mutator": "startup"},
    {"kind": "dynamic_config", "lives_in": "an external flag store", "mutator": "the flag service"},
    {"kind": "contended", "lives_in": "behind a queue", "mutator": "the queue's single consumer"},
]


def _law_exports():
    import honest_state

    bad = []
    expected = ["state_kinds", "mutator_of", "second_mutator_legitimate"]
    if sorted(getattr(honest_state, "__all__", [])) != sorted(expected):
        bad.append(f"__all__ should be exactly the public surface: {getattr(honest_state, '__all__', None)}")
    missing = [name for name in expected if not hasattr(honest_state, name)]
    if missing:
        bad.append(f"__all__ names not importable: {missing}")
    return bad


def _law_state_kinds():
    bad = []
    if state_kinds() != _EXPECTED_KINDS:
        bad.append(f"state_kinds drifted from the normative taxonomy: {state_kinds()}")
    # Every kind names exactly one mutator (the §1.2 acceptance test): one mutator string per row.
    if any(not row["mutator"] for row in state_kinds()):
        bad.append("every kind must name exactly one mutator")
    return bad


def _law_mutator_of():
    bad = []
    if mutator_of("user") != {"ok": "the user"}:
        bad.append(f"mutator_of('user') should be the user: {mutator_of('user')}")
    if mutator_of("contended") != {"ok": "the queue's single consumer"}:
        bad.append(f"mutator_of('contended') should be the queue's single consumer: {mutator_of('contended')}")
    unknown = mutator_of("nope").get("err", {})
    if unknown.get("code") != "unknown_state_kind" or unknown.get("category") != "client" or unknown.get("detail") != "nope":
        bad.append(f"mutator_of of an unknown kind should be unknown_state_kind: {unknown}")
    if unknown.get("message") != "'nope' is not a declared kind of state":
        bad.append(f"unknown_state_kind message wrong: {unknown.get('message')}")
    return bad


def _law_second_mutator_legitimate():
    bad = []
    if second_mutator_legitimate(True, True) is not True:
        bad.append("an honest, disjoint second mutator is legitimate")
    if second_mutator_legitimate(True, False) is not False:
        bad.append("a non-disjoint second mutator is illegitimate")
    if second_mutator_legitimate(False, True) is not False:
        bad.append("a hiding (dishonest) second mutator is illegitimate")
    if second_mutator_legitimate(False, False) is not False:
        bad.append("a dishonest, non-disjoint second mutator is illegitimate")
    return bad


_LAWS = {
    "exports": _law_exports,
    "state_kinds": _law_state_kinds,
    "mutator_of": _law_mutator_of,
    "second_mutator_legitimate": _law_second_mutator_legitimate,
}


def run():
    violations = {name: law() for name, law in _LAWS.items()}
    failed = {name: msgs for name, msgs in violations.items() if msgs}
    passed = len(_LAWS) - len(failed)
    for name, msgs in failed.items():
        print(f"FAIL HS-law [{name}]: {msgs}")
    print(f"HS laws: {passed} passed, {len(failed)} failed, {len(_LAWS)} total")
    return 0 if not failed else 1

"""honest-type conformance: the HT laws (honest-conformance-suite.md), generated.

This is the behavioural circle for honest-type. Instead of a human enumerating tokens and
expected manifests, honest-test's generators (enumerate_sets, adversarial_neighbours) build
the bounded input space from each subject vocabulary's own declarations, and the HT laws are
asserted across that space. The classification behaviour the JSON suite could not express —
predicates, case-insensitive Sets, composed types, Maybe binding, throwing predicates — is
all reachable here because subjects are real Python vocabularies, not JSON.

Laws covered: HT-1 (membership), HT-2 (exclusivity), HT-4 (reserved rejection), HT-5 (empty
rejection), HT-6 (unrecognized -> rejection), HT-7 (Set totality), HT-8 (predicate purity).
HT-3 (zero-drift) is inspection-only per the conformance appendix. The runner also asserts
the classify engine's rejection/fault contract (the rejection-reason vocabulary) over crafted
subjects — the edge of the bounded space.

This module is data + pure checks driven through honest_test.verify_laws; the conformance
directory is outside the honest-check gate (it builds throwing predicates on purpose), so it
is free to construct adversarial fixtures.
"""

from honest_test import adversarial_neighbours, enumerate_sets, law, verify_laws

from honest_type import (
    binding,
    classify,
    composed,
    insensitive,
    maybe,
    predicate,
    vocabulary,
)
from honest_type.recognizers import recognize
from honest_type.reserved import _LAYER1, _LAYER2, _LAYER3_PYTHON, reservation_layer
from honest_type.state_machine import (
    StateMachineError,
    state_machine,
    target_action,
    target_next,
    transition,
)
from honest_type.vocabulary import VocabularyError, merge


def _raiser(_token):
    raise ValueError("predicate boom")


# --------------------------------------------------------------------------- helpers


def _matches(vocab, token):
    """Every base-type name whose recognizer accepts `token` (a throwing predicate counts as
    no match, for the purpose of measuring overlap). The runtime analog of all_matches."""
    names = []
    for name, rec in vocab["base_types"].items():
        try:
            if recognize(token, rec):
                names.append(name)
        except Exception:
            pass
    return names


def _set_members(vocab):
    """Every Set member token the vocabulary declares, via exhaustive enumeration."""
    tokens = []
    for combo in enumerate_sets(vocab):
        tokens.extend(combo.values())
    return sorted(set(tokens))


def _generated_tokens(subject):
    """The bounded input space for a runtime subject: declared Set members, supplied
    predicate tokens, and the adversarial neighbours of every Set member."""
    members = _set_members(subject["vocab"])
    tokens = list(members) + list(subject.get("valid", []))
    for member in members:
        tokens.extend(adversarial_neighbours(member))
    return tokens


# --------------------------------------------------------------------------- runtime laws


def _ht1_membership(subject):
    vocab = subject["vocab"]
    declared = set(vocab["base_types"]) | {c["name"] for c in vocab["composed_types"]}
    bad = []
    for token in _generated_tokens(subject):
        result = classify([token], vocab)
        if "err" in result:
            continue
        for key in result:
            if key != "_rejections" and key not in declared:
                bad.append(f"token {token!r} bound undeclared slot {key!r}")
    return bad


def _ht2_exclusivity(subject):
    vocab = subject["vocab"]
    bad = []
    for token in _generated_tokens(subject):
        hits = _matches(vocab, token)
        if len(hits) > 1:
            bad.append(f"token {token!r} matched {hits} (must match <= 1 type)")
    return bad


def _ht6_unrecognized(subject):
    vocab = subject["vocab"]
    bad = []
    for token in _generated_tokens(subject):
        if not isinstance(token, str) or token == "" or _matches(vocab, token):
            continue
        result = classify([token], vocab)
        reasons = [r["reason"] for r in result.get("_rejections", [])]
        if "unrecognized" not in reasons:
            bad.append(f"unmatched token {token!r} produced no unrecognized rejection: {result}")
    return bad


def _ht7_totality(subject):
    vocab = subject["vocab"]
    bad = []
    for member in _set_members(vocab):
        result = classify([member], vocab)
        hits = _matches(vocab, member)
        if not hits:
            bad.append(f"declared Set member {member!r} is unrecognizable (dead type)")
        # Totality is about the member itself; a missing_required rejection for *other*
        # required types (token None) is correct engine behaviour, not a dead type.
        own = [r for r in result.get("_rejections", []) if r.get("token") == member]
        if own:
            bad.append(f"declared Set member {member!r} was rejected: {own}")
    return bad


def _ht8_purity(subject):
    vocab = subject["vocab"]
    bad = []
    for token in _generated_tokens(subject):
        if classify([token], vocab) != classify([token], vocab):
            bad.append(f"classify is not pure for token {token!r}")
    return bad


# --------------------------------------------------------------------------- construction laws


def _construction_rejected(subject):
    """The subject is a (build thunk, expected-substring) pair; constructing it must raise
    VocabularyError carrying the substring."""
    build, expect = subject["build"], subject["expect"]
    try:
        build()
    except VocabularyError as exc:
        if expect in str(exc):
            return []
        return [f"raised VocabularyError but message missing {expect!r}: {exc}"]
    return ["construction succeeded; expected VocabularyError"]


# --------------------------------------------------------------------------- engine contract law


def _classify_contract(subject):
    """Assert classify's rejection/fault contract on a crafted (vocab, bind, tokens) subject:
    the expected fault code, rejection reasons, and manifest slots."""
    vocab = subject["vocab"]
    bind = binding(subject["bind"]) if "bind" in subject else None
    result = classify(subject["tokens"], vocab, bind)
    bad = []
    if "fault" in subject:
        if "err" not in result or result["err"]["code"] != subject["fault"]:
            bad.append(f"expected fault {subject['fault']!r}, got {result}")
        return bad
    reasons = [r["reason"] for r in result.get("_rejections", [])]
    for reason in subject.get("reasons", []):
        if reason not in reasons:
            bad.append(f"expected rejection reason {reason!r}, got reasons {reasons}")
    for slot, value in subject.get("manifest", {}).items():
        if slot not in result or result.get(slot) != value:
            bad.append(f"expected manifest[{slot!r}]={value!r}, got {result}")
    return bad


# --------------------------------------------------------------------------- subjects

_PROTOCOL_HOST = {"protocol": {"http", "https"}, "host": {"example.com"}}

RUNTIME_SUBJECTS = [
    ("two_sets", {"vocab": vocabulary({"color": {"red", "green"}, "size": {"small", "large"}})}),
    ("insensitive", {"vocab": vocabulary({"lang": insensitive({"EN", "FR"})}), "valid": ["en", "Fr"]}),
    ("predicate", {"vocab": vocabulary({"digits": predicate(str.isdigit)}), "valid": ["1", "42", "007"]}),
    (
        "mixed",
        {
            "vocab": vocabulary({"color": {"red"}, "digits": predicate(str.isdigit)}),
            "valid": ["7"],
        },
    ),
]

CONSTRUCTION_SUBJECTS = [
    ("empty_vocab", {"build": lambda: vocabulary({}), "expect": "HT-5"}),
    ("reserved_framework", {"build": lambda: vocabulary({"t": {"manifest"}}), "expect": "reserved"}),
    ("reserved_crosslang", {"build": lambda: vocabulary({"t": {"class"}}), "expect": "reserved"}),
    ("reserved_python", {"build": lambda: vocabulary({"t": {"lambda"}}), "expect": "reserved"}),
    ("set_overlap", {"build": lambda: vocabulary({"a": {"x"}, "b": {"x"}}), "expect": "share"}),
    (
        "merge_name_collision",
        {"build": lambda: merge(vocabulary({"a": {"x"}}), vocabulary({"a": {"y"}})), "expect": "type name"},
    ),
    (
        "merge_value_collision",
        {"build": lambda: merge(vocabulary({"a": {"x"}}), vocabulary({"b": {"x"}})), "expect": "share"},
    ),
    (
        "composed_unknown_require",
        {
            "build": lambda: vocabulary({"a": {"x"}}, composed_types=[composed("c", {"missing": "v"}, "a")]),
            "expect": "unknown base",
        },
    ),
    (
        "composed_unknown_capture",
        {
            "build": lambda: vocabulary({"a": {"x"}}, composed_types=[composed("c", {"a": "x"}, "missing")]),
            "expect": "captures unknown",
        },
    ),
]

EDGE_SUBJECTS = [
    ("reserved_word", {"vocab": vocabulary({"word": predicate(str.isalpha)}), "tokens": ["class"], "reasons": ["reserved_word"]}),
    ("predicate_error", {"vocab": vocabulary({"boom": predicate(_raiser)}), "tokens": ["x"], "fault": "predicate_error"}),
    (
        "unbound_type",
        {"vocab": vocabulary({"a": {"x"}, "b": {"y"}}), "bind": {"a": "a"}, "tokens": ["y"], "reasons": ["unbound_type"]},
    ),
    (
        "duplicate_slot",
        {"vocab": vocabulary({"a": {"x"}, "b": {"y"}}), "bind": {"a": "s", "b": "s"}, "tokens": ["x", "y"], "reasons": ["duplicate_slot"]},
    ),
    ("missing_required", {"vocab": vocabulary({"a": {"x"}, "b": {"y"}}), "tokens": ["x"], "reasons": ["missing_required"]}),
    ("empty_token", {"vocab": vocabulary({"a": {"x"}}), "tokens": [""], "reasons": ["empty_token"]}),
    ("null_token", {"vocab": vocabulary({"a": {"x"}}), "tokens": [None], "reasons": ["null_token"]}),
    ("non_string_token", {"vocab": vocabulary({"a": {"x"}}), "tokens": [42], "fault": "non_string_token"}),
    (
        "composed_bind",
        {
            "vocab": vocabulary({"protocol": {"https"}, "host": {"example.com"}}, composed_types=[composed("url", {"protocol": "https"}, "host")]),
            "tokens": ["https", "example.com"],
            "manifest": {"url": "example.com"},
        },
    ),
    (
        "composed_capture_absent",
        {
            "vocab": vocabulary({"protocol": {"https"}, "host": {"example.com"}}, composed_types=[composed("url", {"protocol": "https"}, "host")]),
            "tokens": ["https"],
            "manifest": {"protocol": "https"},
        },
    ),
    (
        "composed_maybe_nothing",
        {
            "vocab": vocabulary({"protocol": {"https"}, "host": {"example.com"}}, composed_types=[composed("url", {"protocol": "https"}, maybe("host"))]),
            "tokens": ["https"],
            "manifest": {"url": None},
        },
    ),
    (
        "composed_requirement_unmet",
        {
            "vocab": vocabulary(_PROTOCOL_HOST, composed_types=[composed("url", {"protocol": "https"}, "host")]),
            "tokens": ["http", "example.com"],
            "manifest": {"protocol": "http", "host": "example.com"},
        },
    ),
    (
        "maybe_binding_nothing",
        {
            "vocab": vocabulary({"a": {"x"}, "opt": {"y"}}),
            "bind": {"a": "a", "opt": maybe("opt")},
            "tokens": ["x"],
            "manifest": {"opt": None},
        },
    ),
]

RUNTIME_LAWS = [
    law("HT-1", "classify only ever binds declared type names", _ht1_membership),
    law("HT-2", "no token is classified as two types", _ht2_exclusivity),
    law("HT-6", "an unrecognized token produces a rejection, never a silent default", _ht6_unrecognized),
    law("HT-7", "every declared Set member is recognizable (no dead types)", _ht7_totality),
    law("HT-8", "classify is a pure function of its inputs", _ht8_purity),
]
CONSTRUCTION_LAWS = [law("HT-4/HT-5", "invalid vocabularies are rejected at construction", _construction_rejected)]
ENGINE_LAWS = [law("HT-engine", "classify honours its rejection/fault contract", _classify_contract)]


def _sm_construction_rejected(subject):
    """An invalid state machine must fail construction (StateMachineError) with the expected
    substring."""
    build, expect = subject["build"], subject["expect"]
    try:
        build()
    except StateMachineError as exc:
        return [] if expect in str(exc) else [f"raised but message missing {expect!r}: {exc}"]
    return ["construction succeeded; expected StateMachineError"]


def _sm_from_vocabulary(subject):
    """A state machine whose states/events are honest-type vocabularies must build and
    transition over its declared names (the vocabulary path of _names)."""
    machine = state_machine(
        vocabulary({"state": {"idle", "running"}}),
        vocabulary({"event": {"start"}}),
        {("idle", "start"): "running"},
        "idle",
    )
    result = transition(machine, "idle", "start")
    if result.get("ok", {}).get("state") != "running":
        return [f"vocabulary-built machine did not transition idle->running: {result}"]
    return []


SM_CONSTRUCTION_SUBJECTS = [
    ("unknown_from_state", {"build": lambda: state_machine({"a"}, {"e"}, {("b", "e"): "a"}, "a"), "expect": "unknown state"}),
    ("unknown_event", {"build": lambda: state_machine({"a"}, {"e"}, {("a", "x"): "a"}, "a"), "expect": "unknown event"}),
]
SM_LAWS = [
    law("SM-construct", "an invalid state machine is rejected at construction", _sm_construction_rejected),
]
def _sm_actions(subject):
    """A transition may carry an action and values; the machine routes on `next` and hands
    the action back opaquely. Plain routing targets carry no action."""
    bad = []
    action = {"kind": "set", "values": {"role": "ro"}}
    machine = state_machine(
        {"idle", "running"},
        {"start"},
        {("idle", "start"): {"next": "running", "action": action, "values": {"x": 1}}},
        "idle",
    )
    if transition(machine, "idle", "start").get("ok", {}).get("state") != "running":
        bad.append("action-carrying transition did not route to its next state")
    target = machine["transitions"][("idle", "start")]
    if target_next(target) != "running":
        bad.append("target_next of an action record is wrong")
    if target_action(target) != (action, {"x": 1}):
        bad.append(f"target_action is wrong: {target_action(target)}")
    if target_next("running") != "running" or target_action("running") != (None, None):
        bad.append("plain routing target helpers are wrong")
    return bad


SM_VOCAB_LAWS = [
    law("SM-vocab", "states/events may be declared as vocabularies", _sm_from_vocabulary),
    law("SM-actions", "a transition may carry an opaque action and values", _sm_actions),
]


def _reservation_layer_law():
    """A direct check of reservation_layer's full domain — including the not-reserved case,
    which its only production caller (vocabulary construction) can never reach."""
    bad = []
    if reservation_layer("definitely-not-reserved") is not None:
        bad.append("reservation_layer should return None for a non-reserved word")
    layers = {"framework": _LAYER1, "cross-language": _LAYER2, "python": _LAYER3_PYTHON}
    for expected, words in layers.items():
        sample = sorted(words)[0]
        if reservation_layer(sample) != expected:
            bad.append(f"reservation_layer({sample!r}) != {expected!r}")
    return bad


def run():
    groups = [
        verify_laws(RUNTIME_LAWS, RUNTIME_SUBJECTS),
        verify_laws(CONSTRUCTION_LAWS, CONSTRUCTION_SUBJECTS),
        verify_laws(ENGINE_LAWS, EDGE_SUBJECTS),
        verify_laws(SM_LAWS, SM_CONSTRUCTION_SUBJECTS),
        verify_laws(SM_VOCAB_LAWS, [("vocabulary_states", {})]),
    ]
    direct = _reservation_layer_law()

    passed = sum(g["passed"] for g in groups) + (1 if not direct else 0)
    violations = [v for g in groups for v in g["violations"]]
    if direct:
        violations.append({"law": "HT-4", "statement": "reservation_layer total", "subject": "direct", "messages": direct})
    total = sum(g["total"] for g in groups) + 1

    for v in violations:
        print(f"FAIL {v['law']} [{v['subject']}]: {v['messages']}")
    print(f"HT laws: {passed} passed, {len(violations)} failed, {total} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())

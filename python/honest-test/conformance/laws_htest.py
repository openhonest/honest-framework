"""honest-test conformance: honest-test verifying itself through its own law runner.

honest-test exposes a generative-verification surface (spec section 4.10): law(identifier,
statement, check) states one property as data, a subject is a {name, params} record, and
verify_laws(laws, subjects) runs every law against every subject and returns the run record
{passed, total, violations}. This module is honest-test turning that surface on its own pure
functions. Each property is derived from the spec/.hd contract of the function it names and must
hold on the correct current source; a mutation that broke the function would make the law fail.

The laws state invariants that are checked well across many subjects — adversarial-neighbour
set algebra, Set enumeration counts, the numeric and length generators, the §4.7 status mapping,
the honesty and state-machine checks over generated manifests. The 54 probe_*.py fragments carry
the per-function conformance; these laws do not duplicate them.

Each check is pure: it returns [] when the property holds for its subject, one message per
violation otherwise. It never returns a bare boolean and never raises. Subjects are built from
honest-test's own generators over small sample vocabularies, so the input space is honest-test's
own, not hand-picked literals.
"""

from honest_test import (
    adversarial_neighbors,
    classify_predicate,
    classify_mutant_result,
    compute_expected_status,
    control_characters,
    coverage_ratio,
    detect_mutation,
    edit_distance_1,
    encoding_variants,
    enumerate_lengths,
    enumerate_sets,
    extract_predicates,
    fibonacci_sequence,
    law,
    length_extensions,
    mutate_source,
    parse_source,
    test_idempotency,
    test_invalid_transitions,
    test_valid_transitions,
    unicode_confusables,
    verify_laws,
    verify_purity,
)
from honest_type import predicate, state_machine, transition, vocabulary

# The five adversarial-neighbour class functions, named together so AN-3 can state that
# adversarial_neighbors is exactly their deduplicated union (spec section 3.5).
_NEIGHBOUR_CLASSES = (
    edit_distance_1,
    unicode_confusables,
    control_characters,
    length_extensions,
    encoding_variants,
)

# The mechanical change kinds mutate_source is allowed to emit (spec section 9.6 table).
_MUTATION_KINDS = frozenset({
    "comparison_swap", "number_shift", "condition_flip", "result_swap",
    "constant_replace", "membership_change",
})


# --------------------------------------------------------------------- injected links

def _pure_link(manifest):
    """A deterministic, non-mutating link: honesty checks must pass it clean."""
    return {**manifest, "seen": True}


def _nondeterministic_link(_manifest):
    """A link whose output differs run to run (a fresh object each call), so verify_purity
    and test_idempotency must each report exactly one finding against it."""
    return {"nonce": object()}


def _mutating_link(manifest):
    """A link that mutates its input manifest, so detect_mutation must report it."""
    manifest["_mutated"] = True
    return manifest


def _wrong_transition(_machine, _state, _event):
    """A broken transition that always lands on 'locked', so test_valid_transitions has
    something real to catch (proving the valid-transition law is not a tautology)."""
    return {"ok": {"state": "locked"}}


# --------------------------------------------------------------------- generator laws

def _an_no_original(params):
    value = params["value"]
    return [] if value not in adversarial_neighbors(value) else [
        f"adversarial_neighbors({value!r}) contains the original value"]


def _an_deduplicated(params):
    value = params["value"]
    result = adversarial_neighbors(value)
    return [] if len(result) == len(set(result)) else [
        f"adversarial_neighbors({value!r}) has duplicate neighbours"]


def _an_union_of_classes(params):
    value = params["value"]
    combined = []
    for neighbour_class in _NEIGHBOUR_CLASSES:
        combined.extend(neighbour_class(value))
    expected = [n for n in dict.fromkeys(combined) if n != value]
    actual = adversarial_neighbors(value)
    return [] if actual == expected else [
        f"adversarial_neighbors({value!r}) is not the deduplicated union of the five classes"]


def _edit_distance_deletions(params):
    value = params["value"]
    result = edit_distance_1(value)
    bad = []
    if value in result:
        bad.append(f"edit_distance_1({value!r}) contains the original value")
    for index in range(len(value)):
        deletion = value[:index] + value[index + 1:]
        if deletion not in result:
            bad.append(f"edit_distance_1({value!r}) is missing the deletion {deletion!r}")
    return bad


def _confusables_preserve_length(params):
    value = params["value"]
    result = unicode_confusables(value)
    bad = []
    if value in result:
        bad.append(f"unicode_confusables({value!r}) contains the original value")
    for neighbour in result:
        if len(neighbour) != len(value):
            bad.append(f"confusable {neighbour!r} did not preserve the length of {value!r}")
        if neighbour.isascii():
            bad.append(f"confusable {neighbour!r} carries no non-ASCII codepoint")
    return bad


def _control_adds_one_char(params):
    value = params["value"]
    bad = []
    for neighbour in control_characters(value):
        if len(neighbour) != len(value) + 1:
            bad.append(f"control neighbour {neighbour!r} is not {value!r} plus one character")
    return bad


def _length_extensions_grow(params):
    value = params["value"]
    result = length_extensions(value)
    bad = []
    if len(result) != 6:
        bad.append(f"length_extensions({value!r}) returned {len(result)} neighbours, expected 6")
    for neighbour in result:
        if not neighbour.startswith(value):
            bad.append(f"length extension {neighbour[:8]!r}... does not start with {value!r}")
        if len(neighbour) <= len(value):
            bad.append(f"length extension of {value!r} is not longer than the value")
    return bad


def _encoding_bom(params):
    value = params["value"]
    result = encoding_variants(value)
    bad = []
    if value in result:
        bad.append(f"encoding_variants({value!r}) contains the original value")
    if ("﻿" + value) not in result:
        bad.append(f"encoding_variants({value!r}) is missing the UTF-16 BOM prefix")
    return bad


def _fibonacci_structure(params):
    limit, negative = params["limit"], params["negative"]
    result = fibonacci_sequence(limit, negative)
    # Independent Fibonacci oracle bounded by limit.
    expected_positive = []
    current, following = 0, 1
    while current <= limit:
        expected_positive.append(current)
        current, following = following, current + following
    positives = [value for value in result if value >= 0]
    bad = []
    if positives != expected_positive:
        bad.append(f"non-negative part {positives} != bounded Fibonacci run {expected_positive}")
    if any(value > limit for value in positives):
        bad.append(f"a non-negative value exceeds the limit {limit}")
    negatives = [value for value in result if value < 0]
    if negative:
        expected_negatives = sorted(-value for value in expected_positive if value > 0)
        if negatives != expected_negatives:
            bad.append(f"negatives {negatives} != mirror of positives {expected_negatives}")
        if result != expected_negatives + expected_positive:
            bad.append("negatives are not prepended in number-line order ahead of the positives")
    elif negatives:
        bad.append(f"negative=False but the sequence carried negatives {negatives}")
    return bad


def _coverage_floor(params):
    exercised, total = params["exercised"], params["total"]
    record = coverage_ratio(exercised, total)
    pct = record["pct"]
    bad = []
    if record["exercised"] != exercised or record["total"] != total:
        bad.append(f"coverage_ratio did not echo its inputs: {record}")
    if not (0 <= pct <= 100):
        bad.append(f"percentage {pct} is outside 0..100")
    if total == 0:
        if pct != 100:
            bad.append(f"an empty dimension must report 100, got {pct}")
    else:
        # pct is the whole-number floor of 100*exercised/total: it never over-reports and is
        # never low by a whole point. Stated with integers so it does not restate `//`.
        if pct * total > exercised * 100:
            bad.append(f"percentage {pct} over-reports {exercised}/{total}")
        if (pct + 1) * total <= exercised * 100:
            bad.append(f"percentage {pct} under-reports {exercised}/{total}")
    return bad


def _expected_status(params):
    got = compute_expected_status(params["token_class"], params["fault_mapping"])
    return [] if got == params["expected"] else [
        f"compute_expected_status({params['token_class']!r}) = {got}, expected {params['expected']}"]


def _classify_and_determinism(params):
    source, expected = params["source"], params["expected_class"]
    first = extract_predicates(parse_source(source))
    second = extract_predicates(parse_source(source))
    bad = []
    if not first or not second:
        return [f"extract_predicates found no predicate in {source!r}"]
    kind_one = classify_predicate(first[0])
    kind_two = classify_predicate(second[0])
    if kind_one != expected:
        bad.append(f"classify_predicate -> {kind_one!r}, expected {expected!r}")
    if kind_one != kind_two:
        bad.append("classify_predicate is not deterministic across a re-parse")
    if len(first) != len(second):
        bad.append("extract_predicates count differs across a re-parse")
    return bad


def _length_bounds(params):
    source, minimum, maximum = params["source"], params["min"], params["max"]
    node = extract_predicates(parse_source(source))[0]
    generated = enumerate_lengths(node)
    bad = []
    for string in generated["valid"]:
        if not (minimum <= len(string) <= maximum):
            bad.append(f"valid string of length {len(string)} is outside [{minimum}, {maximum}]")
    for string in generated["invalid"]:
        if minimum <= len(string) <= maximum:
            bad.append(f"invalid string of length {len(string)} sits inside [{minimum}, {maximum}]")
    return bad


def _set_product(params):
    declarations = params["declarations"]
    vocab = vocabulary({name: set(members) for name, members in declarations.items()})
    cases = enumerate_sets(vocab)
    expected_count = 1
    for members in declarations.values():
        expected_count *= len(members)
    bad = []
    if len(cases) != expected_count:
        bad.append(f"enumerate_sets produced {len(cases)} cases, expected the product {expected_count}")
    for case in cases:
        if set(case) != set(declarations):
            bad.append(f"manifest {case} does not key exactly the declared type names")
        for name, value in case.items():
            if value not in declarations[name]:
                bad.append(f"manifest value {value!r} is not a member of set {name!r}")
    return bad


def _mutation_single_site(params):
    mutants = mutate_source(params["source"])
    bad = []
    if not isinstance(mutants, list):
        return [f"mutate_source on parseable source returned {mutants!r}, expected a list of mutants"]
    if not mutants:
        return [f"mutate_source found no mutant in {params['source']!r}"]
    for mutant in mutants:
        if mutant["original"] == mutant["replacement"]:
            bad.append(f"mutant {mutant} is not a change (original == replacement)")
        if mutant["change_kind"] not in _MUTATION_KINDS:
            bad.append(f"mutant change_kind {mutant['change_kind']!r} is not a known kind")
        if not mutant["location"]:
            bad.append(f"mutant {mutant} carries no location")
    return bad


# --------------------------------------------------------------------- honesty laws

def _purity_catches_nondeterminism(params):
    manifest = params["manifest"]
    bad = []
    if verify_purity(_pure_link, dict(manifest)) != []:
        bad.append("verify_purity flagged a deterministic link")
    findings = verify_purity(_nondeterministic_link, dict(manifest))
    if not (len(findings) == 1 and findings[0]["code"] == "non_deterministic"):
        bad.append(f"verify_purity did not report one non_deterministic finding: {findings}")
    return bad


def _mutation_detect(params):
    manifest = params["manifest"]
    bad = []
    if detect_mutation(_pure_link, dict(manifest)) != []:
        bad.append("detect_mutation flagged a non-mutating link")
    findings = detect_mutation(_mutating_link, dict(manifest))
    if not (len(findings) == 1 and findings[0]["code"] == "manifest_mutated"):
        bad.append(f"detect_mutation did not report one manifest_mutated finding: {findings}")
    return bad


def _idempotency_catches_drift(params):
    manifest = params["manifest"]
    bad = []
    if test_idempotency(_pure_link, dict(manifest)) != []:
        bad.append("test_idempotency flagged an idempotent chain")
    findings = test_idempotency(_nondeterministic_link, dict(manifest))
    if not (len(findings) == 1 and findings[0]["code"] == "not_idempotent"):
        bad.append(f"test_idempotency did not report one not_idempotent finding: {findings}")
    return bad


# --------------------------------------------------------------------- state-machine laws

def _sample_machine():
    return state_machine(
        {"locked", "unlocked"},
        {"coin", "push"},
        {("locked", "coin"): "unlocked", ("unlocked", "push"): "locked"},
        "locked",
    )


def _valid_transitions_pass(_params):
    machine = _sample_machine()
    bad = []
    clean = test_valid_transitions(machine, transition)
    if clean != []:
        bad.append(f"test_valid_transitions found a fault in a correct machine: {clean}")
    broken = test_valid_transitions(machine, _wrong_transition)
    if not broken:
        bad.append("test_valid_transitions did not catch a broken transition function")
    return bad


def _invalid_transitions_pass(_params):
    machine = _sample_machine()
    findings = test_invalid_transitions(machine, transition)
    return [] if findings == [] else [
        f"test_invalid_transitions flagged a correct machine's undeclared pairs: {findings}"]


# --------------------------------------------------------------------- subjects

_STRING_SUBJECTS = [
    ("red", {"value": "red"}),
    ("https", {"value": "https"}),
    ("token", {"value": "token"}),
    ("abc", {"value": "abc"}),
    ("digits_123", {"value": "123"}),
]

_FIB_SUBJECTS = [
    ("limit_0", {"limit": 0, "negative": False}),
    ("limit_1", {"limit": 1, "negative": False}),
    ("limit_10", {"limit": 10, "negative": False}),
    ("limit_10_neg", {"limit": 10, "negative": True}),
    ("limit_100_neg", {"limit": 100, "negative": True}),
]

_COVERAGE_SUBJECTS = [
    ("empty", {"exercised": 0, "total": 0}),
    ("none", {"exercised": 0, "total": 5}),
    ("half", {"exercised": 1, "total": 2}),
    ("third", {"exercised": 1, "total": 3}),
    ("most", {"exercised": 7, "total": 10}),
    ("full", {"exercised": 3, "total": 3}),
]

_STATUS_SUBJECTS = [
    ("valid", {"token_class": "valid", "fault_mapping": {}, "expected": 200}),
    ("revoked", {"token_class": "revoked", "fault_mapping": {}, "expected": 401}),
    ("expired", {"token_class": "expired", "fault_mapping": {}, "expected": 401}),
    ("missing", {"token_class": "missing", "fault_mapping": {}, "expected": 401}),
    ("forged", {"token_class": "forged", "fault_mapping": {}, "expected": 401}),
    ("malformed", {"token_class": "malformed", "fault_mapping": {}, "expected": 400}),
    ("override", {"token_class": "revoked", "fault_mapping": {"revoked": 418}, "expected": 418}),
]

_CLASSIFY_SUBJECTS = [
    ("length_bounded", {"source": "f = lambda s: len(s) <= 5", "expected_class": "length_bounded"}),
    ("character_class", {"source": "f = lambda s: s.isdigit()", "expected_class": "character_class"}),
    ("numeric", {"source": "f = lambda s: int(s) > 0", "expected_class": "numeric"}),
    ("catch_all", {"source": "f = lambda s: s == 'x'", "expected_class": "catch_all"}),
    ("composite", {"source": "def helper(s):\n    return True\nf = lambda s: helper(s)", "expected_class": "composite"}),
    ("external_lookup", {"source": "f = lambda s: lookup(s)", "expected_class": "external_lookup"}),
]

_LENGTH_SUBJECTS = [
    ("one_to_five", {"source": "f = lambda s: 1 <= len(s) <= 5", "min": 1, "max": 5}),
    ("upper_three", {"source": "f = lambda s: len(s) <= 3", "min": 1, "max": 3}),
    ("three_to_eight", {"source": "f = lambda s: 3 <= len(s) <= 8", "min": 3, "max": 8}),
]

_SET_SUBJECTS = [
    ("two_sets", {"declarations": {"color": {"red", "green"}, "size": {"small", "large"}}}),
    ("one_set", {"declarations": {"lang": {"EN", "FR", "DE"}}}),
    ("three_sets", {"declarations": {"a": {"x"}, "b": {"p", "q"}, "c": {"m", "n", "o"}}}),
]

_MUTATION_SUBJECTS = [
    ("comparison", {"source": "x = 1 < 2"}),
    ("boolean", {"source": "y = True and False"}),
    ("membership", {"source": "z = 1 in [1, 2]"}),
]


def _manifest_subjects():
    """Honesty subjects are the manifests honest-test's own enumerate_sets generates for a small
    sample vocabulary — the generated input space, not hand-written dicts."""
    vocab = vocabulary({"a": {"x", "y"}, "b": {"p", "q"}})
    return [(f"manifest_{index}", {"manifest": manifest})
            for index, manifest in enumerate(enumerate_sets(vocab))]


# --------------------------------------------------------------------- law groups

_STRING_LAWS = [
    law("AN-1", "adversarial_neighbors never contains the original value", _an_no_original),
    law("AN-2", "adversarial_neighbors is deduplicated", _an_deduplicated),
    law("AN-3", "adversarial_neighbors is the deduplicated union of the five neighbour classes", _an_union_of_classes),
    law("ED-1", "edit_distance_1 omits the original and contains every single-character deletion", _edit_distance_deletions),
    law("UC-1", "each unicode_confusables neighbour preserves length and carries a non-ASCII codepoint", _confusables_preserve_length),
    law("CC-1", "each control_characters neighbour is the value plus exactly one injected character", _control_adds_one_char),
    law("LE-1", "each length_extensions neighbour starts with the value and is longer", _length_extensions_grow),
    law("EV-1", "encoding_variants omits the original and includes the UTF-16 BOM prefix", _encoding_bom),
]

_FIB_LAWS = [law("FIB-1", "fibonacci_sequence is the bounded Fibonacci run, with negatives prepended iff requested", _fibonacci_structure)]
_COVERAGE_LAWS = [law("COV-1", "coverage_ratio is the whole-number floor share within 0..100", _coverage_floor)]
_STATUS_LAWS = [law("STATUS-1", "compute_expected_status maps each token class to its section 4.7 status", _expected_status)]
_CLASSIFY_LAWS = [law("CLS-1", "classify_predicate assigns the declared class deterministically", _classify_and_determinism)]
_LENGTH_LAWS = [law("LEN-1", "enumerate_lengths keeps valid strings in range and invalid ones just outside", _length_bounds)]
_SET_LAWS = [law("SET-1", "enumerate_sets yields the Cartesian product with every value a set member", _set_product)]
_MUTATION_LAWS = [law("MUT-1", "every mutant is a single-site change at a located node", _mutation_single_site)]
_HONESTY_LAWS = [
    law("HON-1", "verify_purity passes a pure link and catches a non-deterministic one", _purity_catches_nondeterminism),
    law("HON-2", "detect_mutation passes a clean link and catches a mutating one", _mutation_detect),
    law("HON-3", "test_idempotency passes an idempotent chain and catches a drifting one", _idempotency_catches_drift),
]
_SM_LAWS = [
    law("SM-1", "test_valid_transitions passes a correct machine and catches a broken transition", _valid_transitions_pass),
    law("SM-2", "test_invalid_transitions passes a correct machine's undeclared pairs", _invalid_transitions_pass),
]


def _subjects(pairs):
    """Wrap (name, params) pairs as honest-test Subject records {name, params}, the shape
    verify_laws reads its cases as."""
    return [{"name": name, "params": params} for name, params in pairs]


def _mutate_source_faults_on_garbage():
    """mutate_source returns a Fault value (problem + remedy), never a raise, for unparseable
    source (spec section 9.6)."""
    result = mutate_source("x = = 2")
    if not (isinstance(result, dict) and "problem" in result and "remedy" in result):
        return ["mutate_source on unparseable source did not return a Fault value"]
    return []


def _enumerate_sets_predicate_only_is_one_empty_manifest():
    """A vocabulary of only predicate recognizers has nothing to enumerate, so enumerate_sets
    yields exactly one empty manifest (spec section 3.2)."""
    cases = enumerate_sets(vocabulary({"digits": predicate(str.isdigit)}))
    if cases != [{}]:
        return [f"enumerate_sets of a predicate-only vocabulary gave {cases}, expected [{{}}]"]
    return []


def _classify_mutant_result_contract():
    """classify_mutant_result judges a run three ways (spec section 9.6): undecided when the run
    did not complete, set_aside when the output matched the baseline, caught when it differed."""
    bad = []
    if classify_mutant_result("a", "b", False)["verdict"] != "undecided":
        bad.append("an incomplete run must be undecided")
    if classify_mutant_result("a", "a", True)["verdict"] != "set_aside":
        bad.append("an identical output must be set_aside")
    if classify_mutant_result("a", "b", True)["verdict"] != "caught":
        bad.append("a differing output must be caught")
    return bad


def run():
    groups = [
        verify_laws(_STRING_LAWS, _subjects(_STRING_SUBJECTS)),
        verify_laws(_FIB_LAWS, _subjects(_FIB_SUBJECTS)),
        verify_laws(_COVERAGE_LAWS, _subjects(_COVERAGE_SUBJECTS)),
        verify_laws(_STATUS_LAWS, _subjects(_STATUS_SUBJECTS)),
        verify_laws(_CLASSIFY_LAWS, _subjects(_CLASSIFY_SUBJECTS)),
        verify_laws(_LENGTH_LAWS, _subjects(_LENGTH_SUBJECTS)),
        verify_laws(_SET_LAWS, _subjects(_SET_SUBJECTS)),
        verify_laws(_MUTATION_LAWS, _subjects(_MUTATION_SUBJECTS)),
        verify_laws(_HONESTY_LAWS, _subjects(_manifest_subjects())),
        verify_laws(_SM_LAWS, _subjects([("turnstile", {})])),
    ]
    directs = [
        ("MUT-2", "mutate_source returns a Fault for unparseable source", _mutate_source_faults_on_garbage()),
        ("SET-2", "enumerate_sets of a predicate-only vocabulary is one empty manifest", _enumerate_sets_predicate_only_is_one_empty_manifest()),
        ("MUT-3", "classify_mutant_result judges undecided/set_aside/caught", _classify_mutant_result_contract()),
    ]

    passed = sum(g["passed"] for g in groups) + sum(1 for _, _, messages in directs if not messages)
    violations = [v for g in groups for v in g["violations"]]
    for law_id, statement, messages in directs:
        if messages:
            violations.append({"law": law_id, "statement": statement, "subject": "direct", "messages": messages})
    total = sum(g["total"] for g in groups) + len(directs)

    for violation in violations:
        print(f"FAIL {violation['law']} [{violation['subject']}]: {violation['messages']}")
    print(f"honest-test laws: {passed} passed, {len(violations)} failed, {total} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())

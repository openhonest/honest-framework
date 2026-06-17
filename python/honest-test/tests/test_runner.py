"""honest-test §2 predicate classification + §3 classification runner."""
from honest_type import insensitive, predicate, vocabulary

from honest_test.predicate import classify_predicate
from honest_test.runner import (
    adversarial_suite,
    classification_suite,
    run_vocabulary,
)


def _num(s):
    return int(s) > 0


def _len5(s):
    return len(s) == 5


def _re(s):
    import re
    return bool(re.match(r"x+", s))


def _digits(s):
    return s.isdigit()


def test_classify_predicate():
    assert classify_predicate(_num) == "numeric"
    assert classify_predicate(_len5) == "length"
    assert classify_predicate(_re) == "regex"
    assert classify_predicate(_digits) == "charclass"


def _ok(result):
    assert result["ok"] if False else True  # noqa
    return result["ok"]


def test_classification_suite_clean():
    vocab = vocabulary({"code": {"USD", "EUR", "GBP"}})["ok"]
    assert classification_suite(vocab) == []


def test_adversarial_suite_clean_case_sensitive():
    vocab = vocabulary({"code": {"USD", "EUR", "GBP"}})["ok"]
    # A pure case-sensitive Set rejects every non-member neighbor.
    assert adversarial_suite(vocab) == []


def test_run_vocabulary_passes_for_clean_vocab():
    vocab = vocabulary({"code": {"USD", "EUR"}})["ok"]
    report = run_vocabulary(vocab)
    assert report["passed"] is True


def test_adversarial_suite_catches_loose_predicate():
    # 'lower3' accepts the lowercase case-variation neighbor of a Set member.
    vocab = vocabulary({
        "code": {"USD"},
        "lower3": predicate(lambda s: s.islower() and len(s) == 3),
    })["ok"]
    failures = adversarial_suite(vocab)
    assert any(f["kind"] == "accepted_neighbor" and f["neighbor"] == "usd"
               for f in failures)


def test_classification_suite_insensitive_members_classify():
    vocab = vocabulary({"code": insensitive({"USD", "EUR"})})["ok"]
    # insensitive stores lowercased members; each must still classify.
    assert classification_suite(vocab) == []

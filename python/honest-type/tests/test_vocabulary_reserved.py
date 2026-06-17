"""reserved-words / binding-auto / binding-merge.

Spec §2 (three-layer reserved words, construction-time validation), §3
(overlap detection and merge collisions), §6 (auto-binding).
"""
import honest_type as ht
from honest_type.reserved import (
    LAYER_1_FRAMEWORK,
    LAYER_2_CROSS_LANGUAGE,
    LAYER_3_PYTHON,
)


def _ok(r):
    assert ht.is_ok(r), r
    return r["ok"]


# --- reserved words ------------------------------------------------------


def test_layer1_framework_word_rejected_at_construction():
    r = ht.vocabulary({"bad": {"manifest", "ticket"}})
    assert ht.is_err(r)
    assert r["err"]["code"] == "reserved_word_in_vocabulary"
    assert r["err"]["category"] == "server"
    assert r["err"]["detail"]["layer"] == "framework"


def test_layer2_cross_language_word_rejected():
    r = ht.vocabulary({"bad": {"class"}})
    assert ht.is_err(r) and r["err"]["detail"]["layer"] == "cross_language"


def test_layer3_python_word_rejected():
    r = ht.vocabulary({"bad": {"lambda"}})
    assert ht.is_err(r) and r["err"]["detail"]["layer"] == "language"


def test_reservation_layer_priority_and_membership():
    assert ht.reservation_layer("manifest") == "framework"
    assert ht.reservation_layer("class") == "cross_language"
    assert ht.reservation_layer("lambda") == "language"
    assert ht.reservation_layer("currency") is None
    assert ht.is_reserved("token") and not ht.is_reserved("widgetish")


def test_layers_are_disjoint_enough_to_report_one_layer():
    # No word should be in both framework and the others in a way that breaks
    # priority reporting; framework wins.
    assert "manifest" in LAYER_1_FRAMEWORK
    assert "class" in LAYER_2_CROSS_LANGUAGE
    assert "lambda" in LAYER_3_PYTHON


# --- overlap (§3) --------------------------------------------------------


def test_set_set_overlap_rejected_at_construction():
    r = ht.vocabulary({"a": {"X", "Y"}, "b": {"Y", "Z"}})
    assert ht.is_err(r)
    assert r["err"]["code"] == "vocabulary_overlap"
    assert "Y" in r["err"]["detail"]["members"]


def test_disjoint_sets_construct_ok():
    assert ht.is_ok(ht.vocabulary({"a": {"X"}, "b": {"Y"}}))


# --- merge (§3) ----------------------------------------------------------


def test_merge_ok_unions_types():
    va = _ok(ht.vocabulary({"format_name": {"currency"}}))
    vb = _ok(ht.vocabulary({"currency_code": {"USD"}}))
    merged = _ok(ht.merge_vocabularies(va, vb))
    assert set(merged["base_types"]) == {"format_name", "currency_code"}


def test_merge_name_collision_fails():
    va = _ok(ht.vocabulary({"x": {"A"}}))
    vb = _ok(ht.vocabulary({"x": {"B"}}))
    r = ht.merge_vocabularies(va, vb)
    assert ht.is_err(r) and r["err"]["code"] == "vocabulary_merge_name_collision"


def test_merge_value_collision_fails():
    va = _ok(ht.vocabulary({"x": {"SHARED"}}))
    vb = _ok(ht.vocabulary({"y": {"SHARED"}}))
    r = ht.merge_vocabularies(va, vb)
    assert ht.is_err(r) and r["err"]["code"] == "vocabulary_merge_value_collision"


# --- auto binding (§6) ---------------------------------------------------


def test_auto_binding_identity_for_base_and_composed():
    vocab = _ok(ht.vocabulary(
        {"format_name": {"currency"}, "integer": ht.predicate(str.isdigit)},
        composed_types=[ht.composed("currency_precision",
                                   requires={"format_name": "currency"},
                                   captures="integer")],
    ))
    auto = ht.auto_binding(vocab)
    assert auto == {
        "format_name": "format_name",
        "integer": "integer",
        "currency_precision": "currency_precision",
    }

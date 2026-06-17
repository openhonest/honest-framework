"""classify-basic / classify-order / classify-composed / classify-maybe.

Derived from honest-type-architecture.md §4, §5, §6 (worked examples) and the
§14.5 conformance cases. Pure-function assertions, no mocks.
"""
import honest_type as ht


def _ok(result):
    assert ht.is_ok(result), result
    return result["ok"]


def _vocab(base, composed=None):
    return _ok(ht.vocabulary(base, composed_types=composed))


# --- classify-basic ------------------------------------------------------


def test_basic_explicit_binding():
    vocab = _vocab({
        "format_name":   {"currency", "number", "percent"},
        "currency_code": {"USD", "EUR", "GBP"},
        "integer":       ht.predicate(str.isdigit),
    })
    m = ht.classify(["currency", "USD", "2"], vocab, {
        "format_name": "format", "currency_code": "currency", "integer": "precision",
    })
    assert m == {"format": "currency", "currency": "USD", "precision": "2"}


def test_basic_auto_binding_uses_type_names_as_slots():
    vocab = _vocab({"format_name": {"currency", "number"}})
    m = ht.classify(["currency"], vocab)
    assert m == {"format_name": "currency"}


# --- classify-order ------------------------------------------------------


def test_order_independence():
    vocab = _vocab({
        "format_name":   {"currency", "number", "percent"},
        "currency_code": {"USD", "EUR", "GBP"},
        "integer":       ht.predicate(str.isdigit),
    })
    bind = {"format_name": "format", "currency_code": "currency", "integer": "precision"}
    a = ht.classify(["currency", "USD", "2"], vocab, bind)
    b = ht.classify(["2", "USD", "currency"], vocab, bind)
    c = ht.classify(["USD", "2", "currency"], vocab, bind)
    assert a == b == c == {"format": "currency", "currency": "USD", "precision": "2"}


# --- classify-composed ---------------------------------------------------


def _composed_vocab():
    return _vocab(
        {
            "format_name":   {"currency", "number", "percent"},
            "currency_code": {"USD", "EUR", "GBP"},
            "integer":       ht.predicate(str.isdigit),
        },
        composed=[ht.composed("currency_precision",
                              requires={"format_name": "currency"},
                              captures="integer")],
    )


_COMPOSED_BIND = {
    "format_name": "format", "currency_code": "currency",
    "integer": "precision", "currency_precision": "decimals",
}


def test_composed_captures_and_overrides_base_binding():
    m = ht.classify(["currency", "USD", "2"], _composed_vocab(), _COMPOSED_BIND)
    # integer captured -> bound to decimals, base "precision" suppressed
    assert m == {"format": "currency", "currency": "USD", "decimals": "2"}
    assert "precision" not in m


def test_composed_requirement_unmet_falls_through_to_base():
    m = ht.classify(["number", "USD", "2"], _composed_vocab(), _COMPOSED_BIND)
    assert m == {"format": "number", "currency": "USD", "precision": "2"}
    assert "decimals" not in m


def test_composed_does_not_emit_missing_required_for_captured_type():
    # Regression: captured integer must not be flagged missing_required.
    m = ht.classify(["currency", "USD", "2"], _composed_vocab(), _COMPOSED_BIND)
    assert "_rejections" not in m


# --- classify-maybe ------------------------------------------------------


def test_maybe_absent_token_becomes_nothing_not_rejection():
    vocab = _vocab({"format_name": {"currency", "number"}, "currency_code": {"USD", "EUR"}})
    m = ht.classify(["currency"], vocab, {
        "format_name": "format", "currency_code": ht.maybe("currency"),
    })
    assert m == {"format": "currency", "currency": None}
    assert "_rejections" not in m


def test_required_absent_token_is_missing_required():
    vocab = _vocab({"format_name": {"currency", "number"}, "currency_code": {"USD", "EUR"}})
    m = ht.classify(["currency"], vocab, {
        "format_name": "format", "currency_code": "currency",
    })
    assert m["format"] == "currency"
    assert {"token": None, "reason": "missing_required", "detail": "currency_code"} in m["_rejections"]


def test_maybe_composed_capture_nothing_when_requirement_met_but_capture_absent():
    vocab = _vocab(
        {"format_name": {"currency", "number"}, "integer": ht.predicate(str.isdigit)},
        composed=[ht.composed("currency_precision",
                             requires={"format_name": "currency"},
                             captures=ht.maybe("integer"))],
    )
    m = ht.classify(["currency"], vocab, {
        "format_name": "format", "integer": ht.maybe("precision"),
        "currency_precision": "decimals",
    })
    assert m["format"] == "currency"
    assert m["decimals"] is None


def test_empty_token_list_all_maybe_nothing_all_required_missing():
    vocab = _vocab({"format_name": {"currency"}, "currency_code": {"USD"}})
    m = ht.classify([], vocab, {
        "format_name": "format", "currency_code": ht.maybe("currency"),
    })
    assert m["currency"] is None
    reasons = {r["reason"] for r in m["_rejections"]}
    assert reasons == {"missing_required"}
    assert m["_rejections"][0]["detail"] == "format_name"

"""classify-rejection / classify-edge / classify-fault.

Every rejection reason code (spec §7, §11.3) and the §9 edge-case rules,
with the exact triggering input. Faults (server bugs) vs rejections (client
input) are kept distinct (§11.1).
"""
import honest_type as ht


def _vocab(base, composed=None):
    r = ht.vocabulary(base, composed_types=composed)
    assert ht.is_ok(r), r
    return r["ok"]


def _reasons(manifest):
    return [r["reason"] for r in manifest.get("_rejections", [])]


# --- every rejection reason code -----------------------------------------


def test_unrecognized():
    m = ht.classify(["currency", "XYZ"], _vocab({"format_name": {"currency", "number"}}))
    assert {"token": "XYZ", "reason": "unrecognized"} in m["_rejections"]


def test_reserved_word_via_predicate_at_classify_time():
    # A predicate that would match a reserved word -> reserved_word rejection (§2).
    vocab = _vocab({"word": ht.predicate(lambda s: True)})
    m = ht.classify(["class"], vocab)        # "class" is Layer-2 reserved
    assert {"token": "class", "reason": "reserved_word"} in m["_rejections"]


def test_unbound_type():
    # A classified type with no binding entry -> unbound_type (server, §11.3).
    vocab = _vocab({"format_name": {"currency"}, "currency_code": {"USD"}})
    m = ht.classify(["currency", "USD"], vocab, {"format_name": "format"})
    assert {"token": "USD", "reason": "unbound_type", "detail": "currency_code"} in m["_rejections"]


def test_duplicate_slot():
    vocab = _vocab({"code": {"USD", "EUR"}})
    m = ht.classify(["USD", "EUR"], vocab, {"code": "currency"})
    assert "duplicate_slot" in _reasons(m)


def test_missing_required():
    vocab = _vocab({"format_name": {"currency"}, "code": {"USD"}})
    m = ht.classify(["currency"], vocab, {"format_name": "format", "code": "currency"})
    assert {"token": None, "reason": "missing_required", "detail": "code"} in m["_rejections"]


def test_empty_token():
    vocab = _vocab({"format_name": {"currency"}})
    m = ht.classify(["currency", ""], vocab)
    assert {"token": "", "reason": "empty_token"} in m["_rejections"]


def test_null_token():
    vocab = _vocab({"format_name": {"currency"}})
    m = ht.classify(["currency", None], vocab)
    assert {"token": None, "reason": "null_token"} in m["_rejections"]


# --- edge cases (§9) -----------------------------------------------------


def test_case_sensitive_by_default():
    vocab = _vocab({"code": {"USD", "EUR"}})
    m = ht.classify(["usd"], vocab)        # lowercase does not match
    assert {"token": "usd", "reason": "unrecognized"} in m["_rejections"]


def test_insensitive_matches_and_preserves_original_value():
    vocab = _vocab({"code": ht.insensitive({"USD", "EUR"})})
    m = ht.classify(["usd"], vocab, {"code": "currency"})
    assert m["currency"] == "usd"          # original token preserved (§9.1)


def test_internal_whitespace_preserved_classify_does_not_trim():
    vocab = _vocab({"city": {"New York", "Boston"}})
    m = ht.classify(["New York"], vocab, {"city": "city"})
    assert m["city"] == "New York"


def test_non_string_token_is_a_server_fault():
    vocab = _vocab({"format_name": {"currency"}})
    result = ht.classify(["currency", 2], vocab)
    assert ht.is_fault(result)
    assert result["code"] == "non_string_token" and result["category"] == "server"


def test_predicate_error_is_a_server_fault():
    def boom(_s):
        raise ValueError("kaboom")
    vocab = _vocab({"explosive": ht.predicate(boom)})
    result = ht.classify(["anything"], vocab)
    assert ht.is_fault(result)
    assert result["code"] == "predicate_error" and result["category"] == "server"

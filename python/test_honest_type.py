"""
honest-type: real tests
Runs against honest_type.py and reports results.
No test framework needed — pure function assertions.
"""

import traceback
from honest_type import (
    vocabulary, classify, maybe, composed, Nothing,
    auto_binding, fault, ok, err,
)

passed = 0
failed = 0
failures = []


def check(test_id: str, actual, expected):
    global passed, failed
    if actual == expected:
        print(f"  PASS  {test_id}")
        passed += 1
    else:
        print(f"  FAIL  {test_id}")
        print(f"        expected: {expected}")
        print(f"        actual:   {actual}")
        failed += 1
        failures.append(test_id)


def section(name: str):
    print(f"\n{name}")
    print("-" * len(name))


# ---------------------------------------------------------------------------
# Shared vocabulary for most tests
# ---------------------------------------------------------------------------

format_vocab = vocabulary({
    "format_name":   {"currency", "number", "percent", "date"},
    "currency_code": {"USD", "EUR", "GBP", "JPY"},
    "style_name":    {"short", "medium", "long"},
    "integer":       str.isdigit,
})

format_binding = {
    "format_name":   "format",
    "currency_code": "currency",
    "style_name":    "style",
    "integer":       "precision",
}

# ---------------------------------------------------------------------------
# Section 1: Basic classification
# ---------------------------------------------------------------------------

section("1. Basic Set classification")

check("basic-001: single token",
    classify(["currency"], format_vocab, format_binding),
    {"format": "currency"}
)

check("basic-002: three tokens explicit binding",
    classify(["currency", "USD", "2"], format_vocab, format_binding),
    {"format": "currency", "currency": "USD", "precision": "2"}
)

check("basic-003: auto binding (type names become slot names)",
    classify(["currency", "USD"], format_vocab),
    {"format_name": "currency", "currency_code": "USD"}
)

# ---------------------------------------------------------------------------
# Section 2: Order independence
# ---------------------------------------------------------------------------

section("2. Order independence")

result_forward  = classify(["currency", "USD", "2"], format_vocab, format_binding)
result_reversed = classify(["2", "USD", "currency"], format_vocab, format_binding)
result_mixed    = classify(["USD", "2", "currency"], format_vocab, format_binding)

check("order-001: forward order",  result_forward,  {"format": "currency", "currency": "USD", "precision": "2"})
check("order-002: reversed order", result_reversed, {"format": "currency", "currency": "USD", "precision": "2"})
check("order-003: mixed order",    result_mixed,    {"format": "currency", "currency": "USD", "precision": "2"})
check("order-004: all three identical", result_forward == result_reversed == result_mixed, True)

# ---------------------------------------------------------------------------
# Section 3: Maybe
# ---------------------------------------------------------------------------

section("3. Maybe (optional slots)")

maybe_binding = {
    "format_name":   "format",
    "currency_code": maybe("currency"),
    "integer":       maybe("precision"),
}

check("maybe-001: maybe slot filled",
    classify(["currency", "USD"], format_vocab, maybe_binding),
    {"format": "currency", "currency": "USD", "precision": Nothing}
)

check("maybe-002: maybe slot absent → Nothing",
    classify(["currency"], format_vocab, maybe_binding),
    {"format": "currency", "currency": Nothing, "precision": Nothing}
)

check("maybe-003: all maybe slots absent",
    classify(["number"], format_vocab, maybe_binding),
    {"format": "number", "currency": Nothing, "precision": Nothing}
)

# ---------------------------------------------------------------------------
# Section 4: Composed types
# ---------------------------------------------------------------------------

section("4. Composed types")

composed_vocab = vocabulary(
    base_types={
        "format_name":   {"currency", "number", "percent", "date"},
        "currency_code": {"USD", "EUR", "GBP", "JPY"},
        "integer":       str.isdigit,
    },
    composed_types=[
        composed("currency_precision",
                 requires={"format_name": "currency"},
                 captures="integer"),
        composed("date_year",
                 requires={"format_name": "date"},
                 captures="integer"),
    ]
)

composed_binding = {
    "format_name":        "format",
    "currency_code":      "currency",
    "integer":            "precision",       # default
    "currency_precision": "decimals",        # override when currency
    "date_year":          "year",            # override when date
}

check("composed-001: integer captured as decimals when currency present",
    classify(["currency", "USD", "2"], composed_vocab, composed_binding),
    {"format": "currency", "currency": "USD", "decimals": "2"}
)

check("composed-002: integer falls to default when number present",
    classify(["number", "USD", "2"], composed_vocab, composed_binding),
    {"format": "number", "currency": "USD", "precision": "2"}
)

check("composed-003: date captures integer as year",
    classify(["date", "2026"], composed_vocab, composed_binding),
    {"format": "date", "year": "2026"}
)

check("composed-004: order independence with composed types",
    classify(["2", "currency", "USD"], composed_vocab, composed_binding),
    classify(["currency", "USD", "2"], composed_vocab, composed_binding),
)

# ---------------------------------------------------------------------------
# Section 5: Rejections
# ---------------------------------------------------------------------------

section("5. Rejections")

result = classify(["currency", "XYZ"], format_vocab, format_binding)
check("rejection-001: unrecognized token",
    result.get("_rejections", [{}])[0].get("reason"),
    "unrecognized"
)
check("rejection-002: recognized tokens still bound despite rejection",
    result.get("format"),
    "currency"
)

result = classify(["currency", ""], format_vocab, format_binding)
check("rejection-003: empty token reason",
    result.get("_rejections", [{}])[0].get("reason"),
    "empty_token"
)

result = classify(["currency", None], format_vocab, format_binding)
check("rejection-004: null token reason",
    result.get("_rejections", [{}])[0].get("reason"),
    "null_token"
)

result = classify(["currency", "USD", "USD"], format_vocab, format_binding)
check("rejection-005: duplicate slot",
    result.get("_rejections", [{}])[0].get("reason"),
    "duplicate_slot"
)

# ---------------------------------------------------------------------------
# Section 6: Faults
# ---------------------------------------------------------------------------

section("6. Faults")

result = classify([42], format_vocab, format_binding)
check("fault-001: non-string token produces fault",
    result.get("_fault", {}).get("code"),
    "non_string_token"
)

throwing_vocab = vocabulary({
    "bad_predicate": lambda s: int(s) > 0,   # throws on non-numeric
})
result = classify(["hello"], throwing_vocab)
check("fault-002: throwing predicate produces fault",
    result.get("_fault", {}).get("code"),
    "predicate_error"
)

# ---------------------------------------------------------------------------
# Section 7: Reserved words
# ---------------------------------------------------------------------------

section("7. Reserved words")

try:
    bad_vocab = vocabulary({"my_type": {"manifest", "USD"}})
    check("reserved-001: framework reserved word rejected at construction",
          False, True)   # should not reach here
except ValueError as e:
    check("reserved-001: framework reserved word rejected at construction",
          "manifest" in str(e), True)

try:
    bad_vocab = vocabulary({"my_type": {"class", "USD"}})
    check("reserved-002: cross-language reserved word rejected",
          False, True)
except ValueError as e:
    check("reserved-002: cross-language reserved word rejected",
          "class" in str(e), True)

# ---------------------------------------------------------------------------
# Section 8: Empty token list
# ---------------------------------------------------------------------------

section("8. Edge cases")

result = classify([], format_vocab, format_binding)
check("edge-001: empty token list produces missing_required rejections",
    any(r.get("reason") == "missing_required"
        for r in result.get("_rejections", [])),
    True
)

check("edge-002: case sensitivity — USD does not match usd",
    classify(["usd"], format_vocab, format_binding),
    {"_rejections": [{"token": "usd", "reason": "unrecognized"}]}
)

check("edge-003: internal whitespace preserved",
    classify(["New York"], vocabulary({"place": {"New York", "Los Angeles"}})),
    {"place": "New York"}
)

# ---------------------------------------------------------------------------
# Section 9: Vocabulary merge
# ---------------------------------------------------------------------------

section("9. Vocabulary merge")

vocab_a = vocabulary({"format_name": {"currency", "number"}})
vocab_b = vocabulary({"style_name":  {"short", "long"}})
vocab_c = vocab_a | vocab_b

check("merge-001: merged vocabulary classifies from both",
    classify(["currency", "short"], vocab_c),
    {"format_name": "currency", "style_name": "short"}
)

try:
    vocab_d = vocabulary({"format_name": {"percent"}})
    _ = vocab_a | vocab_d   # name collision
    check("merge-002: name collision raises error", False, True)
except ValueError:
    check("merge-002: name collision raises error", True, True)

try:
    vocab_e = vocabulary({"other_name": {"currency"}})  # value collision
    _ = vocab_a | vocab_e
    check("merge-003: value collision raises error", False, True)
except ValueError:
    check("merge-003: value collision raises error", True, True)

# ---------------------------------------------------------------------------
# Section 10: Scale — 10,000 types
# ---------------------------------------------------------------------------

import time
import uuid

section("10. Scale (10,000 types)")

N = 10_000

# Build a vocabulary with N unique set-based types, each with one unique value
large_vocab_dict = {f"type_{i}": {f"value_{i}"} for i in range(N)}
large_vocab = vocabulary(large_vocab_dict)

# Build matching auto-binding
large_binding = {f"type_{i}": f"slot_{i}" for i in range(N)}

# Time: classify a single token against a 10,000-type vocabulary
t0 = time.perf_counter()
result = classify(["value_9999"], large_vocab, large_binding)
t1 = time.perf_counter()
single_ms = (t1 - t0) * 1000

check("scale-001: correct classification in 10k-type vocab",
    result.get("slot_9999"),
    "value_9999"
)
check("scale-002: no rejections in 10k-type vocab",
    "_rejections" not in result,
    True
)
print(f"          classify() against 10,000 types: {single_ms:.3f}ms")

# Time: classify 1,000 tokens, each from a different type in the 10k vocab
tokens_1000 = [f"value_{i}" for i in range(1000)]
t0 = time.perf_counter()
result_1000 = classify(tokens_1000, large_vocab, large_binding)
t1 = time.perf_counter()
batch_ms = (t1 - t0) * 1000

check("scale-003: 1,000-token batch all bound correctly",
    result_1000.get("slot_0") == "value_0" and result_1000.get("slot_999") == "value_999",
    True
)
check("scale-004: no rejections in 1,000-token batch",
    "_rejections" not in result_1000,
    True
)
print(f"          classify() 1,000 tokens against 10,000 types: {batch_ms:.3f}ms")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

total = passed + failed
print(f"\n{'=' * 50}")
print(f"Results: {passed}/{total} passed", end="")
if failed:
    print(f"  ({failed} failed)")
    print(f"Failed: {', '.join(failures)}")
else:
    print("  — all tests passed")
print(f"{'=' * 50}")

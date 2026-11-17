"""RED probe for honest-test.supplied_cases — the external-lookup value resolver (.hd, spec section 3.6).

supplied_cases looks one predicate up in the resolved SuppliedConfig the reader
handed in. When the config holds an entry it returns that entry's valid and invalid
lists with missing false; when it holds no entry it returns empty lists with missing
true — the case the runner turns into a missing_supplied_values warning rather than
passing over. It reads no file and returns pure data.
honest-test has no code yet, so importing honest_test fails — the correct red state.
"""

from honest_test import supplied_cases


def probe_supplied_cases():
    """supplied_cases copies a present entry's valid and invalid values with missing
    false, and reports missing true with empty lists when the predicate has no entry."""
    bad = []

    # A resolved SuppliedConfig: a map from predicate name to its SuppliedEntry.
    config = {
        "customer_id": {
            "valid": ["CUST-00001", "CUST-99999"],
            "invalid": ["CUST-0", "cust-00001", "CUST-AAAAA"],
            "strategy": "supplied_only",
        },
        "order_amount": {
            "valid": [],
            "invalid": [],
            "strategy": "fibonacci",
        },
    }

    present = supplied_cases("customer_id", config)
    if not isinstance(present, dict):
        bad.append(f"supplied_cases returned {type(present).__name__}, expected a SuppliedCases dict")
    else:
        if present.get("valid") != ["CUST-00001", "CUST-99999"]:
            bad.append(f"customer_id valid = {present.get('valid')!r}, expected the two supplied values")
        if present.get("invalid") != ["CUST-0", "cust-00001", "CUST-AAAAA"]:
            bad.append(f"customer_id invalid = {present.get('invalid')!r}, expected the three supplied values")
        if present.get("missing") is not False:
            bad.append(f"customer_id missing = {present.get('missing')!r}, expected False for a present entry")

    # A present entry carrying empty lists is still present — missing stays false.
    empty_entry = supplied_cases("order_amount", config)
    if empty_entry.get("valid") != [] or empty_entry.get("invalid") != []:
        bad.append(f"order_amount lists should be empty: {empty_entry!r}")
    if empty_entry.get("missing") is not False:
        bad.append(f"order_amount missing = {empty_entry.get('missing')!r}, expected False: the entry exists")

    # A predicate absent from the config: missing true, both lists empty.
    absent = supplied_cases("unknown_predicate", config)
    if absent.get("missing") is not True:
        bad.append(f"an absent predicate must report missing True: {absent!r}")
    if absent.get("valid") != [] or absent.get("invalid") != []:
        bad.append(f"an absent predicate must carry empty lists: {absent!r}")

    # The empty config: every lookup is missing.
    none_at_all = supplied_cases("anything", {})
    if none_at_all.get("missing") is not True:
        bad.append(f"an empty config must report missing True: {none_at_all!r}")
    if none_at_all.get("valid") != [] or none_at_all.get("invalid") != []:
        bad.append(f"an empty config must carry empty lists: {none_at_all!r}")

    return bad


def run():
    failures = probe_supplied_cases()
    for message in failures:
        print(f"FAIL supplied_cases: {message}")
    print(f"supplied_cases probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)

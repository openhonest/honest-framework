"""RED probe for honest-test.resolve_supplied_config — the pure config resolver (.hd, sections 3.6, 10).

resolve_supplied_config reshapes the decoded honest-test.toml table into a
SuppliedConfig: a map from each predicate name to its SuppliedEntry — the
predicate's valid list, its invalid list, and its strategy (supplied_only or
fibonacci). It reads no world; the input is the plain table read_config returned.
honest-test has no code yet, so importing honest_test fails — the correct red state.
"""

from honest_test import resolve_supplied_config


def probe_resolve_supplied_config():
    """resolve_supplied_config builds one SuppliedEntry per declared predicate,
    carries only the predicates sub-table, and returns the empty map when none are
    declared."""
    bad = []

    # The decoded section-10 table: predicates live under the "predicates" key;
    # runner/coverage/bdd are not predicates and must not leak into the result.
    table = {
        "runner": {"parallel": True, "timeout_seconds": 30},
        "predicates": {
            "customer_id": {
                "valid": ["CUST-00001", "CUST-99999"],
                "invalid": ["CUST-0", "cust-00001"],
                "strategy": "supplied_only",
            },
            "order_amount": {
                "strategy": "fibonacci",
                "limit": 1000000000,
                "negative": False,
            },
        },
        "coverage": {"minimum_vocabulary": 100},
        "bdd": {"features_dir": "features/"},
    }

    got = resolve_supplied_config(table)
    if not isinstance(got, dict):
        bad.append(f"resolve_supplied_config returned {type(got).__name__}, expected a SuppliedConfig dict")
        return bad

    for leaked in ("runner", "coverage", "bdd"):
        if leaked in got:
            bad.append(f"a non-predicate section {leaked!r} leaked into the SuppliedConfig: {got!r}")

    if "customer_id" not in got:
        bad.append(f"customer_id should resolve to an entry, got keys {sorted(got)}")
    else:
        entry = got["customer_id"]
        if entry.get("valid") != ["CUST-00001", "CUST-99999"]:
            bad.append(f"customer_id valid = {entry.get('valid')!r}, expected the two supplied values")
        if entry.get("invalid") != ["CUST-0", "cust-00001"]:
            bad.append(f"customer_id invalid = {entry.get('invalid')!r}, expected the two supplied values")
        if entry.get("strategy") != "supplied_only":
            bad.append(f"customer_id strategy = {entry.get('strategy')!r}, expected 'supplied_only'")

    if "order_amount" not in got:
        bad.append(f"order_amount should resolve to an entry, got keys {sorted(got)}")
    else:
        entry = got["order_amount"]
        if entry.get("strategy") != "fibonacci":
            bad.append(f"order_amount strategy = {entry.get('strategy')!r}, expected 'fibonacci'")
        # A fibonacci entry supplies no valid/invalid lists, so they default empty.
        if entry.get("valid") != []:
            bad.append(f"order_amount valid = {entry.get('valid')!r}, expected [] when none supplied")
        if entry.get("invalid") != []:
            bad.append(f"order_amount invalid = {entry.get('invalid')!r}, expected [] when none supplied")

    # A table with no predicates resolves to the empty map.
    if resolve_supplied_config({}) != {}:
        bad.append("an empty table should resolve to the empty SuppliedConfig")
    if resolve_supplied_config({"runner": {"parallel": True}, "predicates": {}}) != {}:
        bad.append("a table declaring no predicates should resolve to the empty SuppliedConfig")

    return bad


def run():
    failures = probe_resolve_supplied_config()
    for message in failures:
        print(f"FAIL resolve_supplied_config: {message}")
    print(f"resolve_supplied_config probe: {'PASS' if not failures else str(len(failures)) + ' failed'}")
    return failures


if __name__ == "__main__":
    raise SystemExit(1 if run() else 0)

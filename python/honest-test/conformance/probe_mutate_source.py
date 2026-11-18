"""honest-test conformance: mutate_source — the mechanical mutant generator.

mutate_source(source) parses the source with tree-sitter and applies the seven
change kinds to every place each fits, returning one Mutant {location, change_kind,
original, replacement} per change; it returns a honest-test Fault {problem, remedy}
when the source does not parse (spec §9.6). This probe runs it on a tiny real source
carrying a comparison and a number, then on unparseable source.

No classes, no mocks. It calls the real honest_test.mutate_source and reads results
by shape — a Fault is the honest-test record carrying problem and remedy, a bare
union with no envelope.
"""

from honest_parse import walk

from honest_test import mutate_source, parse_source

_MUTATION_KINDS = {
    "comparison_swap",
    "number_shift",
    "condition_flip",
    "constant_replace",
    "result_swap",
    "line_removal",
    "membership_change",
}


def _is_fault(value):
    return isinstance(value, dict) and "problem" in value and "remedy" in value


def probe_mutate_source():
    bad = []

    # A tiny parseable source with a comparison operator and a numeric literal.
    source = "def recognize(s):\n    return len(s) < 10\n"
    mutants = mutate_source(source)
    if _is_fault(mutants):
        return [f"mutate_source should mutate parseable source, got a Fault {mutants!r}"]
    if not isinstance(mutants, list):
        return [f"mutate_source returned {mutants!r}, expected a list of Mutant"]
    if not mutants:
        bad.append("mutate_source returned no mutants for source carrying a comparison and a number")

    for m in mutants:
        if not isinstance(m, dict):
            bad.append(f"a mutant is not a record: {m!r}")
            continue
        for field in ("location", "change_kind", "original", "replacement"):
            if field not in m:
                bad.append(f"a mutant is missing the {field} field: {m!r}")
        if m.get("change_kind") not in _MUTATION_KINDS:
            bad.append(f"a mutant carries an unknown change_kind {m.get('change_kind')!r}")

    swaps = [m for m in mutants if m.get("change_kind") == "comparison_swap" and m.get("original") == "<"]
    if not swaps:
        bad.append("mutate_source did not produce a comparison_swap of the '<' operator")
    elif swaps[0].get("replacement") != "<=":
        bad.append(f"the '<' comparison_swap replaces with {swaps[0].get('replacement')!r}, expected '<='")

    shifts = [m for m in mutants if m.get("change_kind") == "number_shift" and m.get("original") == "10"]
    if not shifts:
        bad.append("mutate_source did not produce a number_shift of the literal '10'")
    elif shifts[0].get("replacement") not in ("11", "9"):
        bad.append(f"the '10' number_shift replaces with {shifts[0].get('replacement')!r}, expected '11' or '9'")

    # Every mutant's location must be a valid splice coordinate: a span key the harness
    # builds over the parse tree, mapping back to the node whose text is the mutant's
    # original (spec §9.6, the mutant location is the tree-sitter node's span).
    tree = parse_source(source)
    spans = {f"{n.start_point}-{n.end_point}": n.text.decode("utf-8") for n in walk(tree)}
    for m in mutants:
        location = m.get("location")
        if location not in spans:
            bad.append(f"mutant location {location!r} is not a span key the harness can splice at; original {m.get('original')!r}")
        elif spans[location] != m.get("original"):
            bad.append(f"mutant location {location!r} maps to {spans[location]!r}, not the mutant's original {m.get('original')!r}")

    # Unparseable source yields a Fault, never a mutant list.
    broken = mutate_source("def ((((\n")
    if not _is_fault(broken):
        bad.append(f"mutate_source should return a Fault on unparseable source, got {broken!r}")

    return bad


def run():
    messages = probe_mutate_source()
    if messages:
        print(f"FAIL HTEST-probe [mutate_source]: {messages}")
    print(f"mutate_source: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())

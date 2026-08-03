"""The orchestrating runner (section 11): assemble the generators, execution, honesty checks,
and state-machine tests into one result record per chain, then render the section-11 report.

This module holds the pure engine and the pure report formatter. Discovery (walking `src/`,
reading honest-check's declaration graph, and binding the declared names to the live honest_type
objects the primitives execute) and the CLI boundary are layered on top of these functions.

The honesty verdict a chain carries is `True`, `False`, or - for idempotency of a chain that
contains a boundary link - the string `"exempt"` (section 4.3): a chain that touches the world
is not expected to repeat. Rendering dispatches on the record's `kind` through a table, never a
branch, so a new record kind is a row, not an `if`.
"""

import copy

from honest_check.declgraph import extract_chains, extract_state_machines, resolve_aliases
from honest_parse import parse_python
from honest_type.chains import link_meta
from honest_type.recognizers import is_bounded, members, recognize

from honest_test.adversarial import adversarial_neighbours
from honest_test.coverage_data import (
    build_coverage,
    chain_coverage,
    honesty_coverage,
    state_machine_coverage,
    vocabulary_coverage,
    write_coverage,
)
from honest_test.enumeration import enumerate_sets
from honest_test.honesty import (
    detect_mutation,
    test_chain_contracts,
    verify_idempotency,
    verify_purity,
)
from honest_test.statemachine import (
    test_adversarial_transitions,
    test_invalid_transitions,
    test_valid_transitions,
)


def _is_boundary(link) -> bool:
    """Whether a link declared itself a boundary (section 4.4): I/O is expected, honesty exempt."""
    return link_meta(link)["boundary"]


def _adversarial_rejections(vocab) -> dict:
    """Every near-miss of every bounded member, and how many the recognizers reject (sections 3.5,
    4.4). Unbounded (predicate) types have no members to perturb and are skipped."""
    pairs = [
        (neighbour, recognizer)
        for recognizer in vocab["base_types"].values()
        if is_bounded(recognizer)
        for member in members(recognizer)
        for neighbour in adversarial_neighbours(member)
    ]
    rejected = sum(1 for neighbour, recognizer in pairs if not recognize(neighbour, recognizer))
    return {"total": len(pairs), "rejected": rejected}


def _idempotency(links, manifests, boundary) -> object:
    """The chain's idempotency verdict (section 4.3): exempt when a boundary link is present,
    otherwise True only if every enumerated manifest repeats."""
    if boundary:
        return "exempt"
    return all(verify_idempotency(links, copy.deepcopy(manifest)) is None for manifest in manifests)


def _link_checks(link, manifests) -> dict:
    """Per-link honesty on a fresh copy of every manifest (sections 4.1, 4.2): the link is pure and
    does not mutate its input. A fresh copy per probe is required because verify_purity runs the link
    and detect_mutation mutates by design - a shared manifest would let one probe hide another."""
    return {
        "purity": all(verify_purity(link, copy.deepcopy(manifest)) is None for manifest in manifests),
        "mutation": all(detect_mutation(link, copy.deepcopy(manifest)) is None for manifest in manifests),
    }


def _honesty(links, manifests) -> dict:
    """The chain's honesty record (section 4): the purity and mutation verdicts aggregated over every
    non-boundary link, the chain-level idempotency verdict, the names of the declared boundary links,
    and the names of the non-boundary links verified honest (pure and mutation-free on every case)."""
    boundary = [link.__name__ for link in links if _is_boundary(link)]
    checks = {link.__name__: _link_checks(link, manifests) for link in links if not _is_boundary(link)}
    return {
        "purity": all(c["purity"] for c in checks.values()),
        "mutation": all(c["mutation"] for c in checks.values()),
        "idempotency": _idempotency(links, manifests, boundary),
        "boundary": boundary,
        "honest": [name for name, c in checks.items() if c["purity"] and c["mutation"]],
    }


def _first_fault(links, manifest):
    """The index of the first link that returns a non-ok result - a fault exit (section 9.2) - or None
    if the whole chain runs clean. Runs on the given manifest; the caller passes a fresh copy so one
    chain run cannot dirty the next."""
    current = manifest
    for index, link in enumerate(links):
        result = link(current)
        if "ok" not in result:
            return index
        current = result["ok"]
    return None


def run_chain(name, links, vocab, bind) -> dict:
    """Verify one chain (sections 3, 4): enumerate every manifest the vocabulary allows, run each
    through the chain, perturb every member into near-misses, and check the links are honest. The
    returned record is data the report and the coverage document both read."""
    manifests = enumerate_sets(vocab, bind)
    faults = [_first_fault(links, copy.deepcopy(manifest)) for manifest in manifests]
    passed = sum(1 for fault in faults if fault is None)
    adversarial = _adversarial_rejections(vocab)
    return {
        "name": name,
        "kind": "chain",
        "link_count": len(links),
        "vocab_terms": [(n, len(members(r))) for n, r in vocab["base_types"].items() if is_bounded(r)],
        "permutations": len(manifests),
        "passed": passed,
        "fault_paths_exercised": len({fault for fault in faults if fault is not None}),
        "adversarial_total": adversarial["total"],
        "adversarial_rejected": adversarial["rejected"],
        "honesty": _honesty(links, manifests),
        "contracts_ok": not test_chain_contracts(links),
    }


def _adversarial_tokens(machine) -> int:
    """The near-miss state and event tokens test_adversarial_transitions perturbs (section 5.3): every
    state's neighbours (perturbed only when there is an event to pair them with) plus every event's
    neighbours. States are always non-empty (the initial state is declared), so events are the guard."""
    state_tokens = sum(len(adversarial_neighbours(state)) for state in machine["states"]) if machine["events"] else 0
    event_tokens = sum(len(adversarial_neighbours(event)) for event in machine["events"])
    return state_tokens + event_tokens


def run_state_machine(name, machine) -> dict:
    """Verify one state machine (sections 5.1-5.3): every declared transition must fire correctly,
    every undeclared (state, event) pair must fault, and every near-miss state/event token must be
    rejected. The undeclared count is the full grid minus the declared table, the same denominator
    test_invalid_transitions walks; the adversarial count is the perturbed-token total."""
    valid_total = len(machine["transitions"])
    invalid_total = len(machine["states"]) * len(machine["events"]) - valid_total
    adversarial_total = _adversarial_tokens(machine)
    return {
        "name": name,
        "kind": "state_machine",
        "states": len(machine["states"]),
        "events": len(machine["events"]),
        "transitions": valid_total,
        "valid_total": valid_total,
        "valid_passed": valid_total - len(test_valid_transitions(machine)),
        "invalid_total": invalid_total,
        "invalid_rejected": invalid_total - len(test_invalid_transitions(machine)),
        "adversarial_total": adversarial_total,
        "adversarial_rejected": adversarial_total - len(test_adversarial_transitions(machine)),
    }


def compute_totals(results) -> dict:
    """Fold the per-chain records into the report footer's totals (section 11). State machines carry
    no permutations, links, or BDD, so those totals sum over the chain records only."""
    chains = [r for r in results if r["kind"] == "chain"]
    permutations = sum(r["permutations"] for r in chains)
    passed = sum(r["passed"] for r in chains)
    bdd = [r["bdd"] for r in chains if "bdd" in r]
    return {
        "permutations": permutations,
        "failures": permutations - passed,
        "adversarial": sum(r["adversarial_total"] for r in chains),
        "adversarial_rejected": sum(r["adversarial_rejected"] for r in chains),
        "total_links": sum(r["link_count"] for r in chains),
        "honest_links": sum(len(r["honesty"]["honest"]) for r in chains),
        "boundary_links": sum(len(r["honesty"]["boundary"]) for r in chains),
        "bdd_passed": sum(b["passed"] for b in bdd),
        "bdd_total": sum(b["total"] for b in bdd),
    }


_MARK = {True: "✓", False: "✗"}
_IDEMPOTENCY = {True: "✓", False: "✗", "exempt": "n/a (boundary)"}


def _format_vocab_line(terms) -> str:
    return " × ".join(f"{name}({count})" for name, count in terms)


def _format_honesty(honesty) -> str:
    marks = f"purity {_MARK[honesty['purity']]}  mutation {_MARK[honesty['mutation']]}  idempotency {_IDEMPOTENCY[honesty['idempotency']]}"
    boundary = honesty["boundary"]
    if not boundary:
        return marks
    return marks + f"  boundary: {', '.join(boundary)} (expected)"


def _format_chain(result) -> list:
    passed, total = result["passed"], result["permutations"]
    base = [
        f"{result['name']} ({result['link_count']} links)",
        f"  Vocabulary: {_format_vocab_line(result['vocab_terms'])}",
        f"  Permutations: {total:,}",
        f"  Running... {passed:,}/{total:,} {'PASS' if passed == total else 'FAIL'}",
        f"  Adversarial: {result['adversarial_total']:,} near-miss inputs, {result['adversarial_rejected']:,} rejected",
        f"  Honesty: {_format_honesty(result['honesty'])}",
        f"  Chain contracts: {'all outputs accepted by downstream links' if result['contracts_ok'] else 'BROKEN'}",
    ]
    bdd = result.get("bdd")
    if bdd is None:
        return base
    return base + [f"  BDD: {bdd['feature']} — {bdd['passed']}/{bdd['total']} scenarios PASS"]


def _format_state_machine(result) -> list:
    return [
        f"{result['name']} (state machine)",
        f"  States: {result['states']}, Events: {result['events']}, Transitions: {result['transitions']}",
        f"  Valid transitions: {result['valid_passed']}/{result['valid_total']} PASS",
        f"  Invalid transitions: {result['invalid_rejected']}/{result['invalid_total']} correctly rejected",
        f"  Adversarial: {result['adversarial_total']:,} near-miss state/event tokens, {result['adversarial_rejected']:,} rejected",
    ]


_BLOCK = {"chain": _format_chain, "state_machine": _format_state_machine}


def _header(results) -> list:
    chains = [r for r in results if r["kind"] == "chain"]
    links = sum(r["link_count"] for r in chains)
    vocabularies = sum(1 for r in chains if r["vocab_terms"])
    return [
        "honest-test v0.1.0",
        "Scanning src/ for chains...",
        "",
        f"Found {len(chains)} chains, {links} links, {vocabularies} vocabularies",
        "",
    ]


def _footer(results) -> list:
    totals = compute_totals(results)
    return [
        "",
        f"Total: {totals['permutations']:,} permutations tested, {totals['failures']} failures",
        f"       {totals['adversarial']:,} adversarial inputs, {totals['adversarial_rejected']:,} rejected",
        f"       {totals['honest_links']}/{totals['total_links']} links verified honest ({totals['boundary_links']} declared boundary)",
        f"       {totals['bdd_passed']}/{totals['bdd_total']} BDD scenarios PASS",
    ]


def format_report(results) -> str:
    """Render the section-11 report from the per-chain records: a header with the discovery counts,
    one block per record (dispatched on its kind), and the totals footer."""
    blocks = [line for result in results for line in _BLOCK[result["kind"]](result) + [""]]
    return "\n".join(_header(results) + blocks + _footer(results))


# --------------------------------------------------------------------------- discovery + orchestration
#
# Discovery reads honest-check's declaration graph (section 1.1) for the chains and state machines a
# source file declares, then binds those declared names to the live honest_type objects the primitives
# execute - the static graph says what exists, the imported module provides what runs. Every boundary
# (the directory walk, the file read, the module import, the feature runner, the report emit, the
# coverage write, the clock) is injected, so this layer is pure and the CLI is the only real I/O.


def discover(src_dir, walk, read, import_module) -> dict:
    """Find every testable construct under src_dir. For each source file: parse it, read the chain and
    state-machine declarations, then import the module and bind the declared names to live objects. A
    chain whose first link declares no accepts vocabulary cannot be enumerated (section 3.1); it is
    surfaced by name in `untestable`, never silently dropped."""
    chains = []
    machines = []
    untestable = []
    for path in walk(src_dir):
        source = read(path)
        root = parse_python(source).root_node
        aliases = resolve_aliases(root, source)
        module = import_module(path)
        for decl in extract_chains(root, source, aliases):
            links = [getattr(module, link_name) for link_name in decl["links"]]
            vocab = link_meta(links[0])["accepts"]
            if vocab is None:
                untestable.append(decl["name"])
                continue
            chains.append({"name": decl["name"], "links": links, "vocab": vocab, "bind": link_meta(links[0])["binds"]})
        for decl in extract_state_machines(root, source, aliases):
            machines.append({"name": decl["name"], "machine": getattr(module, decl["name"])})
    return {"chains": chains, "machines": machines, "untestable": untestable}


def _run_discovered_chain(chain, run_feature) -> dict:
    """Verify a discovered chain and attach its BDD result when the developer wrote a feature for it
    (run_feature returns the feature's scenario counts, or None when there is no feature)."""
    result = run_chain(chain["name"], chain["links"], chain["vocab"], chain["bind"])
    bdd = run_feature(chain)
    if bdd is None:
        return result
    return {**result, "bdd": bdd}


def _chain_ok(result) -> bool:
    """A chain passes when every permutation ran clean, every near-miss was rejected, the contracts
    hold, and the non-boundary links are honest (idempotency exempt for a boundary chain is not a
    failure)."""
    honesty = result["honesty"]
    return (
        result["passed"] == result["permutations"]
        and result["adversarial_rejected"] == result["adversarial_total"]
        and result["contracts_ok"]
        and honesty["purity"]
        and honesty["mutation"]
        and honesty["idempotency"] is not False
    )


def all_passed(results) -> bool:
    """Whether the whole run passes (section 11): every chain is clean and honest, every developer
    feature's scenarios all pass, and every state machine rejected every near-miss token. A validly
    constructed machine fires its declared transitions and faults its undeclared pairs by
    construction, so those are not re-checked here."""
    chains = [r for r in results if r["kind"] == "chain"]
    machines = [r for r in results if r["kind"] == "state_machine"]
    return (
        all(_chain_ok(r) for r in chains)
        and all(r["adversarial_rejected"] == r["adversarial_total"] for r in machines)
        and all(r["bdd"]["passed"] == r["bdd"]["total"] for r in chains if "bdd" in r)
    )


def _coverage(results, timestamp) -> dict:
    """The section-9.5 coverage document from the run's records. Vocabulary coverage is complete by
    construction - every enumerated case is run; honesty coverage is measured per chain; chain coverage
    counts the fault exits observed during enumeration (deliberate fault-path generation, section 9.2,
    is separate work); state-machine coverage is the transitions that fired."""
    chains = [r for r in results if r["kind"] == "chain"]
    machines = [r for r in results if r["kind"] == "state_machine"]
    return build_coverage(
        {r["name"]: vocabulary_coverage(r["permutations"], r["permutations"]) for r in chains},
        {r["name"]: chain_coverage(r["link_count"], r["fault_paths_exercised"]) for r in chains},
        {r["name"]: honesty_coverage(r["link_count"], len(r["honesty"]["honest"]), len(r["honesty"]["boundary"])) for r in chains},
        {r["name"]: state_machine_coverage(r["transitions"], r["valid_passed"]) for r in machines},
        timestamp,
    )


def run_suite(src_dir, walk, read, import_module, run_feature, emit, write, timestamp) -> int:
    """Scan src_dir, verify every discovered chain and state machine, emit the section-11 report, name
    any chain skipped for want of a vocabulary, write the section-9.5 coverage document, and return 0
    only when the whole run passes. Every boundary is injected; this is pure orchestration."""
    discovered = discover(src_dir, walk, read, import_module)
    chain_results = [_run_discovered_chain(chain, run_feature) for chain in discovered["chains"]]
    machine_results = [run_state_machine(m["name"], m["machine"]) for m in discovered["machines"]]
    results = chain_results + machine_results
    emit(format_report(results))
    for name in discovered["untestable"]:
        emit(f"skipped (no input vocabulary declared): {name}")
    write_coverage(_coverage(results, timestamp), "coverage.json", write)
    return 0 if all_passed(results) else 1

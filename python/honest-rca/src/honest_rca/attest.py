"""The attestation, its bound, and its validation (spec §7-§8). The attestation is the negative
claim — terminates at X; no upstream factor identified under this evidence and method — never a
positive "X is the root". validate_attestation is the poka-yoke: a claim missing its evidence hash,
method version, terminus, or bound (or a design root with no poka-yoke) is not a weaker attestation,
it is not a valid attestation at all, so fake RCA has no representation."""

from honest_type import fault

from honest_rca.types import RELATION_SIGNAL
from honest_rca.trace import terminus


def terminus_is_design_root(item):
    """True when the terminus item names a bug category — a design decision (missing invariant,
    unowned mutation, unbounded input), not an instance (§8)."""
    return bool(item["category"])


def bound(evidence, graph):
    """Compute the stated limit from fact (§7.1). outside_evidence lists item ids the evidence
    references but does not contain; invisible_to_method lists recorded relations no enabled signal
    grounded. An empty bound is present and stated, never omitted."""
    items = evidence["items"]
    item_ids = {item["id"] for item in items}
    recorded = {
        (item["id"], effect, RELATION_SIGNAL[relation])
        for item in items
        for relation in RELATION_SIGNAL
        for effect in item[relation]
    }
    grounded = {(edge["cause"], edge["effect"], edge["signal"]) for edge in graph["edges"]}
    referenced = {effect for _cause, effect, _signal in recorded}
    invisible = sorted(recorded - grounded)
    return {
        "outside_evidence": sorted(referenced - item_ids),
        "invisible_to_method": [{"cause": cause, "effect": effect} for cause, effect, _signal in invisible],
    }


def attest(symptom, evidence, method, graph, chain, poka_yoke):
    """Assemble the bounded-completeness statement (§7): the terminus, the chain, the marked edges the
    chain relied on, the computed bound, the terminus item's category, and the reproducibility keys."""
    end = terminus(chain)
    end_item = next((item for item in evidence["items"] if item["id"] == end), None)
    category = end_item["category"] if end_item is not None else ""
    chain_edges = {(chain[index + 1], chain[index]) for index in range(len(chain) - 1)}
    marked_edges = [edge for edge in graph["edges"] if (edge["cause"], edge["effect"]) in chain_edges and edge["marked"]]
    return {
        "symptom": symptom["id"],
        "evidence_hash": evidence["hash"],
        "method_version": method["version"],
        "terminus": end,
        "chain": list(chain),
        "marked_edges": marked_edges,
        "bound": bound(evidence, graph),
        "category": category,
        "poka_yoke": poka_yoke,
    }


def validate_attestation(attestation):
    """Refuse any attestation that is not a well-formed bounded-completeness statement (§7). One fault
    per omission; an attestation with no faults is a real RCA, and fake RCA cannot pass."""
    faults = []
    if not attestation["evidence_hash"]:
        faults.append(fault("missing_evidence_hash", "Attestation names no evidence set; a bounded-completeness claim must state the evidence it searched.", "server"))
    if not attestation["method_version"]:
        faults.append(fault("missing_method_version", "Attestation names no method version; the claim is reproducible only against a versioned method.", "server"))
    if not attestation["terminus"]:
        faults.append(fault("missing_terminus", "Attestation has no terminus; the chain must terminate at a node past which the bounded search finds nothing.", "server"))
    if "bound" not in attestation:
        faults.append(fault("missing_bound", "Attestation states no bound; a positive claim hides its bound, an honest one wears it on its face.", "server"))
    if attestation["category"] and not attestation["poka_yoke"]:
        faults.append(fault("missing_poka_yoke", "Attestation terminates at a design root but names no poka-yoke; a fix that cannot name the category it eliminates has not reached a design root.", "server"))
    return faults

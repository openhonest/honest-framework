"""The pure functions of honest-rca (spec sections 3-8). Every function is pure: it reads no file,
clock, environment or network, and nothing raises. The one error-returning function,
validate_attestation, returns its faults as data in a list; honest-type's Fault is referenced by name
and never redeclared here.

The decision core imports nothing of the world at runtime: evidence arrives as EvidenceItem records
assembled at a sibling's boundary, and each function is pure over that data. The world reaches these
functions only by importing them (the .hd entry rows); honest-rca has no door of its own.
"""

import hashlib
import json

from honest_type import fault


def evidence_hash(items):
    """A pure, order-independent, change-sensitive digest of the evidence items (spec section 3). Each
    item is serialized to a canonical JSON string with its keys sorted; the per-item strings are then
    sorted and joined, so the same set of items in any order yields the same hash, while any change to
    an item's id, kind, ref, or a relation changes at least one string and so changes the digest. It
    reads no world and raises nothing."""
    serialized = sorted(json.dumps(item, sort_keys=True) for item in items)
    return hashlib.sha256("\n".join(serialized).encode("utf-8")).hexdigest()


def evidence_set(items):
    """Assemble a bounded evidence set and stamp its hash (spec section 3). The items are already read
    from the world at the boundary — evidence_set does no collection itself — so it simply holds them
    and records evidence_hash(items) as the reproducibility key. Pure; raises nothing."""
    return {"items": items, "hash": evidence_hash(items)}


def relation_flows_to(item):
    """The dataflow detector: the item's flows_to relation — the downstream ids whose value depends on
    this item, grounded from parse's data-flow facts (spec section 5). Empty where the relation is
    absent, which yields no edge. Pure; raises nothing."""
    return item["flows_to"]


def relation_controls(item):
    """The controlflow detector: the item's controls relation — the downstream ids whose execution this
    item's branch gates, grounded from parse's control-flow facts (spec section 5). Empty where the
    relation is absent, which yields no edge. Pure; raises nothing."""
    return item["controls"]


def relation_changed_with(item):
    """The change_correlation detector: the item's changed_with relation — the downstream ids that
    changed together with this item, grounded from history's blame/change sets (spec section 5). Empty
    where the relation is absent, which yields no edge. Pure; raises nothing."""
    return item["changed_with"]


def relation_precedes(item):
    """The temporal detector: the item's precedes relation — the downstream ids this item strictly
    happens-before in the event log, grounded from observe's log ordering (spec section 5). Empty where
    the relation is absent, which yields no edge. Pure; raises nothing."""
    return item["precedes"]


# signal_edges' dispatch table (spec section 5). Each deterministic signal kind maps to the detector
# that reads the one EvidenceItem relation field that kind grounds edges on: dataflow->flows_to,
# controlflow->controls, change_correlation->changed_with, temporal->precedes. Adding or changing a
# signal's source is editing this table, never editing control flow. judgment is absent from the table
# because it grounds no edges of its own.
by_signal = {
    "dataflow": relation_flows_to,
    "controlflow": relation_controls,
    "change_correlation": relation_changed_with,
    "temporal": relation_precedes,
}


def signal_edges(evidence, kind):
    """Build the grounded edges for one signal kind (spec section 5). It dispatches on kind through
    by_signal to pick the relation detector, applies that detector to each item, and emits one
    CausalEdge per downstream id the relation names — cause the item's id, effect the downstream id,
    signal the kind, marked false (a grounded edge is a recorded fact). An absent relation produces no
    edge. judgment is the one SIGNAL_KINDS word the table does not carry: it grounds no edges of its
    own, so it yields the empty list rather than a silent miss. Pure; raises nothing."""
    if kind not in by_signal:
        return []  # judgment is the SIGNAL_KINDS word absent from the table; it grounds no edges
    detector = by_signal[kind]

    def edges_from(item):
        return [
            {"cause": item["id"], "effect": downstream, "signal": kind, "marked": False}
            for downstream in detector(item)
        ]

    return [edge for item in evidence["items"] for edge in edges_from(item)]


def causal_graph(evidence, method, judgments):
    """Build the causal graph by applying each enabled signal's detector to E, then adding the supplied
    judgments only when judgment is enabled (spec section 5). For each kind in method.signals it calls
    signal_edges(evidence, kind) and collects the grounded edges (judgment yields none of its own); it
    then appends the supplied marked judgments exactly when 'judgment' is in method.signals, so an edge
    whose signal is not enabled is not built. The nodes are the evidence items' ids. Pure; raises
    nothing."""
    grounded = [
        edge
        for kind in method["signals"]
        for edge in signal_edges(evidence, kind)
    ]
    enabled_judgments = judgments if "judgment" in method["signals"] else []
    return {
        "nodes": [item["id"] for item in evidence["items"]],
        "edges": grounded + enabled_judgments,
    }


def trace(graph, symptom):
    """Follow the graph upstream from the symptom's site, cause by cause, to a fixpoint (spec section
    6). The upstream causes of a node N are the causes of edges whose effect is N. The traversal is
    deterministic and terminating: it never revisits a node, so a cycle terminates at its entry, and
    the returned chain runs from the site to the terminus — the node with no unvisited upstream cause.
    When the site has no upstream edge at all, the chain is the site alone. Pure; raises nothing."""
    def next_upstream(node, visited):
        causes = [
            edge["cause"]
            for edge in graph["edges"]
            if edge["effect"] == node and edge["cause"] not in visited
        ]
        return causes[0] if causes else ""

    chain = [symptom["site"]]
    seen = {symptom["site"]}
    upstream = next_upstream(symptom["site"], seen)
    while upstream != "":
        chain.append(upstream)
        seen.add(upstream)
        upstream = next_upstream(upstream, seen)
    return chain


def terminus(chain):
    """The last node of a non-empty chain, the terminus X (spec section 6) — not 'the root', but the
    node past which this bounded search finds nothing. When the chain is the site alone, the terminus
    is that site. Pure; raises nothing."""
    return chain[-1]


def bound(evidence, graph):
    """Derive the stated limit from fact, never asserted (spec section 7.1). outside_evidence is the
    set of item ids the evidence's relations reference but that are not themselves items in E — a cause
    may lie in one of them. invisible_to_method is the set of referenced edges that no enabled signal
    grounded — a cause may hide in a signal M did not run, each rendered as a 'cause->effect' string.
    Both lists are always present; an empty bound is a stated empty bound. Pure; raises nothing."""
    item_ids = {item["id"] for item in evidence["items"]}
    referenced_pairs = [
        (item["id"], downstream)
        for item in evidence["items"]
        for field in ("flows_to", "controls", "changed_with", "precedes")
        for downstream in item[field]
    ]
    grounded_pairs = {(edge["cause"], edge["effect"]) for edge in graph["edges"]}
    outside = {downstream for _cause, downstream in referenced_pairs if downstream not in item_ids}
    invisible = {
        f"{cause}->{effect}"
        for cause, effect in referenced_pairs
        if (cause, effect) not in grounded_pairs
    }
    return {"outside_evidence": sorted(outside), "invisible_to_method": sorted(invisible)}


def attest(symptom, evidence, method, graph, chain, poka_yoke):
    """Assemble the negative claim (spec sections 2, 7, 8). It reads the evidence's hash into
    evidence_hash and the method's version into method_version, reads the marked judgment edges from
    the graph, calls terminus(chain) for the terminus id and bound(evidence, graph) for the Bound,
    copies the terminus item's category (empty for an ordinary terminus, the named bug category for a
    design root), and copies the supplied poka_yoke. The record has no field asserting 'X is the root'.
    Pure; raises nothing — a construction failure is caught by validate_attestation, not by a raise."""
    terminus_id = terminus(chain)
    categories = {item["id"]: item["category"] for item in evidence["items"]}
    category = categories[terminus_id] if terminus_id in categories else ""
    return {
        "symptom": symptom,
        "evidence_hash": evidence["hash"],
        "method_version": method["version"],
        "terminus": terminus_id,
        "chain": chain,
        "marked_edges": [edge for edge in graph["edges"] if edge["marked"]],
        "bound": bound(evidence, graph),
        "category": category,
        "poka_yoke": poka_yoke,
    }


def validate_attestation(attestation):
    """The poka-yoke guard: the runtime check that an attestation is a well-formed bounded-completeness
    statement (spec sections 7, 8). It returns one honest-type Fault per missing element and an empty
    list for a real RCA: missing_evidence_hash when the hash is empty, missing_method_version when the
    version is empty, missing_terminus when there is no terminus, missing_bound when the bound is
    absent (an empty-but-present bound is valid), and missing_poka_yoke when the terminus is a design
    root — a non-empty category — but no poka_yoke is named. Pure; returns faults as data, never
    raising."""
    bound_present = "bound" in attestation and attestation["bound"] is not None
    checks = [
        (attestation["evidence_hash"] == "", "missing_evidence_hash",
         "the attestation carries no evidence hash; a bounded-completeness claim must name the "
         "EvidenceSet it searched so a re-run can prove the same evidence was used"),
        (attestation["method_version"] == "", "missing_method_version",
         "the attestation carries no method version; a bounded-completeness claim must name the "
         "Method it used so a re-run is compared against the same method"),
        (attestation["terminus"] == "", "missing_terminus",
         "the attestation names no terminus; the bounded search must state the node past which it "
         "found nothing upstream"),
        (not bound_present, "missing_bound",
         "the attestation states no bound; an empty bound is present and valid, but an absent bound "
         "hides what may lie outside the evidence or be invisible to the method"),
        (attestation["category"] != "" and attestation["poka_yoke"] == "", "missing_poka_yoke",
         "the terminus is a design root (it carries a bug category) but the attestation names no "
         "poka-yoke; a fix that cannot name the category it eliminates has not reached a design root"),
    ]
    return [
        fault(code=code, message=message, category="client", results=[],
              detail={"field": code.removeprefix("missing_")})
        for failed, code, message in checks
        if failed
    ]


def terminus_is_design_root(item):
    """Tell whether a terminus item is a design root rather than an instance (spec section 8): true
    exactly when the item carries a non-empty category — a design decision (a missing invariant, an
    unowned mutation, an unbounded input, a bug category) rather than a single instance. A pure
    predicate; reads no world and raises nothing."""
    return item["category"] != ""

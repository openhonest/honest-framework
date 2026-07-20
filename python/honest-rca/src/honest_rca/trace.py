"""Fixpoint traversal (spec §6): follow the graph upstream from the symptom's site, cause by cause,
until a node has no upstream cause. Because causal_graph already scoped the graph to the edges M
grounds or enables, that fixpoint is exactly the terminus X — the node past which this bounded search
finds nothing. The traversal never revisits a node, so a cycle terminates at its entry."""


def trace(graph, symptom):
    """The ordered chain from the symptom's site to the terminus (§6). Deterministic (upstream causes
    are taken in sorted order) and terminating (no node is revisited)."""

    def upstream(node, seen):
        return sorted({edge["cause"] for edge in graph["edges"] if edge["effect"] == node and edge["cause"] not in seen})

    current = symptom["site"]
    chain = [current]
    visited = {current}
    causes = upstream(current, visited)
    while causes:
        current = causes[0]
        visited.add(current)
        chain.append(current)
        causes = upstream(current, visited)
    return chain


def terminus(chain):
    """The last node of the chain — the terminus X — or empty for an empty chain (§6)."""
    return chain[-1] if chain else ""

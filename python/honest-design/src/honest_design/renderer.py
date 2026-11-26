"""The static renderer: Module IR -> the 4-column diagram, as data.

Pure and deterministic — the same IR renders the same diagram every time, with no interaction and no
external state. It places each function in its derived column (input boundary, orchestrators, pure
functions, output boundary), marks boundary functions with their declared side-effect targets, and
draws each chain as left-to-right edges between adjacent links. The diagram is structured data (the
layout); serializing it to SVG for display is a thin, separate presentation step. Drawing a given
`.hd` is open; drawing *into* `.hd` (the interactive producer) is the commercial line.
"""

from honest_design import ir

_COLUMN_TITLES = ("Input boundary", "Orchestrators", "Pure functions", "Output boundary")


def _node(fn) -> ir.Node:
    return {"name": fn["name"], "role": fn["role"], "effects": [se["target"] for se in fn["side_effects"]]}


def _column(module, index) -> ir.Column:
    functions = filter(lambda function: function["column"] == index, module["functions"])
    return {
        "index": index,
        "title": _COLUMN_TITLES[index - 1],
        "nodes": [_node(function) for function in functions],
    }


def _edges(module) -> list[ir.Edge]:
    return [
        {"chain": c["name"], "src": src, "dst": dst}
        for c in module["chains"]
        for src, dst in zip(c["links"], c["links"][1:])
    ]


def render(module) -> ir.Diagram:
    """Render a module's IR into the 4-column diagram (data)."""
    return {
        "module": module["name"],
        "columns": [_column(module, index) for index in (1, 2, 3, 4)],
        "edges": _edges(module),
    }

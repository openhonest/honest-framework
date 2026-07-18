"""The language-agnostic intermediate representation honest-design's reader produces.

Plain data (TypedDicts): the single value the validator, the diagram renderer, and honest-check's
conformance tier all read, so none of them touches the tree-sitter grammar. A `.hd` file folds to a
Document; a module file fills `modules`, a workspace file fills `rules` / `actors` / `flows`.

A type is a union of atoms (`Manifest | Fault` -> two atoms); an atom is a name with generic
arguments, each argument itself a type, so `dict<str, set<str>>` nests. The `column` on a function
is derived from its role, not authored.
"""

from typing import TypedDict


class Atom(TypedDict):
    name: str
    args: list  # list[Type]; a Type is list[Atom]


class Field(TypedDict):
    name: str
    type: list  # Type = list[Atom]


class Param(TypedDict):
    name: str
    type: list  # Type = list[Atom]


class SideEffect(TypedDict):
    direction: str  # "reads" | "writes" | "reads_writes"
    target: str


class Function(TypedDict):
    name: str
    role: str  # "boundary_in" | "orchestrator" | "fn" | "boundary_out"
    params: list  # list[Param]
    ret: list  # Type = list[Atom]
    side_effects: list  # list[SideEffect]
    invokes: list  # list[str]
    raises: list  # list[str]
    column: int


class TypeDecl(TypedDict):
    name: str
    record: list  # list[Field]; empty when the type is an alias
    alias: list  # Type = list[Atom]; empty when the type is a record


class SetMember(TypedDict):
    value: str
    description: str  # "" when the member has none


class SetDecl(TypedDict):
    name: str
    members: list  # list[SetMember]


class Vocabulary(TypedDict):
    name: str
    sets: list  # list[str]


class DispatchEntry(TypedDict):
    key: str
    handler: str


class Dispatch(TypedDict):
    name: str
    entries: list  # list[DispatchEntry]


class Example(TypedDict):
    name: str
    chain: str
    text: str


class Chain(TypedDict):
    name: str
    links: list  # list[str]


class Route(TypedDict):
    method: str
    path: str
    target: str


class Entry(TypedDict):
    callsite: str
    target: str


class HtmlAttr(TypedDict):
    attr: str
    description: str


class Module(TypedDict):
    name: str
    layer: str
    types: list
    sets: list
    vocabularies: list
    dispatches: list
    examples: list
    functions: list
    chains: list
    routes: list
    entries: list
    html_attrs: list


class Rule(TypedDict):
    id: str
    module: str  # "" for a global rule
    statement: str


class Actor(TypedDict):
    name: str


class Flow(TypedDict):
    name: str
    group: str
    steps: list  # list[str]


class Document(TypedDict):
    modules: list  # list[Module]
    rules: list  # list[Rule]
    actors: list  # list[Actor]
    flows: list  # list[Flow]


# --- the rendered 4-column diagram ---------------------------------------------


class Node(TypedDict):
    name: str
    role: str
    effects: list  # list[str]; a boundary's side_effect targets, empty otherwise


class Column(TypedDict):
    index: int  # 1..4
    title: str
    nodes: list  # list[Node], in declared order


class Edge(TypedDict):
    chain: str
    src: str
    dst: str


class Diagram(TypedDict):
    module: str
    columns: list  # list[Column], the four columns left to right
    edges: list  # list[Edge], each adjacent link pair of every chain

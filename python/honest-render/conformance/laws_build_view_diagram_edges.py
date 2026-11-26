# scenario: build_view uses supplied diagram edges for the chain layout
# inherits: hd=python/honest-render/honest-render.hd::build_view -> feature=specs/features/honest-render.feature::build_view uses supplied diagram edges for the chain layout
import re

from honest_design import read_hd, render
from honest_render import build_view

_DECLARATION = """module edge-fixture
  layer foundation
  note "declaration details are copied from this module"
  inputs = {}
  outputs = {}
  boundary_in fn dispatch : () -> int invokes preferred note "opens the declared path"
  orchestrator fn preferred : () -> int note "details of the declared preferred function"
  orchestrator fn alternate : () -> int note "details of the declared alternate function"
  chain pipeline = dispatch -> preferred
  entry "import edge_fixture" -> dispatch
"""

_DIAGRAM_DECLARATION = """module edge-fixture
  layer foundation
  note "only the layout comes from this module"
  inputs = {}
  outputs = {}
  boundary_in fn dispatch : () -> int invokes alternate note "opens the alternate path"
  orchestrator fn alternate : () -> int note "fixture for alternate placement"
  orchestrator fn preferred : () -> int note "fixture for preferred placement"
  chain pipeline = dispatch -> alternate
  entry "import edge_fixture" -> dispatch
"""


def _tokens(section):
    """Extract prose and table-cell tokens without requiring an edge serialization."""
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", " ".join(section["lines"] + [
        cell for row in section["rows"] for cell in row
    ]))


def probe_build_view_diagram_edges():
    """Use supplied Diagram placement and edges while keeping Module details."""
    module = read_hd(_DECLARATION)["ok"]["modules"][0]
    layout_module = read_hd(_DIAGRAM_DECLARATION)["ok"]["modules"][0]
    diagram = render(layout_module)
    view = build_view(module, diagram)
    sections = {section["kind"]: section for section in view["sections"]}
    chain = sections.get("chains", {"lines": [], "rows": []})
    functions = sections.get("functions", {"lines": [], "rows": []})
    chain_tokens = _tokens(chain)
    failures = []
    if "pipeline" not in chain_tokens or "dispatch" not in chain_tokens or "alternate" not in chain_tokens:
        failures.append(f"chain layout does not show the supplied pipeline dispatch-to-alternate edge: {chain!r}")
    elif chain_tokens.index("dispatch") >= chain_tokens.index("alternate"):
        failures.append(f"chain layout reverses the supplied dispatch-to-alternate edge: {chain!r}")
    if "preferred" in chain_tokens:
        failures.append(f"chain layout recomputed the dispatch-to-preferred edge from Module.links: {chain!r}")
    prose = "\n".join(functions["lines"])
    alternate_signature = re.search(r"\balternate\s*:?\s*\(", prose)
    preferred_signature = re.search(r"\bpreferred\s*:?\s*\(", prose)
    if alternate_signature is None or preferred_signature is None:
        failures.append(f"function section omits Diagram-placed signatures: {functions!r}")
    elif alternate_signature.start() >= preferred_signature.start():
        failures.append(f"function section ignores supplied alternate-before-preferred placement: {functions!r}")
    if "details of the declared alternate function" not in prose or "details of the declared preferred function" not in prose:
        failures.append(f"function section did not preserve the parsed Module notes: {functions!r}")
    return failures

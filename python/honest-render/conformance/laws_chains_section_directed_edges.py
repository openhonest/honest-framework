# scenario: _chains_section keeps separate directed edges in diagram order
# inherits: hd=python/honest-render/honest-render.hd::_chains_section -> feature=specs/features/honest-render.feature::_chains_section keeps separate directed edges in diagram order
import re
from honest_design import read_hd, render
from honest_render.render import _chains_section

_SOURCE = """module chain-fixture
  layer foundation
  boundary_in fn start : () -> int note "starts the chain"
  orchestrator fn check : () -> int note "checks the chain"
  fn send : () -> int note "prepares the output"
  boundary_out fn finish : () -> int note "writes the result"
  chain dispatch = start -> check -> send -> finish
"""


def probe_chains_section_directed_edges():
    """Keep two distinct directed pairs without inventing continuity."""
    module = read_hd(_SOURCE)["ok"]["modules"][0]
    diagram = render(module)
    diagram["edges"] = [
        {"chain": "dispatch", "src": "start", "dst": "check"},
        {"chain": "dispatch", "src": "send", "dst": "finish"},
    ]
    section = _chains_section(module, diagram)
    lines = section["lines"]
    failures = []
    if section["kind"] != "chains" or section["rows"] or len(lines) != 1:
        failures.append(f"expected one chain line and no rows, got {section!r}")
        return failures
    tokens = re.findall(r"[A-Za-z_]+", lines[0])
    if tokens != ["dispatch", "start", "check", "send", "finish"]:
        failures.append(f"directed edge endpoints are outside their supplied order: {lines[0]!r}")
    for source, target in (("start", "check"), ("send", "finish")):
        if not re.search(rf"\b{source}\s*(?:->|→)\s*{target}\b", lines[0]):
            failures.append(f"chain line omits the supplied {source}-to-{target} pair: {lines[0]!r}")
    if re.search(r"\bcheck\s*(?:->|→)\s*send\b", lines[0]):
        failures.append(f"chain line invented the check-to-send edge: {lines[0]!r}")
    return failures

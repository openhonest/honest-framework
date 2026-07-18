"""honest-design - the .hd architecture-declaration read path.

Reads `.hd` source into the language-agnostic IR (`read_hd`), depending only on honest-parse. It sits
below honest-type in the build order, so it emits faults as data in the shared Result shape rather
than importing honest-type's Result. The IR is what honest-design's validator and static renderer,
and honest-check's conformance tier, consume — none of them touches the tree-sitter grammar.
"""

from honest_design.reader import read_hd
from honest_design.renderer import render
from honest_design.validator import validate
from honest_design.result import err, fault, ok

__all__ = ["read_hd", "validate", "render", "ok", "err", "fault"]

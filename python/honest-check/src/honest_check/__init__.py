"""honest-check — the pre-auto-generation verification gate of the Honest Framework.

Public surface: `check_source(source, path) -> list[Diagnostic]`.
"""

from honest_check.diagnostics import Diagnostic
from honest_check.rules import check_source

__all__ = ["Diagnostic", "check_source"]

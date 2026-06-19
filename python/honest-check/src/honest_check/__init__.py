"""honest-check — the pre-auto-generation verification gate of the Honest Framework.

Public surface:
  - `check_source(source, path) -> list[Diagnostic]`
  - `startup_check(paths, on_error, severity)` — framework startup integration (section 2.3)
"""

from honest_check.diagnostics import Diagnostic
from honest_check.rules import check_source
from honest_check.startup import HonestCheckError, startup_check

__all__ = ["Diagnostic", "check_source", "startup_check", "HonestCheckError"]

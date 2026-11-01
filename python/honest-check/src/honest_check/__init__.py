"""honest-check — the static checker enforcing the Honest Code principles.

The package surface, the five functions honest-check.hd declares. check_source
is the pure core; read_source and load_config are the filesystem-side readers;
check_paths is the orchestrator; startup_check is the development-mode startup
door, the one place HonestCheckError is raised.
"""

from honest_check.check_paths import check_paths
from honest_check.check_source import check_source
from honest_check.load_config import load_config
from honest_check.read_source import read_source
from honest_check.startup_check import HonestCheckError, startup_check
from honest_check.types import Diagnostic, RuleConfig, RuleId

__all__ = [
    "Diagnostic",
    "HonestCheckError",
    "RuleConfig",
    "RuleId",
    "check_paths",
    "check_source",
    "load_config",
    "read_source",
    "startup_check",
]

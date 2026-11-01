"""honest-check — the static checker, the honesty gate.

The eighteen declared functions of honest-check.hd, re-exported so a caller writes
`from honest_check import check_source`. Every module-level def across this package is
one of these eighteen; every other helper is nested or module-level data.
"""

from honest_check.cli import (
    HonestCheckError,
    check_paths,
    main,
    run_check,
    startup_check,
)
from honest_check.core import check_source
from honest_check.readers import (
    discover_files,
    load_config,
    load_project_config,
    read_source,
    write_report,
)
from honest_check.report import (
    enforced_rules_of,
    format_github,
    format_human,
    format_json,
    format_junit,
    parse_args,
    prepare_report,
    resolve_exit_code,
)

__all__ = [
    "HonestCheckError",
    "check_paths",
    "check_source",
    "discover_files",
    "enforced_rules_of",
    "format_github",
    "format_human",
    "format_json",
    "format_junit",
    "load_config",
    "load_project_config",
    "main",
    "parse_args",
    "prepare_report",
    "read_source",
    "resolve_exit_code",
    "run_check",
    "startup_check",
    "write_report",
]

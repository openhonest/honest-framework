"""honest-check — the static checker, the honesty gate.

The twenty-four declared functions this package publishes, re-exported so a caller writes
`from honest_check import check_source`. The five cross-module seam functions are declared
too but reached only through `import honest_check.integration_rules`, so they are not in this
surface; every module-level def across this package is one declared function, nested helpers
are nested or module-level data.

__all__ is exactly the twenty-four published declared functions, the surface HC-REF005 crosses
against the declaration. HonestCheckError is honest-check's sanctioned boundary exception,
declared in the .hd as a `raises` target rather than a `fn`, so it stays importable by name
but is not in the declared function surface __all__ publishes.
"""

from honest_check.cli import (
    HonestCheckError,
    check_paths,
    main,
    run_check,
    startup_check,
)
from honest_check.core import (
    check_auth,
    check_references,
    check_roles,
    check_source,
    cross_declaration,
    pair_source,
)
from honest_check.readers import (
    discover_files,
    load_config,
    load_project_config,
    read_declaration,
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
    "check_auth",
    "check_paths",
    "check_references",
    "check_roles",
    "check_source",
    "cross_declaration",
    "discover_files",
    "enforced_rules_of",
    "format_github",
    "format_human",
    "format_json",
    "format_junit",
    "load_config",
    "load_project_config",
    "main",
    "pair_source",
    "parse_args",
    "prepare_report",
    "read_declaration",
    "read_source",
    "resolve_exit_code",
    "run_check",
    "startup_check",
    "write_report",
]

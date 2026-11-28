"""honest-check — the static checker that enforces the Honest Code principles.

It parses application source through honest-parse and reports violations as
Diagnostics; it never runs the code it checks, and its own source is honest — no
`if` statement (every branch is a table lookup or boolean algebra), no class
declaration (the one boundary exception is built via `type()`), faults travel as
data by return, and I/O lives only at the declared readers, writers and doors.

The public surface is re-exported here so each probed function imports from the
package root, while the implementation lives in focused submodules (§3.4)."""

from .errors import HonestCheckError
from .diagnostics import NOTHING, diagnostic, fixable_rules
from .nodes import (
    call_arguments,
    called_name,
    canonical_name,
    dotted_target,
    enclosing_function,
    is_attribute_suffix,
    is_keyword_name,
    is_main_guard,
    literal_string,
    mutated_names,
    nonlocal_names,
    own_body,
    param_names,
    string_members,
    underscore_self_name,
    within_class_init,
)
from .decorators import (
    decorator_expression,
    decorator_target,
    decorators_of,
    has_decorator,
    in_non_boundary_function,
    is_boundary_decorator,
    link_declares_emits,
)
from .analysis import (
    body_has_call,
    body_statement_count,
    canonical_body,
    is_empty_default,
    is_immutable_value,
    link_is_impure,
    link_locals,
    local_function_links,
    longest_shared_run,
    module_mutable_globals,
    predicate_is_risky,
    watched,
)
from .bindings import (
    base_types_of,
    binding_keys,
    construction_maps,
    dom_collect_names,
    feature_state_flag,
    features_vocabulary,
    module_dict_literals,
    persist_write_targets,
    value_calls_collect,
    vocabulary_binding_pairs,
    vocabulary_types,
)
from .context import build_context, resolve_aliases
from .rules import apply_suppression, check_construction, check_per_file, check_source
from .report import (
    blocking_findings,
    enforced_rules_of,
    format_github,
    format_human,
    format_json,
    format_junit,
    parse_args,
    prepare_report,
    resolve_exit_code,
)
from .boundary import (
    discover_declaration,
    discover_files,
    load_config,
    load_project_config,
    pair_source,
    read_declaration,
    read_fault,
    read_format_manifest,
    read_source,
    resolve_project_config,
    resolve_rule_config,
    write_report,
)
from .orchestrate import check_paths, main, run_check, startup_check
from .crossing import check_auth, check_references, check_roles, cross_declaration
from .seams import (
    check_hc_ref006,
    check_hc_ref007,
    check_ref012,
    check_seams,
    declared_seams,
    pure_target_is_callable,
    run_seam_rules,
)

__all__ = [
    "HonestCheckError",
    "build_context",
    "check_source",
    "check_construction",
    "check_per_file",
    "apply_suppression",
    "startup_check",
    "check_paths",
    "run_check",
    "main",
    "check_seams",
    "pure_target_is_callable",
    "resolve_aliases",
]

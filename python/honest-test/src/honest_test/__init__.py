"""honest-test — the auto-generated verification layer of the Honest Framework.

honest-test derives every test case from a module's own declarations — vocabularies,
links, chains, state machines, schemas — and runs them. Three doors start it: the CLI
run (run_cli), the pytest collection hook (check_test_body), and the value-oracle engine
a sibling imports (evaluate_case). Every function the architecture declares is realized
here; the fifty-nine declared functions are the module's whole public surface, and
NOTHING names the explicit absence a Maybe field carries (it is a value, not a declared
function, so it is not part of that surface and stays out of __all__).

The architecture: honest-test.hd. The spec: specs/02-code-quality/honest-test-architecture.md.
"""

NOTHING = None

from honest_test.analyze import (
    classify_mutant_result,
    classify_predicate,
    enumerate_lengths,
    extract_predicates,
    fibonacci_sequence,
    mutate_source,
    parse_source,
    resolve_supplied_config,
    supplied_cases,
)
from honest_test.generate import (
    adversarial_neighbors,
    control_characters,
    edit_distance_1,
    encoding_variants,
    enumerate_sets,
    enumerate_test_cases,
    generate_scaffolding,
    length_extensions,
    unicode_confusables,
)
from honest_test.honesty import (
    check_gate_honesty,
    compute_expected_status,
    detect_mutation,
    test_auth_honesty,
    test_body_violations,
    test_chain_contracts,
    test_idempotency,
    verify_purity,
    verify_under_monitor,
)
from honest_test.machines import (
    test_adversarial_state_machine,
    test_invalid_transitions,
    test_valid_transitions,
)
from honest_test.persist_components import (
    enumerate_check_constraints,
    extract_css_classes,
    test_css_isolation,
    test_persist_schema_contract,
    test_route_isolation,
    test_startup_isolation,
)
from honest_test.report import (
    build_coverage_report,
    build_proof_event,
    build_run_report,
    coverage_ratio,
    render_report,
)
from honest_test.oracle import (
    compare_output,
    evaluate_case,
    resolve_call,
    run_case,
    run_resolved_call,
)
from honest_test.io_boundary import (
    check_test_body,
    emit_proof_event,
    io_monitor,
    load_under_test,
    print_report,
    read_config,
    read_source,
    read_template,
    run_body_check,
    run_cli,
    run_mutant_suite,
    run_suite,
    write_coverage,
    write_scaffolding,
)

__all__ = [
    "classify_mutant_result", "classify_predicate", "enumerate_lengths", "extract_predicates",
    "fibonacci_sequence", "mutate_source", "parse_source", "resolve_supplied_config", "supplied_cases",
    "adversarial_neighbors", "control_characters", "edit_distance_1", "encoding_variants",
    "enumerate_sets", "enumerate_test_cases", "generate_scaffolding", "length_extensions",
    "unicode_confusables",
    "check_gate_honesty", "compute_expected_status", "detect_mutation", "test_auth_honesty",
    "test_body_violations", "test_chain_contracts", "test_idempotency", "verify_purity",
    "verify_under_monitor",
    "test_adversarial_state_machine", "test_invalid_transitions", "test_valid_transitions",
    "enumerate_check_constraints", "extract_css_classes", "test_css_isolation",
    "test_persist_schema_contract", "test_route_isolation", "test_startup_isolation",
    "build_coverage_report", "build_proof_event", "build_run_report", "coverage_ratio", "render_report",
    "compare_output", "evaluate_case", "resolve_call", "run_case", "run_resolved_call",
    "check_test_body", "emit_proof_event", "io_monitor", "load_under_test", "print_report", "read_config",
    "read_source", "read_template", "run_body_check", "run_cli", "run_mutant_suite", "run_suite",
    "write_coverage", "write_scaffolding",
]

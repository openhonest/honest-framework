"""honest-test — the auto-generated verification layer of the Honest Framework.

A runner reads a module's source and declarations and turns them into every test case, with a
pure import surface of generators and honesty checks, and two doors — the CLI and pytest runner,
and the pytest collection hook that rejects a dishonest test body. The public surface below is
exactly the functions honest-test.hd declares.
"""

from honest_test.bodies import test_body_violations
from honest_test.components import (
    extract_css_classes,
    test_css_isolation,
    test_route_isolation,
    test_startup_isolation,
)
from honest_test.coverage import (
    build_coverage_report,
    build_run_report,
    coverage_ratio,
    render_report,
)
from honest_test.generators import (
    adversarial_neighbors,
    classify_predicate,
    control_characters,
    edit_distance_1,
    encoding_variants,
    enumerate_lengths,
    enumerate_sets,
    enumerate_test_cases,
    extract_predicates,
    fibonacci_sequence,
    length_extensions,
    parse_source,
    supplied_cases,
    unicode_confusables,
)
from honest_test.honesty import (
    check_gate_honesty,
    compute_expected_status,
    detect_mutation,
    test_auth_honesty,
    test_chain_contracts,
    test_idempotency,
    verify_under_monitor,
    verify_purity,
)
from honest_test.io_read import (
    load_under_test,
    read_config,
    read_source,
    resolve_supplied_config,
)
from honest_test.laws import law, verify_laws
from honest_test.mutation import classify_mutant_result, mutate_source
from honest_test.oracle import build_proof_event, evaluate_case, generate_scaffolding
from honest_test.persist import enumerate_check_constraints, test_persist_schema_contract
from honest_test.protocol import (
    assert_body_bytes,
    assert_body_html_selector,
    assert_body_json_schema,
    assert_charset,
    assert_content_type,
    assert_cookie_attribute,
    assert_cookie_max_age,
    assert_cookie_value,
    assert_header,
    assert_location,
    assert_no_header,
    assert_same_session_cookie,
    assert_status,
    assert_status_class,
)
from honest_test.request import (
    carry_cookie,
    reuse_session,
    send_request,
    with_body,
    with_content_type,
    with_cookie,
    with_header,
)
from honest_test.runner import check_test_body, run_body_check, run_cli, run_suite
from honest_test.sinks import print_report, write_coverage
from honest_test.statemachine import (
    test_adversarial_state_machine,
    test_invalid_transitions,
    test_valid_transitions,
)

__all__ = [
    "parse_source", "extract_predicates", "classify_predicate", "enumerate_lengths",
    "fibonacci_sequence", "supplied_cases", "resolve_supplied_config", "enumerate_sets",
    "enumerate_test_cases", "adversarial_neighbors", "edit_distance_1", "unicode_confusables",
    "control_characters", "length_extensions", "encoding_variants", "verify_purity",
    "detect_mutation", "test_idempotency", "verify_under_monitor",
    "test_chain_contracts", "test_auth_honesty", "compute_expected_status", "check_gate_honesty",
    "test_valid_transitions", "test_invalid_transitions", "test_adversarial_state_machine",
    "test_persist_schema_contract", "enumerate_check_constraints", "test_css_isolation",
    "test_route_isolation", "test_startup_isolation", "extract_css_classes", "coverage_ratio",
    "build_coverage_report", "build_run_report", "render_report", "mutate_source",
    "classify_mutant_result", "evaluate_case", "generate_scaffolding", "build_proof_event",
    "law", "verify_laws", "test_body_violations", "run_body_check", "check_test_body",
    "read_source", "read_config", "load_under_test", "run_suite", "run_cli",
    "print_report", "write_coverage",
    "assert_status", "assert_status_class", "assert_content_type", "assert_charset",
    "assert_header", "assert_no_header", "assert_body_bytes", "assert_body_json_schema",
    "assert_body_html_selector", "assert_cookie_value", "assert_cookie_attribute",
    "assert_cookie_max_age", "assert_location", "assert_same_session_cookie",
    "with_header", "with_cookie", "with_body", "with_content_type",
    "carry_cookie", "reuse_session", "send_request",
]

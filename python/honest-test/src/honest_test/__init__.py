"""honest-test - the auto-generated verification layer of the Honest Framework.

Unit 1 (this release): the generation engine - Set enumeration (section 3.2) and adversarial
input generation (section 3.5). Both are pure functions over a honest-type vocabulary. The
pytest plugin, predicate-strategy generation, and honesty tests follow.
"""

from honest_test.adversarial import (
    adversarial_neighbors,
    adversarial_neighbours,
    control_characters,
    edit_distance_1,
    encoding_variants,
    length_extensions,
    unicode_confusables,
)
from honest_test.authhonesty import (
    auth_expected_status,
    auth_honesty_finding,
    auth_token_classes,
    map_fault_to_http,
    test_auth_honesty,
)
from honest_test.coverage_data import (
    build_coverage,
    chain_coverage,
    honesty_coverage,
    state_machine_coverage,
    vocabulary_coverage,
    write_coverage,
)
from honest_test.mutation import enumerate_mutants, mutation_adequacy, run_mutants
from honest_test.determinism import (
    call_monitor,
    nondeterminism_finding,
    nondeterministic_watch_list,
    verify_determinism,
)
from honest_test.enumeration import enumerate_sets
from honest_test.honesty import (
    detect_mutation,
    enumerate_test_cases,
    test_chain_contracts,
    verify_idempotency,
    verify_purity,
)
from honest_test.laws import law, verify_laws
from honest_test.length import enumerate_lengths, extract_length_bounds
from honest_test.numeric import DEFAULT_LIMIT, fibonacci_sequence, numeric_values
from honest_test.predicate import classify_predicate, classify_source
from honest_test.statemachine import (
    test_adversarial_transitions,
    test_invalid_transitions,
    test_valid_transitions,
)
from honest_test.proof import PROOF_RESULTS, decide_proof, emit_proofs, proof_payload
from honest_test.supplied import load_config, supplied_for
from honest_test.value_oracle import check_oracle, run_value_case, run_value_cases

__all__ = [
    "PROOF_RESULTS",
    "proof_payload",
    "decide_proof",
    "emit_proofs",
    "check_oracle",
    "run_value_case",
    "run_value_cases",
    "enumerate_sets",
    "law",
    "verify_laws",
    "classify_source",
    "classify_predicate",
    "fibonacci_sequence",
    "numeric_values",
    "DEFAULT_LIMIT",
    "enumerate_lengths",
    "extract_length_bounds",
    "supplied_for",
    "load_config",
    "verify_purity",
    "detect_mutation",
    "verify_idempotency",
    "nondeterministic_watch_list",
    "nondeterminism_finding",
    "call_monitor",
    "verify_determinism",
    "auth_token_classes",
    "map_fault_to_http",
    "auth_expected_status",
    "auth_honesty_finding",
    "test_auth_honesty",
    "vocabulary_coverage",
    "chain_coverage",
    "honesty_coverage",
    "state_machine_coverage",
    "build_coverage",
    "write_coverage",
    "enumerate_mutants",
    "run_mutants",
    "mutation_adequacy",
    "enumerate_test_cases",
    "test_chain_contracts",
    "test_valid_transitions",
    "test_invalid_transitions",
    "test_adversarial_transitions",
    "adversarial_neighbors",
    "adversarial_neighbours",
    "edit_distance_1",
    "unicode_confusables",
    "control_characters",
    "length_extensions",
    "encoding_variants",
]

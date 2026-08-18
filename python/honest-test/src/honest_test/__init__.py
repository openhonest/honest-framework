"""honest-test - the auto-generated verification layer of the Honest Framework.

Unit 1 (this release): the generation engine - Set enumeration (section 3.2) and adversarial
input generation (section 3.5). Both are pure functions over a honest-type vocabulary. The
pytest plugin, predicate-strategy generation, and honesty tests follow.

Exports resolve on first use, not at import. The pytest plugin ships in this package, so pytest
loads it in EVERY process where honest-test is installed. An eager import here would pull the
module's whole surface, and its sibling packages with it, into every unrelated project sharing
that environment: one missing dependency anywhere below would then fail collection for all of
them. `_EXPORTS` names where each public name lives and `__getattr__` fetches it on demand
(PEP 562), so `import honest_test.pytest_plugin` costs one module rather than twenty-two.
"""

from importlib import import_module
from types import MappingProxyType

# Public name -> the module that defines it. A closed table, read by subscript: a name absent
# from it is an AttributeError naming the name, never a quietly different object.
_EXPORTS = MappingProxyType({
    "DEFAULT_LIMIT": "honest_test.numeric",
    "PROOF_RESULTS": "honest_test.proof",
    "adversarial_neighbors": "honest_test.adversarial",
    "adversarial_neighbours": "honest_test.adversarial",
    "auth_expected_status": "honest_test.authhonesty",
    "auth_honesty_finding": "honest_test.authhonesty",
    "auth_token_classes": "honest_test.authhonesty",
    "build_coverage": "honest_test.coverage_data",
    "call_monitor": "honest_test.determinism",
    "chain_coverage": "honest_test.coverage_data",
    "check_oracle": "honest_test.value_oracle",
    "classify_predicate": "honest_test.predicate",
    "classify_source": "honest_test.predicate",
    "component_classes": "honest_test.component_isolation",
    "compute_totals": "honest_test.runner",
    "control_characters": "honest_test.adversarial",
    "decide_proof": "honest_test.proof",
    "detect_mutation": "honest_test.honesty",
    "edit_distance_1": "honest_test.adversarial",
    "emit_proofs": "honest_test.proof",
    "encoding_variants": "honest_test.adversarial",
    "enumerate_lengths": "honest_test.length",
    "enumerate_mutants": "honest_test.mutation",
    "enumerate_sets": "honest_test.enumeration",
    "enumerate_test_cases": "honest_test.honesty",
    "extract_length_bounds": "honest_test.length",
    "fault_coverage": "honest_test.fault_paths",
    "fault_exits": "honest_test.fault_paths",
    "fibonacci_sequence": "honest_test.numeric",
    "format_report": "honest_test.runner",
    "function_source": "honest_test.fault_paths",
    "honesty_coverage": "honest_test.coverage_data",
    "io_finding": "honest_test.isolation",
    "io_monitor": "honest_test.isolation",
    "io_watch_list": "honest_test.isolation",
    "law": "honest_test.laws",
    "length_extensions": "honest_test.adversarial",
    "load_config": "honest_test.supplied",
    "map_fault_to_http": "honest_test.authhonesty",
    "mutation_adequacy": "honest_test.mutation",
    "nondeterminism_finding": "honest_test.determinism",
    "nondeterministic_watch_list": "honest_test.determinism",
    "numeric_values": "honest_test.numeric",
    "perturbations": "honest_test.fault_paths",
    "proof_payload": "honest_test.proof",
    "register_http_steps": "honest_test.http_steps",
    "run_chain": "honest_test.runner",
    "run_mutants": "honest_test.mutation",
    "run_state_machine": "honest_test.runner",
    "run_value_case": "honest_test.value_oracle",
    "run_value_cases": "honest_test.value_oracle",
    "scaffold_chain": "honest_test.scaffolding",
    "seam_breakers": "honest_test.fault_paths",
    "state_machine_coverage": "honest_test.coverage_data",
    "supplied_for": "honest_test.supplied",
    "test_adversarial_transitions": "honest_test.statemachine",
    "test_auth_honesty": "honest_test.authhonesty",
    "test_chain_contracts": "honest_test.honesty",
    "test_css_isolation": "honest_test.component_isolation",
    "test_invalid_transitions": "honest_test.statemachine",
    "test_route_isolation": "honest_test.component_isolation",
    "test_startup_isolation": "honest_test.component_isolation",
    "test_valid_transitions": "honest_test.statemachine",
    "unicode_confusables": "honest_test.adversarial",
    "verify_boundary_isolation": "honest_test.isolation",
    "verify_determinism": "honest_test.determinism",
    "verify_idempotency": "honest_test.honesty",
    "verify_laws": "honest_test.laws",
    "verify_purity": "honest_test.honesty",
    "verify_write": "honest_test.persist_contract",
    "vocabulary_coverage": "honest_test.coverage_data",
    "write_coverage": "honest_test.coverage_data",
})

__all__ = tuple(sorted(_EXPORTS))


def __getattr__(name):
    """Resolve a public name to its defining module on first access (PEP 562)."""
    if name not in _EXPORTS:
        raise AttributeError(f"module 'honest_test' has no attribute '{name}'")
    return getattr(import_module(_EXPORTS[name]), name)


def __dir__():
    """List the module's public names without importing any of them."""
    return sorted(_EXPORTS)

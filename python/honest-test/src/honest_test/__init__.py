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
from honest_test.enumeration import enumerate_sets
from honest_test.honesty import (
    detect_mutation,
    enumerate_test_cases,
    test_chain_contracts,
    verify_idempotency,
    verify_purity,
)
from honest_test.length import enumerate_lengths, extract_length_bounds
from honest_test.numeric import DEFAULT_LIMIT, fibonacci_sequence, numeric_values
from honest_test.predicate import classify_predicate, classify_source
from honest_test.supplied import load_config, supplied_for

__all__ = [
    "enumerate_sets",
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
    "enumerate_test_cases",
    "test_chain_contracts",
    "adversarial_neighbors",
    "adversarial_neighbours",
    "edit_distance_1",
    "unicode_confusables",
    "control_characters",
    "length_extensions",
    "encoding_variants",
]

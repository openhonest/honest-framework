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
from honest_test.numeric import DEFAULT_LIMIT, fibonacci_sequence, numeric_values
from honest_test.predicate import classify_predicate, classify_source

__all__ = [
    "enumerate_sets",
    "classify_source",
    "classify_predicate",
    "fibonacci_sequence",
    "numeric_values",
    "DEFAULT_LIMIT",
    "adversarial_neighbors",
    "adversarial_neighbours",
    "edit_distance_1",
    "unicode_confusables",
    "control_characters",
    "length_extensions",
    "encoding_variants",
]

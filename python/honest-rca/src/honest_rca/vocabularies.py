"""The three bounded vocabularies of honest-rca (spec section 2.1, .hd set declarations).

Each is a closed set of words, frozen so honest-test can enumerate it into a Cartesian product and
honest-check can treat it as a discriminant set. They are the words an evidence item's source kind, a
causal edge's signal kind, and a bound's incompleteness mode may each take. They are module-level
frozensets, never a free str.
"""

EVIDENCE_KINDS = frozenset({"code", "event", "history", "config", "deploy"})

SIGNAL_KINDS = frozenset({"dataflow", "controlflow", "change_correlation", "temporal", "judgment"})

BOUND_KINDS = frozenset({"outside_evidence", "invisible_to_method"})

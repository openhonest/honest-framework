"""The single-mutator law, precisely (section 1.1).

Every declared piece of state has exactly one mutator. A *second* mutator of the same store is legitimate
if and only if it is **honest** (it does not hide the state it mutates) and **disjoint** (it does not touch
any state another mutator already owns). Two honest, disjoint mutators never write the same declared state,
so they are not a synchronization problem; two mutators of the same declared state always are. Pure.
"""


def second_mutator_legitimate(honest, disjoint):
    """Whether a second mutator of a store is legitimate (section 1.1): only when it is both honest (does
    not hide what it mutates) and disjoint (touches no state another mutator owns). Pure."""
    return honest and disjoint

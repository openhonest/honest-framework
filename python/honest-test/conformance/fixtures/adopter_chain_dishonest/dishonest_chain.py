"""An example adopter with a broken chain join: the failing chain-contract case.

produce emits a valid manifest, but refuse rejects it with a server fault — "I cannot
handle this" — so the two links do not actually compose. The chain-contract check (§4.6)
must report at least one chain_contract failure over this chain. A server fault is the
broken-join signal; a client fault would mean bad input, not a mismatch between the links.

The two links are themselves honest (neither mutates its input), so the only failure
run_suite reports here is the contract failure, not an honesty one.
"""

from honest_type import binding, chain, fault, link, vocabulary

access = vocabulary({"action": {"create", "read"}})
bind = binding({"action": "action"})


@link(accepts=access, binds=bind)
def produce(manifest):
    """Upstream: returns a new manifest the downstream link is supposed to accept."""
    return {**manifest, "stage": "produced"}


@link(accepts=access, binds=bind)
def refuse(manifest):
    """Downstream: rejects a valid upstream output with a server fault — the broken join."""
    return fault("cannot_handle", "downstream cannot process the upstream output", "server", [], {})


broken_pipeline = chain(produce, refuse)

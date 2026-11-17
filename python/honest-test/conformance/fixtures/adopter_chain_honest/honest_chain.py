"""An example adopter with a chain whose join holds: the honest chain-contract case.

A chain is links joined end to end. The chain-contract check (§4.6) verifies that the
downstream link accepts everything the upstream link can emit. Here grant accepts every
manifest receive produces, so run_suite reports zero chain-contract failures over this
chain. honest-type's chain() stamps the ordered links on the composed value, so
load_under_test finds the chain with is_chain and recovers its pairs with chain_meta.
"""

from honest_type import binding, chain, link, vocabulary

access = vocabulary({"action": {"create", "read"}})
bind = binding({"action": "action"})


@link(accepts=access, binds=bind)
def receive(manifest):
    """Upstream: returns a new manifest marking the stage, never mutating its input."""
    return {**manifest, "stage": "received"}


@link(accepts=access, binds=bind)
def grant(manifest):
    """Downstream: accepts whatever receive emits and returns a new manifest. The join holds."""
    return {**manifest, "granted": True}


pipeline = chain(receive, grant)

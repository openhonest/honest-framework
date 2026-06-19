"""A small, honest example application: a state machine and a pure link. The driver should
find zero honesty findings here. Fixture for the discovery-driver conformance cases."""

from honest_type import link, ok, state_machine

order = state_machine(
    states={"pending", "paid", "shipped"},
    events={"pay", "ship"},
    transitions={("pending", "pay"): "paid", ("paid", "ship"): "shipped"},
    initial="pending",
)


@link()
def normalize(manifest):
    return ok({**manifest, "normalized": True})

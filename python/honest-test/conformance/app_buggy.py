"""An example application with two planted bugs: a state machine whose state names are too
similar ("on" is an adversarial neighbour of "one"), and a link that mutates its input
manifest. The driver should surface both. Fixture for the discovery-driver conformance cases.
"""

from honest_type import link, ok, state_machine

ambiguous = state_machine(
    states={"on", "one"},
    events={"go"},
    transitions={("on", "go"): "one"},
    initial="on",
)


@link()
def leaky(manifest):
    manifest["mutated"] = True  # mutates its input - dishonest
    return ok(manifest)

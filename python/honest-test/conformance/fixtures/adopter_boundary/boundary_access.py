"""An example adopter whose links must NOT be run for honesty: the skip cases.

run_suite runs the honesty checks (§4) only over a non-boundary link that declares a
vocabulary. Two kinds of link are skipped, and this fixture carries one of each:

- write_world is a boundary link: it is declared to touch the world (@link(boundary=True))
  and so may be impure. Running purity or mutation over it would wrongly fault it, and it
  carries no vocabulary to enumerate anyway.
- untyped is an ordinary link that declares no vocabulary (@link() with no accepts). There
  are no manifests to enumerate, so there is nothing to run it over.

Both must be skipped, so run_suite over this directory discovers two links and reports
zero failures — and, critically, does not crash on enumerate_sets(None). Without the
skip guard run_suite would try to enumerate a None vocabulary and raise.
"""

from honest_type import link, vocabulary

# A bounded vocabulary is present in the module, but neither link accepts it, so neither is
# run: the boundary one is exempt, the untyped one has nothing to enumerate.
access = vocabulary({"action": {"create", "read"}})


@link(boundary=True)
def write_world(manifest):
    """A boundary link: declared to touch the world, exempt from the honesty checks."""
    manifest["written"] = True
    return manifest


@link()
def untyped(manifest):
    """A non-boundary link that declares no vocabulary, so run_suite has nothing to run it over."""
    return manifest

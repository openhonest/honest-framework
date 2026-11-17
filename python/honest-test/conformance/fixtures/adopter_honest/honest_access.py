"""An example adopter module: a real, callable surface for honest-test to check.

A framework module is a pure library and declares no application links, so it gives
run_suite nothing to run the honesty checks over. An adopter does: it builds a
vocabulary and declares links that accept it, exactly the surface §4 checks exist to
verify. This module is the honest case — every link returns a new manifest and never
mutates its input, so run_suite reports zero failures over it.

It carries no .hd: the framework never imposes one on an adopter (§11.1). A link
declares its surface inline, through honest-type's @link, which load_under_test finds
with is_link and reads with link_meta.
"""

from honest_type import link, vocabulary

# Two bounded Sets. enumerate_sets turns their Cartesian product into test manifests:
# 3 actions x 2 roles = 6 cases the honesty checks run each link over.
access = vocabulary({"action": {"create", "read", "update"}, "role": {"admin", "user"}})


@link(accepts=access)
def stamp_access(manifest):
    """Honest: returns a new manifest with the grant added, leaving its input untouched."""
    return {**manifest, "granted": True}


@link(accepts=access)
def tag_action(manifest):
    """Honest: returns a new manifest naming the action, never writing the one handed in."""
    return {**manifest, "tagged": manifest["action"]}

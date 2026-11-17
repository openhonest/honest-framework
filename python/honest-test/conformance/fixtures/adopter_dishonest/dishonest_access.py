"""An example adopter module whose link is dishonest: the failing case for run_suite.

Same vocabulary as the honest adopter, but sneak_access mutates the manifest it is
handed instead of returning a new one. detect_mutation (§4.2) catches it, so run_suite
driven over this directory must report at least one failure — the proof that it runs
the honesty checks rather than reporting a blanket zero.
"""

from honest_type import link, vocabulary

access = vocabulary({"action": {"create", "read", "update"}, "role": {"admin", "user"}})


@link(accepts=access)
def sneak_access(manifest):
    """Dishonest: writes the grant into its input manifest in place, then returns it."""
    manifest["granted"] = True
    return manifest

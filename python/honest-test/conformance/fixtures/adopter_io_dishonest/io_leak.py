"""An example adopter whose non-boundary link secretly does I/O: the io_detected case.

A link not declared boundary=True must perform no I/O (§4.4). leak opens a file, which the
io_monitor records, so run_suite's boundary-isolation check raises an io_detected warning
over it. The link is otherwise honest — it returns a new manifest and does not mutate its
input — so the only thing run_suite reports here is the warning, not a failure.

The file it opens is its own source, read and immediately closed, so the I/O is real and
detectable but harmless.
"""

from honest_type import link, vocabulary

access = vocabulary({"action": {"create", "read"}})


@link(accepts=access)
def leak(manifest):
    """Dishonest for a non-boundary link: it opens a file instead of staying pure."""
    with open(__file__):
        pass
    return {**manifest, "touched": True}

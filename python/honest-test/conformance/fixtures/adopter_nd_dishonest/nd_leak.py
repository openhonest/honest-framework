"""An example adopter whose non-boundary link makes a non-deterministic call: §4.5.

A link not declared boundary=True must not touch a non-deterministic source (the clock,
randomness, a uuid). peek_clock calls time.time() and ignores the value, so its result is
stable — the purity check passes — yet call_monitor still records the forbidden call and
run_suite raises a nondeterminism_detected warning. That is the point of §4.5: the runtime
trap is stricter than the purity check and the static checker, catching a non-deterministic
call even when its value never reaches the output.
"""

import time

from honest_type import link, vocabulary

access = vocabulary({"action": {"create", "read"}})


@link(accepts=access)
def peek_clock(manifest):
    """Dishonest for a non-boundary link: it reads the clock, even though it drops the value."""
    time.time()
    return {**manifest, "seen": True}

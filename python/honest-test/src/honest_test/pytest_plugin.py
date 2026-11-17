"""The pytest11 entry-point module (section 4.8).

honest-test's collection-time verdict is check_test_body: it refuses a test body that
rebinds a call target at runtime. The verdict logic lives in the module's declared door
check_test_body (re-exported here so the entry point resolves and a host can call it).
Registering it as a pytest collection hook needs hook functions that are not part of the
module's declared fifty-nine-function surface, so the wiring is left to the host rather
than adding undeclared column-0 functions here.
"""

from honest_test import check_test_body

__all__ = ["check_test_body"]

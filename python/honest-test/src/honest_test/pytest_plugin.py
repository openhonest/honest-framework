"""The pytest entry point for honest-test (the collection-time boundary, spec section 4.8).

The pure verdict is test_body_violations and the door is check_test_body, both exercised
directly by their conformance probes. Wiring check_test_body as a hard collection gate across
every workspace package is a spoke decision, so this plugin loads cleanly and installs no
rejecting hook of its own; a spoke that wants the gate adds its collection hook here, calling
check_test_body.
"""

from honest_test.runner import check_test_body  # noqa: F401  (the door a spoke wires into its hook)

"""An example adopter with a state machine: the surface for the §5 machine checks.

A machine built with honest-type's state_machine is a value run_suite discovers by shape
and exercises exhaustively: every declared transition is applied, every undeclared pair is
refused, and every adversarial neighbor of a state or event is rejected. Driven with
honest-type's own correct `transition` runner the checks report no failures — a valid
machine cannot fail them — so the observable is the adversarial-rejection count, not a
failure. That is the exhaustive-coverage half of honest-test's job (§5).
"""

from honest_type import state_machine

order_machine = state_machine(
    {"cart", "paid", "shipped"},
    {"pay", "ship"},
    {("cart", "pay"): "paid", ("paid", "ship"): "shipped"},
    "cart",
)

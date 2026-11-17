"""`python -m honest_test [src_dir]` — the CLI door (section 11).

The host starts a run here; the module's own run_cli hands src_dir to run_suite and
returns the RunReport or a Fault. This file adds no function to the module's declared
surface — it only routes the command-line argument to the declared door.
"""

import sys

from honest_test import run_cli

if __name__ == "__main__":
    run_cli((sys.argv[1:] or ["."])[0])

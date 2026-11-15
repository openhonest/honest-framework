"""The console-script shim and module entry (§2.1). Both `python -m honest_check.cli`
and the `honest-check` script land here; entry_point hands argv to the main door and
turns its ExitCode into the process exit. The one `if __name__ == "__main__"` guard
is the single `if` HC-P001 exempts (§4.2 §HC-P001)."""

import sys

from .orchestrate import main


def entry_point():
    """Run the CLI door over the process argv and return its exit code as an int.
    main raises HonestCheckError on the declaration-read fault, which the door
    discharges as exit code 2 (§2.1)."""
    return int(main(sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(entry_point())

#!/usr/bin/env bash
# lint-all.sh — full sweep: every honest-* module must pass honest-check (the framework's
# own linter). For CI and manual full checks. The pre-commit gate uses lint-affected.sh
# (changed modules only). A module that fails its own linter is dishonest and must not land.
#
# Single honest-check invocation over all module sources: one interpreter startup, so the
# gate stays ~constant-time regardless of module count.
set -uo pipefail
cd "$(dirname "$0")"            # -> python/

shopt -s nullglob
srcdirs=(honest-*/src/*/)
if [ ${#srcdirs[@]} -eq 0 ]; then
    echo "lint-all: no honest-* module sources found under $(pwd)" >&2
    exit 2
fi

# Membership: every workspace member carries a declaration, or is exempt by name with a reason.
# A gate you leave by deleting a file is not a gate, so absence is checked before content.
echo "lint-all: every workspace member declares itself…"
if ! uv run --package honest-check python -c '
import pathlib, sys
from honest_check.declared import undeclared_members
root = pathlib.Path(__file__).parent if False else pathlib.Path(".")
members = {d.name for d in root.iterdir() if d.is_dir() and (d / "pyproject.toml").exists()}
found = {d.name for d in root.iterdir() if d.is_dir() and list(d.glob("*.hd"))}
missing = undeclared_members(members, found)
if missing:
    print("lint-all: these workspace members carry no .hd and no exemption:", ", ".join(missing), file=sys.stderr)
    print("  Write the declaration, or add the member to EXEMPT_FROM_DECLARATION with its reason.", file=sys.stderr)
    sys.exit(1)
'; then
    exit 1
fi

echo "lint-all: ${srcdirs[*]}"
if uv run --package honest-check python -m honest_check.cli "${srcdirs[@]}"; then
    echo "lint-all: all modules pass honest-check."
else
    echo "lint-all: honest-check FAILED — fix each violation listed above (every line names its" >&2
    echo "  rule id and the honest alternative), then re-run. Nothing dishonest may be committed." >&2
    exit 1
fi

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
if ! uv run --package honest-check python membership-check.py; then
    exit 1
fi

# Catalogue: the rule list the specs publish and the rules the linter emits must be the same list.
# A rule documented but never written reads as protection that is not there, which is the direction
# that misleads; three of them (HC-P008/P009/P012) sat in the tables unnoticed until this ran.
echo "lint-all: the rule catalogue matches the linter…"
if ! uv run --package honest-check python rules-check.py; then
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

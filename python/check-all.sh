#!/usr/bin/env bash
# check-all.sh — full sweep: every honest-* module must pass honest-check (the framework's
# own checker). For CI and manual full checks. The pre-commit gate uses check-affected.sh
# (changed modules only). A module that fails its own checker is dishonest and must not land.
#
# Single honest-check invocation over all module sources: one interpreter startup, so the
# gate stays ~constant-time regardless of module count.
set -uo pipefail
cd "$(dirname "$0")"            # -> python/

shopt -s nullglob
# honest-persist is slated for wholesale replacement, so the gate does not check code that is
# about to be deleted and rebuilt. Drop it from the sweep until its replacement lands.
srcdirs=()
for d in honest-*/src/*/; do
    case "$d" in honest-persist/*) continue;; esac
    srcdirs+=("$d")
done
if [ ${#srcdirs[@]} -eq 0 ]; then
    echo "check-all: no honest-* module sources found under $(pwd)" >&2
    exit 2
fi

# Membership: every workspace member carries a declaration, or is exempt by name with a reason.
# A gate you leave by deleting a file is not a gate, so absence is checked before content.
echo "check-all: every workspace member declares itself…"
if ! uv run --package honest-check python membership-check.py; then
    exit 1
fi

# Catalogue: the rule list the specs publish and the rules the checker emits must be the same list.
# A rule documented but never written reads as protection that is not there, which is the direction
# that misleads; three of them (HC-P008/P009/P012) sat in the tables unnoticed until this ran.
echo "check-all: the rule catalogue matches the checker…"
if ! uv run --package honest-check python rules-check.py; then
    exit 1
fi

echo "check-all: ${srcdirs[*]}"
if uv run --package honest-check python -m honest_check.cli "${srcdirs[@]}"; then
    echo "check-all: all modules pass honest-check."
else
    echo "check-all: honest-check FAILED — fix each violation listed above (every line names its" >&2
    echo "  rule id and the honest alternative), then re-run. Nothing dishonest may be committed." >&2
    exit 1
fi

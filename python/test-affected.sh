#!/usr/bin/env bash
# test-affected.sh — behavioral half of the gate: run the conformance suite (section 9.2)
# of each honest-* module with staged changes. The suite cases are data (source + expected
# diagnostics); the runner is one generic harness. Paired with lint-affected.sh (structural).
set -uo pipefail
cd "$(dirname "$0")"            # -> python/

staged=$(git diff --cached --name-only --diff-filter=ACM | grep -E '^python/honest-[^/]+/.*\.py$' || true)
if [ -z "$staged" ]; then
    echo "test-affected: no honest-* Python staged; nothing to test."
    exit 0
fi

mods=$(printf '%s\n' "$staged" | sed -E 's#^python/(honest-[^/]+)/.*#\1#' | sort -u)
status=0
for mod in $mods; do
    runner="$mod/conformance/run_conformance.py"
    if [ -f "$runner" ]; then
        echo "== conformance: $mod"
        uv run --package honest-check python "$runner" || status=1
    fi
done
exit $status

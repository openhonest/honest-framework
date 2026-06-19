#!/usr/bin/env bash
# test-all.sh — full behavioral sweep for CI: run every honest-* module's conformance
# suite (section 9.2). The counterpart to lint-all.sh (full structural sweep).
set -uo pipefail
cd "$(dirname "$0")"            # -> python/

shopt -s nullglob
runners=(honest-*/conformance/run_conformance.py)
if [ ${#runners[@]} -eq 0 ]; then
    echo "test-all: no conformance suites found." >&2
    exit 2
fi

status=0
for runner in "${runners[@]}"; do
    pkg=${runner%%/*}              # honest-<mod>/conformance/... -> honest-<mod>
    echo "== conformance: $runner"
    uv run --package "$pkg" python "$runner" || status=1
done
[ "$status" -eq 0 ] && echo "test-all: all conformance suites pass." || echo "test-all: conformance FAILED." >&2
exit "$status"

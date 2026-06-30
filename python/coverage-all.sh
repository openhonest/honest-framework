#!/usr/bin/env bash
# coverage-all.sh — the dogfooding gate: the behavioural circle's enforcement.
#
# Runs every module's conformance suite under branch coverage and FAILS if combined
# line+branch coverage is below 100%. 100% is the completeness oracle of the circle:
# a line no generated law or example reaches is either dead code or an unspecified
# behaviour — both are bugs. A failing conformance suite also fails the gate.
#
# This is the full sweep (all modules), the coverage counterpart to test-all.sh.
set -uo pipefail
cd "$(dirname "$0")"            # -> python/

SRC=honest_auth,honest_check,honest_errors,honest_gherkin,honest_observe,honest_parse,honest_persist,honest_test,honest_type
COV="uv run --with coverage coverage"

$COV erase
status=0
shopt -s nullglob
runners=(honest-*/conformance/run_conformance.py)
if [ ${#runners[@]} -eq 0 ]; then
    echo "coverage-all: no conformance suites found." >&2
    exit 2
fi
for runner in "${runners[@]}"; do
    if ! $COV run --append --branch --source="$SRC" "$runner" >/dev/null 2>&1; then
        mod=$(echo "$runner" | sed -E 's#(honest-[a-z]+)/.*#\1#')
        echo "coverage-all: conformance FAILED: $runner" >&2
        echo "  its output was suppressed here — run it directly to see which case failed:" >&2
        echo "    cd python && uv run --package $mod python $runner" >&2
        status=1
    fi
done

# The CLI's `if __name__ == "__main__"` entry shim only executes when the module is run
# as a script. Run it as a module under coverage so even the entry point is exercised —
# the gate then needs no source exclusions at all.
tmp=$(mktemp -d)
printf 'def add(a, b):\n    return a + b\n' > "$tmp/ok.py"
$COV run --append --branch --source="$SRC" -m honest_check.cli "$tmp/ok.py" >/dev/null 2>&1 || true
printf 'Feature: f\n\n  Scenario: s\n    Given a step\n' > "$tmp/f.feature"
$COV run --append --branch --source="$SRC" -m honest_gherkin.cli run "$tmp/f.feature" >/dev/null 2>&1 || true
rm -rf "$tmp"

if [ "$status" -ne 0 ]; then
    echo "coverage-all: a conformance suite failed — gate blocked." >&2
    exit 1
fi

if ! $COV report -m --fail-under=100; then
    echo "coverage-all: below 100% line+branch coverage — gate blocked." >&2
    echo "  see the 'Missing' column in the report above: each unreached line or branch is either" >&2
    echo "  dead code (delete it) or a behaviour nothing tests (add a conformance case for it). Then re-run." >&2
    exit 1
fi
echo "coverage-all: 100% line+branch coverage — every line is dogfooded."

# The value-oracle gate (honest-test §8.6): every module's suite.json value cases must prove. A
# module cannot run the oracle on itself (it would import its own dependant), so this is checked
# centrally here, where honest-test is available.
if ! uv run python value-check.py; then
    echo "coverage-all: value-oracle gate failed — a value case asserts the wrong output." >&2
    exit 1
fi

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

SRC=honest_alerts,honest_auth,honest_check,honest_design,honest_estimate,honest_state,honest_errors,honest_features,honest_gherkin,honest_observe,honest_page,honest_parse,honest_persist,honest_rca,honest_render,honest_test,honest_type,honest_utilities
# The whole workspace, every time. A `uv run --package X` anywhere before this trims the shared
# environment to X's closure, and then thirteen suites here failed on a missing import that had
# nothing to do with the staged change (2026-09-05). The gate must not depend on what the last
# command left installed.
COV="uv run --all-packages --with coverage coverage"

$COV erase
status=0
shopt -s nullglob
runners=(honest-*/conformance/run_conformance.py)
if [ ${#runners[@]} -eq 0 ]; then
    echo "coverage-all: no conformance suites found." >&2
    exit 2
fi
for runner in "${runners[@]}"; do
    mod=$(echo "$runner" | sed -E 's#(honest-[a-z_]+)/.*#\1#')
    pkg=${mod//-/_}
    # Only a module in the dogfooding set (SRC above) is under this gate. A module not in SRC is in
    # progress: the build order is .hd, features, red tests, then code, so its conformance is red by
    # design until the code is written. Running it here would fail the gate on a module meant to be
    # red. It joins the gate the commit its source lands and it is added to SRC, which is the one
    # place that says a module is done.
    case ",$SRC," in
        *",$pkg,"*) ;;
        *) echo "coverage-all: $mod is not in the dogfooding set yet (in progress) — skipped."; continue;;
    esac
    if ! $COV run --append --branch --source="$SRC" "$runner" >/dev/null 2>&1; then
        echo "coverage-all: conformance FAILED: $runner" >&2
        echo "  its output was suppressed here — run it directly to see which case failed:" >&2
        echo "    cd python && uv run --package $mod python $runner" >&2
        status=1
    fi
done

# Exercise the real subprocess deadline once for workspace coverage. The standalone
# probe stays outside conformance discovery so each unrelated mutant does not wait 15s.
timeout_probe=honest-test/conformance/check_run_mutant_suite_timeout.py
if ! $COV run --append --branch --source=honest_test "$timeout_probe"; then
    echo "coverage-all: the Honest Test subprocess deadline probe failed." >&2
    status=1
fi

# The CLI's `if __name__ == "__main__"` entry shim only executes when the module is run
# as a script. Run it as a module under coverage so even the entry point is exercised —
# the gate then needs no source exclusions at all.
tmp=$(mktemp -d)
printf 'def add(a, b):\n    return a + b\n' > "$tmp/ok.py"
$COV run --append --branch --source="$SRC" -m honest_check.cli "$tmp/ok.py" >/dev/null 2>&1 || true
# The __main__ error-exit path: a --declaration naming a .hd that does not exist makes
# read_declaration answer a Fault, which main discharges as HonestCheckError and the shim
# turns into exit 2. The success run above never reaches it, so drive it once here.
$COV run --append --branch --source="$SRC" -m honest_check.cli --declaration "$tmp/missing.hd" "$tmp/ok.py" >/dev/null 2>&1 || true
printf 'Feature: f\n\n  Scenario: s\n    Given a step\n' > "$tmp/f.feature"
$COV run --append --branch --source="$SRC" -m honest_gherkin.cli run "$tmp/f.feature" >/dev/null 2>&1 || true
mkdir -p "$tmp/tsrc"
# honest_test writes its report in its current directory. Keep it in the fixture directory
# and append coverage to the same data file used by the other conformance runs.
coverage_file=${COVERAGE_FILE:-.coverage}
case "$coverage_file" in /*) ;; *) coverage_file="$PWD/$coverage_file";; esac
workspace=$PWD
printf 'from honest_check.cli import entry_point\nimport honest_test.__main__\nimport honest_test.pytest_plugin\n\nassert callable(entry_point)\n' > "$tmp/import_cli_entries.py"
if ! (
    cd "$tmp" || exit 1
    export COVERAGE_FILE="$coverage_file"
    uv run --project "$workspace" --all-packages --with coverage coverage run --append --branch --source="$SRC" -m honest_test "$tmp/tsrc" &&
    uv run --project "$workspace" --all-packages --with coverage coverage run --append --branch --source="$SRC" "$tmp/import_cli_entries.py"
) >/dev/null 2>&1; then
    echo "coverage-all: a CLI or plugin entry failed." >&2
    status=1
fi
rm -rf "$tmp"

if [ "$status" -ne 0 ]; then
    echo "coverage-all: a conformance suite failed — gate blocked." >&2
    exit 1
fi

# Value cases run centrally because module runners cannot import their own dependant.
# Include their executed lines in the same workspace coverage report.
if ! $COV run --append --branch --source="$SRC" value-check.py; then
    echo "coverage-all: value-oracle gate failed — a value case asserts the wrong output." >&2
    exit 1
fi

if ! $COV report -m --fail-under=100; then
    echo "coverage-all: below 100% line+branch coverage — gate blocked." >&2
    echo "  see the 'Missing' column in the report above: each unreached line or branch is either" >&2
    echo "  dead code (delete it) or a behaviour nothing tests (add a conformance case for it). Then re-run." >&2
    exit 1
fi
echo "coverage-all: 100% line+branch coverage — every line is dogfooded."

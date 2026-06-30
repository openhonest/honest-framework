#!/usr/bin/env bash
# mutate-all.sh — the mutation-adequacy gate across every module (honest-test §9.6), the mutation
# counterpart to coverage-all.sh. Every mechanical source change must make a conformance case fail, or
# be declared equivalent with a reason in the module's set-aside registry. Slow by nature (one suite run
# per mutant); run in CI, not on every keystroke.
set -uo pipefail
cd "$(dirname "$0")"
uv run python mutate.py auth state check errors features gherkin observe parse persist test type

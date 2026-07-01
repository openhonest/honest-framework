#!/usr/bin/env bash
# The honest-DOM (JavaScript) gate. The JavaScript counterpart of the Python module gate: the same
# discipline applied through the JavaScript toolchain built in phase 1-2.
#
#   1. honest-check  — Honest Code (the structural rules honest-check enforces over JavaScript)
#   2. test + coverage — Node's built-in runner at 100% line + branch + function coverage
#
# feature-gate, conformance, and mutation are added as they land. Run from anywhere.
set -euo pipefail
root=$(git rev-parse --show-toplevel)
pkg="$root/javascript/honest-dom"

echo "lint (honest-check)…"
(cd "$root/python/honest-check" && uv run honest-check "$pkg"/src/*.js)

echo "test + 100% coverage…"
(cd "$pkg" && node --test --experimental-test-coverage \
  --test-coverage-lines=100 --test-coverage-branches=100 --test-coverage-functions=100 \
  --test-coverage-include='src/**' 'test/*.test.js')

echo "honest-dom gate: passed."

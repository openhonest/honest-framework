#!/usr/bin/env bash
# feature-gate.sh (JavaScript) — the function-point invariant for honest-DOM: every named function
# carries exactly one gherkin scenario. The JavaScript counterpart of python/feature-gate.sh.
#
# Bijection: the set of function-point names across src/*.js must equal the set of scenario subjects
# in features/honest-dom.feature (counts equal, none missing, none extra). Function points are read
# with tree-sitter (js_function_points.py), so a data `const` is never mistaken for a function.
set -uo pipefail
root=$(git rev-parse --show-toplevel)
pkg="$root/javascript/honest-dom"

funcs=$( (cd "$root/python" && uv run python "$root/javascript/js_function_points.py" "$pkg"/src/*.js) | sort )
scen=$(grep -hE '^  Scenario:' "$pkg"/features/*.feature 2>/dev/null | sed -E 's/^  Scenario: ([A-Za-z_$][A-Za-z0-9_$]*).*/\1/' | sort)

nf=$(printf '%s\n' "$funcs" | grep -c .)
ns=$(printf '%s\n' "$scen" | grep -c .)
missing=$(comm -23 <(printf '%s\n' "$funcs" | uniq) <(printf '%s\n' "$scen" | uniq))
extra=$(comm -13 <(printf '%s\n' "$funcs" | uniq) <(printf '%s\n' "$scen" | uniq))

if [ "$nf" != "$ns" ] || [ -n "$missing" ] || [ -n "$extra" ]; then
  echo "feature-gate: honest-dom — the gherkin features do not match the code ($nf functions, $ns scenarios)."
  echo "  Every function has exactly one scenario named after it: Scenario: <functionName> <plain description>"
  [ -n "$missing" ] && { echo "  ADD a scenario for each of these functions:"; printf '    %s\n' $missing; }
  [ -n "$extra" ] && { echo "  These scenarios name no function — rename or remove:"; printf '    %s\n' $extra; }
  exit 1
fi
echo "feature-gate: honest-dom OK ($nf functions = $ns scenarios)"

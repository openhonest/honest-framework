#!/usr/bin/env bash
# feature-gate.sh — the function-point invariant: every function carries exactly one gherkin
# scenario (honest-gherkin §9). The scenario count is the directly-counted FP measure, so a
# function with no scenario (or a scenario with no function) is a real defect, gated like
# dishonest code.
#
# Affected-only: checks just the modules whose source OR feature files are staged for commit —
# we only test what changed. Bijection per module: the set of function names in src/ must equal
# the set of scenario subjects across specs/features/<m>.feature and the python/<m>/features/<m>.
# feature supplement (counts equal, none missing, none extra; same-name functions in different
# files are matched by count).
set -uo pipefail
root=$(git rev-parse --show-toplevel)

staged=$(git diff --cached --name-only --diff-filter=ACM)
mods=$(printf '%s\n' "$staged" | sed -nE \
  -e 's#^python/honest-([a-z]+)/src/.*#\1#p' \
  -e 's#^python/honest-([a-z]+)/features/.*#\1#p' \
  -e 's#^specs/features/honest-([a-z]+)\.feature#\1#p' | sort -u)
[ -z "$mods" ] && exit 0

fail=0
for m in $mods; do
  src="$root/python/honest-$m/src/honest_$m"
  [ -d "$src" ] || continue   # a feature for a module with no Python source yet — nothing to bind to

  funcs=$(grep -rhoE '^(async )?def [a-z_][a-z0-9_]*' "$src" | sed -E 's/^(async )?def //' | sort)

  feat=("$root/specs/features/honest-$m.feature")
  [ -f "$root/python/honest-$m/features/honest-$m.feature" ] && feat+=("$root/python/honest-$m/features/honest-$m.feature")
  scen=$(grep -hE '^  Scenario:' "${feat[@]}" 2>/dev/null | sed -E 's/^  Scenario: ([A-Za-z_][A-Za-z0-9_]*).*/\1/' | sort)

  nf=$(printf '%s\n' "$funcs" | grep -c .)
  ns=$(printf '%s\n' "$scen" | grep -c .)
  missing=$(comm -23 <(printf '%s\n' "$funcs" | uniq) <(printf '%s\n' "$scen" | uniq))
  extra=$(comm -13 <(printf '%s\n' "$funcs" | uniq) <(printf '%s\n' "$scen" | uniq))

  if [ "$nf" != "$ns" ] || [ -n "$missing" ] || [ -n "$extra" ]; then
    fail=1
    nfeat="specs/features/honest-$m.feature"
    supp="python/honest-$m/features/honest-$m.feature"
    echo ""
    echo "feature-gate: honest-$m — the gherkin features do not match the code ($nf functions, $ns scenarios)."
    echo "  The rule: every function has exactly one scenario named after it, written as"
    echo "    Scenario: <function_name> <plain description>"
    echo "  in $nfeat (or, for host-specific behaviour, the supplement $supp)."
    if [ -n "$missing" ]; then
      echo "  ADD a scenario for each of these functions (it has none yet):"
      printf '    %s\n' $missing
    fi
    if [ -n "$extra" ]; then
      echo "  These scenarios name no function — the function was renamed or removed."
      echo "  DELETE the scenario, or correct its name to match the function:"
      printf '    %s\n' $extra
    fi
  else
    echo "feature-gate: honest-$m OK ($nf functions = $ns scenarios)"
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "" >&2
  echo "feature-gate: commit blocked — make the features above match the code, then commit again." >&2
fi
exit "$fail"

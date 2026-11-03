#!/usr/bin/env bash
# feature-gate.sh — the function-point invariant: every function carries exactly one gherkin
# scenario (honest-gherkin §9). The scenario count is the directly-counted FP measure, so a
# function written in src/ with no scenario, or a scenario that names no function anywhere, is a
# real defect, gated like dishonest code.
#
# The build order is .hd -> features -> tests -> code. A later stage may lag the earlier ones but
# must never run ahead of them, so the gate is one-directional. The allowed scenario set is the
# union of the functions the module's .hd declares and the functions its src/ defines: the .hd
# may run ahead of the code, so a scenario for a declared-but-unwritten function is legitimate,
# and a declared function with no scenario yet is the feature stage simply lagging the .hd. What
# is never allowed is code running ahead of its features (a src/ function with no scenario) or a
# scenario naming a function neither declared nor written.
#
# Affected-only: checks just the modules whose source, feature, or .hd files are staged for
# commit — we only test what changed. Per module the scenario subjects are read across
# specs/features/<m>.feature and the python/<m>/features/<m>.feature supplement.
set -uo pipefail
root=$(git rev-parse --show-toplevel)

staged=$(git diff --cached --name-only --diff-filter=ACM)
mods=$(printf '%s\n' "$staged" | sed -nE \
  -e 's#^python/honest-([a-z_]+)/src/.*#\1#p' \
  -e 's#^python/honest-([a-z_]+)/features/.*#\1#p' \
  -e 's#^python/honest-([a-z_]+)/honest-[a-z_]+\.hd#\1#p' \
  -e 's#^specs/features/honest-([a-z_]+)\.feature#\1#p' | sort -u)
[ -z "$mods" ] && exit 0

fail=0
for m in $mods; do
  src="$root/python/honest-$m/src/honest_$m"
  hd="$root/python/honest-$m/honest-$m.hd"

  # The functions written in src/ (empty while the code stage still lags).
  srcfuncs=""
  [ -d "$src" ] && srcfuncs=$(grep -rhoE '^(async )?def [a-z_][a-z0-9_]*' "$src" | sed -E 's/^(async )?def //' | sort -u)

  # The functions the .hd declares (empty if the module carries no declaration yet). The build
  # order writes the .hd first, so these may name functions the code has not written yet.
  hdfuncs=""
  [ -f "$hd" ] && hdfuncs=$(uv run --project "$root/python" --package honest-design python - "$hd" <<'PY'
import sys
from honest_design import read_hd
doc = read_hd(open(sys.argv[1]).read())
names = []
if "ok" in doc:
    for module in doc["ok"]["modules"]:
        names += [f["name"] for f in module["functions"]]
print("\n".join(sorted(set(names))))
PY
)

  [ -z "$srcfuncs" ] && [ -z "$hdfuncs" ] && continue   # nothing to bind scenarios to

  feat=("$root/specs/features/honest-$m.feature")
  [ -f "$root/python/honest-$m/features/honest-$m.feature" ] && feat+=("$root/python/honest-$m/features/honest-$m.feature")
  scen=$(grep -hE '^  Scenario:' "${feat[@]}" 2>/dev/null | sed -E 's/^  Scenario: ([A-Za-z_][A-Za-z0-9_]*).*/\1/' | sort -u)

  # The allowed scenario set is the union of the declared and the written functions.
  allowed=$(printf '%s\n%s\n' "$srcfuncs" "$hdfuncs" | grep -v '^$' | sort -u)

  # Code must not run ahead of the features: every function written in src/ needs its scenario.
  missing=$(comm -23 <(printf '%s\n' "$srcfuncs" | grep -v '^$') <(printf '%s\n' "$scen" | grep -v '^$'))
  # A scenario must name a function the .hd declares or src/ defines; one that names neither is
  # an orphan — the function was renamed or removed, or the scenario ran ahead of both stages.
  extra=$(comm -13 <(printf '%s\n' "$allowed") <(printf '%s\n' "$scen" | grep -v '^$'))

  nsrc=$(printf '%s\n' "$srcfuncs" | grep -c .)
  nhd=$(printf '%s\n' "$hdfuncs" | grep -c .)
  nscen=$(printf '%s\n' "$scen" | grep -c .)

  if [ -n "$missing" ] || [ -n "$extra" ]; then
    fail=1
    nfeat="specs/features/honest-$m.feature"
    supp="python/honest-$m/features/honest-$m.feature"
    echo ""
    echo "feature-gate: honest-$m — the gherkin features do not match the code ($nscen scenarios; $nsrc written, $nhd declared)."
    echo "  The rule: every function written in src/ has exactly one scenario named after it, as"
    echo "    Scenario: <function_name> <plain description>"
    echo "  in $nfeat (or, for host-specific behaviour, the supplement $supp). A function the .hd"
    echo "  declares but src/ has not written yet needs no scenario — the code stage may lag."
    if [ -n "$missing" ]; then
      echo "  ADD a scenario for each of these functions — it is written in src/ with none yet:"
      printf '    %s\n' $missing
    fi
    if [ -n "$extra" ]; then
      echo "  These scenarios name no declared or written function — it was renamed or removed."
      echo "  DELETE the scenario, or correct its name to match the function:"
      printf '    %s\n' $extra
    fi
  else
    echo "feature-gate: honest-$m OK ($nscen scenarios; $nsrc written, $nhd declared)"
  fi
done

if [ "$fail" -ne 0 ]; then
  echo "" >&2
  echo "feature-gate: commit blocked — make the features above match the code, then commit again." >&2
fi
exit "$fail"

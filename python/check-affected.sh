#!/usr/bin/env bash
# check-affected.sh — the honesty gate, fast path.
#
# Checks ONLY the honest-* modules with staged Python changes. honest-check is a
# structural, per-module checker: a module's honesty does not depend on another
# module's source, so unchanged modules need not be re-checked. The affected modules
# are checked in a single honest-check invocation (no per-module interpreter startup).
# For a full sweep (CI), use check-all.sh.
set -uo pipefail
cd "$(dirname "$0")"            # -> python/

staged=$(git diff --cached --name-only --diff-filter=ACM | grep -E '^python/honest-[^/]+/.*\.py$' || true)
if [ -z "$staged" ]; then
    echo "check-affected: no honest-* Python staged; nothing to check."
    exit 0
fi

# A module may carry conformance without a src/ of its own — honest-page's implementation is the
# reference app and templates, not a package — so only check the source directories that exist.
srcdirs=$(printf '%s\n' "$staged" | sed -E 's#^python/(honest-[^/]+)/.*#\1/src#' | sort -u)
# honest-persist is slated for wholesale replacement; the gate does not check code being deleted.
srcdirs=$(for d in $srcdirs; do [ "$d" = "honest-persist/src" ] && continue; [ -d "$d" ] && printf '%s ' "$d"; done)
[ -z "$srcdirs" ] && { echo "check-affected: no honest-* source staged; nothing to check."; exit 0; }
echo "check-affected: $(printf '%s ' $srcdirs)"
# shellcheck disable=SC2086  -- intentional word-split; module paths contain no spaces
uv run --package honest-check python -m honest_check.cli $srcdirs

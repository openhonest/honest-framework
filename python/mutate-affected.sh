#!/usr/bin/env bash
# mutate-affected.sh — mutation adequacy for the modules whose src is staged for commit (the mutation
# counterpart to test-affected.sh). Mirrors mutate-all.sh but scoped to staged changes.
set -uo pipefail
cd "$(dirname "$0")"
mods=$(git diff --cached --name-only --diff-filter=ACM | sed -nE 's#^python/honest-([a-z]+)/src/.*#\1#p' | sort -u)
[ -z "$mods" ] && { echo "mutate-affected: no staged module source — nothing to mutate."; exit 0; }
uv run python mutate.py $mods

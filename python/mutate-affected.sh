#!/usr/bin/env bash
# mutate-affected.sh — mutation adequacy for the staged source FILES (file-scoped). The fast
# pre-commit counterpart to mutate-all.sh: each staged python/honest-<mod>/src/.../<file>.py is
# mutated in isolation via mutate.py's "module:filename" filter, so a single-file edit mutates only
# that file rather than its whole module. (CI runs mutate-all.sh as the whole-tree backstop.)
set -uo pipefail
cd "$(dirname "$0")"
staged=$(git diff --cached --name-only --diff-filter=ACM)
args=$(printf '%s\n' "$staged" \
       | sed -nE 's#^python/honest-([a-z_]+)/src/.*/([^/]+\.py)$#\1:\2#p' | sort -u)
if [ -n "$args" ] || printf '%s\n' "$staged" | grep -qxE 'python/(mutate\.py|honest-test/conformance/check_mutation_worker_reload\.py)'; then
    uv run --all-packages python honest-test/conformance/check_mutation_worker_reload.py || exit 1
fi
[ -z "$args" ] && { echo "mutate-affected: no staged module source — nothing to mutate."; exit 0; }
uv run --all-packages python mutate.py $args

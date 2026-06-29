#!/usr/bin/env bash
# mutate-affected.sh — mutation adequacy for the staged source FILES (file-scoped). The fast
# pre-commit counterpart to mutate-all.sh: each staged python/honest-<mod>/src/.../<file>.py is
# mutated in isolation via mutate.py's "module:filename" filter, so a single-file edit mutates only
# that file rather than its whole module. (CI runs mutate-all.sh as the whole-tree backstop.)
set -uo pipefail
cd "$(dirname "$0")"
args=$(git diff --cached --name-only --diff-filter=ACM \
       | sed -nE 's#^python/honest-([a-z]+)/src/.*/([^/]+\.py)$#\1:\2#p' | sort -u)
[ -z "$args" ] && { echo "mutate-affected: no staged module source — nothing to mutate."; exit 0; }
uv run python mutate.py $args

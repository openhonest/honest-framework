#!/usr/bin/env bash
# bootstrap.sh — one-time setup after a fresh clone (idempotent; safe to re-run).
#
# Git does not run a repo's hooks until they are pointed to, so a cloned hook is inert
# until this enables it. This:
#   1. points git at the in-repo hooks (.githooks: pre-commit honesty gate + commit-msg),
#   2. makes the hook/gate scripts executable,
#   3. verifies uv is installed,
#   4. syncs the Python workspace (shared venv + lockfile).
set -euo pipefail
cd "$(dirname "$0")"

echo "bootstrap: enabling repo git hooks (.githooks)…"
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/commit-msg python/lint-all.sh python/lint-affected.sh 2>/dev/null || true

echo "bootstrap: checking uv…"
command -v uv >/dev/null 2>&1 || {
    echo "ERROR: uv not found. Install it: https://docs.astral.sh/uv/" >&2
    exit 1
}

echo "bootstrap: syncing the Python workspace (all members)…"
( cd python && uv sync --all-packages )

echo "bootstrap: done — hooks enabled, workspace synced. The honest-check gate now runs on every commit that stages python/*.py."

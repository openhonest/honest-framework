#!/usr/bin/env bash
# bootstrap.sh — one-time setup after a fresh clone (idempotent; safe to re-run).
#
# Git does not run a repo's hooks until they are pointed to, so a cloned hook is inert until
# this enables it. This:
#   1. makes sure the pre-commit honesty gate is the hook git will actually run,
#   2. makes the hook and gate scripts executable,
#   3. verifies uv is installed,
#   4. syncs the Python workspace (shared venv + lockfile).
#
# Step 1 verifies rather than asserts, and that is the point. core.hooksPath is global state
# that other tools rewrite: beads repoints it at .beads/hooks and copies this repo's hook in,
# after which .githooks/pre-commit is dead text and editing it changes nothing that runs.
# Forcing the path back would silently drop whatever the other tool installed, so this reads
# the path git will really use, checks the hook sitting there actually invokes the gate, and
# says so plainly when it does not. The bug it removes: believing you are gated because a
# gate file exists, when the gate that runs is somewhere else.
set -euo pipefail
cd "$(dirname "$0")"
root=$(pwd)

# The gate is identified by what it runs, not by where it lives. Any pre-commit hook that
# invokes lint-affected.sh is the honesty gate, wherever a tool has copied it to.
GATE_MARKER="lint-affected.sh"

chmod +x .githooks/pre-commit .githooks/commit-msg python/*.sh 2>/dev/null || true

configured=$(git config core.hooksPath || true)
if [ -z "$configured" ]; then
    echo "bootstrap: no core.hooksPath set — pointing git at .githooks…"
    git config core.hooksPath .githooks
    configured=.githooks
fi

case "$configured" in
    /*) hooks_dir="$configured" ;;
    *)  hooks_dir="$root/$configured" ;;
esac
echo "bootstrap: git runs hooks from ${hooks_dir#"$root"/}"

if [ ! -f "$hooks_dir/pre-commit" ]; then
    echo "ERROR: there is no pre-commit hook at $hooks_dir/pre-commit, so nothing gates a commit." >&2
    echo "       The gate lives in .githooks/pre-commit. Either copy it there, or run:" >&2
    echo "         git config core.hooksPath .githooks" >&2
    exit 1
fi

if ! grep -q "$GATE_MARKER" "$hooks_dir/pre-commit"; then
    echo "ERROR: $hooks_dir/pre-commit is the hook git runs, and it does not invoke the honesty" >&2
    echo "       gate ($GATE_MARKER). Commits are landing ungated." >&2
    echo "       .githooks/pre-commit holds the gate. Copy its body into the hook above," >&2
    echo "       keeping any tool-managed section, or point git back at .githooks." >&2
    exit 1
fi
echo "bootstrap: the pre-commit hook git runs does invoke the honesty gate."

# When the running hook is a copy, report whether the copy still matches the tracked gate.
# A tool-managed section (beads appends one between BEGIN/END markers) is expected and is
# not drift, so it is stripped before comparing.
if [ "$hooks_dir" != "$root/.githooks" ]; then
    running_body=$(sed '/--- BEGIN .* INTEGRATION/,$d' "$hooks_dir/pre-commit")
    if [ "$running_body" != "$(cat .githooks/pre-commit)" ]; then
        echo "bootstrap: WARNING — the running hook is a COPY of .githooks/pre-commit and the two" >&2
        echo "           have drifted. What runs is $hooks_dir/pre-commit; edits to" >&2
        echo "           .githooks/pre-commit do not change it. Compare them with:" >&2
        echo "             diff .githooks/pre-commit $hooks_dir/pre-commit" >&2
    else
        echo "bootstrap: the running hook is a copy of .githooks/pre-commit and still matches it."
        echo "           Edit .githooks/pre-commit, then re-run this script to re-check."
    fi
fi

echo "bootstrap: checking uv…"
command -v uv >/dev/null 2>&1 || {
    echo "ERROR: uv not found. Install it: https://docs.astral.sh/uv/" >&2
    exit 1
}

echo "bootstrap: syncing the Python workspace (all members)…"
( cd python && uv sync --all-packages )

echo "bootstrap: done — the gate git runs is verified, workspace synced."

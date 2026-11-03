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
# invokes check-affected.sh is the honesty gate, wherever a tool has copied it to.
GATE_MARKER="check-affected.sh"

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

# The running hook invokes the gate one of two ways: it carries the gate's body (the marker is in
# the file), or it sources the tracked gate (the marker lives in .githooks/pre-commit, which the
# running hook sources). A source is the honest arrangement — the tracked file stays the one copy,
# so an edit to it takes effect and the two cannot drift.
sources_tracked=0
if grep -Eq '^[[:space:]]*(source|\.)[[:space:]].*\.githooks/pre-commit' "$hooks_dir/pre-commit"; then
    sources_tracked=1
fi

if [ "$sources_tracked" -eq 0 ] && ! grep -q "$GATE_MARKER" "$hooks_dir/pre-commit"; then
    echo "ERROR: $hooks_dir/pre-commit is the hook git runs, and it does not invoke the honesty" >&2
    echo "       gate ($GATE_MARKER). Commits are landing ungated." >&2
    echo "       .githooks/pre-commit holds the gate. Source it from the hook above with" >&2
    echo "         source \"\$(git rev-parse --show-toplevel)/.githooks/pre-commit\"" >&2
    echo "       keeping any tool-managed section, or point git back at .githooks." >&2
    exit 1
fi
echo "bootstrap: the pre-commit hook git runs does invoke the honesty gate."

# When the running hook is elsewhere, report how it relates to the tracked gate. Sourcing it is
# ideal — there is one copy and nothing to drift. A literal copy can drift, so it is compared; a
# tool-managed section (beads appends one between BEGIN/END markers) is expected and is stripped
# before comparing.
if [ "$hooks_dir" != "$root/.githooks" ]; then
    if [ "$sources_tracked" -eq 1 ]; then
        echo "bootstrap: the running hook sources .githooks/pre-commit, so the tracked gate is the"
        echo "           single source of truth — an edit to it takes effect here and the two cannot drift."
    else
        running_body=$(sed '/--- BEGIN .* INTEGRATION/,$d' "$hooks_dir/pre-commit")
        if [ "$running_body" != "$(cat .githooks/pre-commit)" ]; then
            echo "bootstrap: WARNING — the running hook is a COPY of .githooks/pre-commit and the two" >&2
            echo "           have drifted. What runs is $hooks_dir/pre-commit; edits to" >&2
            echo "           .githooks/pre-commit do not change it. Replace the copied body (above any" >&2
            echo "           tool-managed section) with one line that sources the tracked gate:" >&2
            echo "             source \"\$(git rev-parse --show-toplevel)/.githooks/pre-commit\"" >&2
            echo "           or compare them with: diff .githooks/pre-commit $hooks_dir/pre-commit" >&2
        else
            echo "bootstrap: the running hook is a copy of .githooks/pre-commit and still matches it."
            echo "           Replace its copied body with a source line so it cannot drift; re-run to re-check."
        fi
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

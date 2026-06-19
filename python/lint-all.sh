#!/usr/bin/env bash
# lint-all.sh — the honesty gate.
#
# Every honest-* module must pass honest-check (the framework's own linter). A module
# that fails its own linter is dishonest by definition and must not land. This is the
# structural half of "Verification First"; the behavioural half (honest-test's
# auto-generated suite) wires in here once honest-test exists.
set -uo pipefail
cd "$(dirname "$0")"            # -> python/

shopt -s nullglob
status=0
found=0
for srcdir in honest-*/src/*/ ; do
    found=1
    printf '== honest-check %s\n' "$srcdir"
    if ! uv run --package honest-check python -m honest_check.cli "$srcdir"; then
        status=1
    fi
done

if [ "$found" -eq 0 ]; then
    echo "lint-all: no honest-* module sources found under $(pwd)" >&2
    exit 2
fi

if [ "$status" -eq 0 ]; then
    echo "lint-all: all modules pass honest-check."
else
    echo "lint-all: honest-check FAILED — dishonest code, commit blocked." >&2
fi
exit "$status"

#!/usr/bin/env bash
# grammar-gate.sh — a tree-sitter grammar and its generated parser move together.
#
# src/parser.c is generated from grammar.js and committed, so the package builds without the
# tree-sitter CLI. That leaves one way to lie: change grammar.js and leave parser.c behind. The
# old parser keeps parsing, the binding rebuilds from it, and every gate stays green (2026-09-02,
# when `env` was added to .hd). This gate refuses that commit. Affected-only: it looks at each
# staged grammar.js, requires the generated files to be staged with it, and, with a CLI in reach,
# regenerates into a scratch copy and diffs, so a hand-edited parser.c cannot pass either.
#
# The CLI is not required to build the package, only to change the grammar. When the grammar
# changed and no CLI can be found, the gate fails rather than skips: a gate that cannot run must
# not pass quietly.
set -uo pipefail
root=$(git rev-parse --show-toplevel)
staged=$(git diff --cached --name-only --diff-filter=ACM)
grammars=$(printf '%s\n' "$staged" | sed -nE 's#^(python/tree-sitter-[a-z-]+)/grammar\.js$#\1#p' | sort -u)
[ -z "$grammars" ] && exit 0

# One CLI, chosen the same way every time: the one on PATH, else the highest version npx has
# kept under ~/.npm/_npx from earlier runs. Two versions can generate two different parser.c
# files from one grammar, so picking by directory age would make the diff below flap.
cli=$(command -v tree-sitter 2>/dev/null || true)
if [ -z "$cli" ]; then
  cli=$(for c in "$HOME"/.npm/_npx/*/node_modules/.bin/tree-sitter; do
          [ -x "$c" ] && printf '%s %s\n' "$("$c" --version 2>/dev/null | awk '{print $2}')" "$c"
        done | sort -V | tail -1 | cut -d' ' -f2-)
fi

fail=0
for g in $grammars; do
  for generated in src/parser.c src/grammar.json src/node-types.json; do
    if ! printf '%s\n' "$staged" | grep -qx "$g/$generated"; then
      echo "grammar-gate: $g/grammar.js is staged and $g/$generated is not." >&2
      echo "  Regenerate (tree-sitter generate --abi 14, in $g) and stage the generated files with the grammar." >&2
      fail=1
    fi
  done
  if [ -z "$cli" ]; then
    echo "grammar-gate: $g/grammar.js changed and no tree-sitter CLI was found on PATH or in the npx cache," >&2
    echo "  so the generated parser cannot be checked against it. Install the CLI (see $g/README.md) and retry." >&2
    fail=1
    continue
  fi
  scratch=$(mktemp -d)
  cp -R "$root/$g/." "$scratch/"
  if ! (cd "$scratch" && "$cli" generate --abi 14 >/dev/null 2>&1); then
    echo "grammar-gate: tree-sitter generate failed on $g/grammar.js." >&2
    fail=1
  elif ! cmp -s "$scratch/src/grammar.json" "$root/$g/src/grammar.json" || ! cmp -s "$scratch/src/parser.c" "$root/$g/src/parser.c"; then
    echo "grammar-gate: $g/src is not what grammar.js generates. Regenerate it; do not edit it by hand." >&2
    fail=1
  fi
  rm -rf "$scratch"
done
exit $fail

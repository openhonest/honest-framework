#!/usr/bin/env python
"""The installed parser still reads every declaration this repository has committed.

A .hd is parsed by a compiled binding that uv rebuilds whenever src/parser.c or src/grammar.json
changes on disk. On 2026-11-18 someone laid an older copy of the repository over the working tree.
grammar.js lost 84 lines, taking note, version, inputs, outputs, store, foreign, awaited, expose and
two function roles with it. uv faithfully rebuilt the binding from the older generated parser, and
eleven committed declarations began failing with hd_syntax_error pointing at their own line. Each
file accused itself and nothing accused the parser.

Two gates already guard the grammar, and both missed it, because both key off what a commit stages.
uv's cache-keys rebuild the binding from whatever generated files sit on disk, and grammar-gate.sh
exits at once unless a grammar.js is staged. The overwrite staged nothing, so it defeated both. This
check keys off the installed parser instead, and the hook runs it on every commit.

It reads each .hd as committed at HEAD, never as it sits in the working tree. A declaration somebody
is drafting right now may well not parse yet, and that is the author's business. A declaration that
parsed when it was committed and does not parse now is the parser's.
"""

import pathlib
import subprocess
import sys

import tree_sitter_honest_hd
from honest_design import read_hd


def git(*args: str) -> str:
    """One git command's stdout, raising when git itself fails."""
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def committed_declarations() -> dict:
    """Every tracked .hd path, mapped to its text as committed at HEAD."""
    paths = git("ls-tree", "-r", "--name-only", "-z", "HEAD").split("\0")
    return {path: git("show", f"HEAD:{path}") for path in paths if path.endswith(".hd")}


def rejected(declarations: dict) -> list:
    """Each committed declaration the installed parser will not read, with the fault it raised."""
    answers = {path: read_hd(source) for path, source in declarations.items()}
    return [(path, answer["err"]["message"]) for path, answer in answers.items() if "err" in answer]


def main() -> int:
    declarations = committed_declarations()
    if not declarations:
        print("parser-check: git tracks no .hd file, so nothing here proves the parser reads anything.", file=sys.stderr)
        print("  A check that cannot reach its subject must refuse, so this is a failure, not a skip.", file=sys.stderr)
        return 1

    bad = rejected(declarations)
    if not bad:
        return 0

    binding = pathlib.Path(tree_sitter_honest_hd.__file__).parent
    print(f"parser-check: the installed .hd parser rejects {len(bad)} of {len(declarations)} committed declarations.", file=sys.stderr)
    print("  A committed declaration that no longer parses points at the parser first, not at the file.", file=sys.stderr)
    print(f"  Installed binding: {binding}", file=sys.stderr)
    print("  Check python/tree-sitter-honest-hd against HEAD (git status, git diff), restore whatever", file=sys.stderr)
    print("  moved, then rebuild it: uv sync --reinstall-package tree-sitter-honest-hd.", file=sys.stderr)
    for path, message in bad:
        print(f"    {path}: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

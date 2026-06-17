"""honest-type CLI. The only I/O-bearing module in the package.

    honest-type classify TOKEN [TOKEN ...]

Classifies tokens against a demonstration vocabulary (email / integer) and
prints the resulting manifest (or fault) as JSON. The vocabulary is built via
the Result-returning constructor; a construction fault is reported and exits 2.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from honest_type import classify, is_err, is_fault, predicate, vocabulary

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_INT_RE = re.compile(r"^-?\d+$")


def _demo_vocabulary() -> dict:
    return vocabulary({
        "email":   predicate(lambda s: bool(_EMAIL_RE.match(s))),
        "integer": predicate(lambda s: bool(_INT_RE.match(s))),
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="honest-type")
    sub = parser.add_subparsers(dest="command", required=True)

    p_classify = sub.add_parser("classify", help="Classify one or more tokens.")
    p_classify.add_argument("tokens", nargs="+", type=str)

    args = parser.parse_args(argv)
    return _COMMANDS[args.command](args)


def _cmd_classify(args: argparse.Namespace) -> int:
    vocab_result = _demo_vocabulary()
    if is_err(vocab_result):
        print(json.dumps(vocab_result["err"], indent=2), file=sys.stderr)
        return 2
    result = classify(args.tokens, vocab_result["ok"])
    print(json.dumps(result, indent=2))
    # A bare fault (server bug) exits 2; a manifest (even with rejections) exits 0.
    return 2 if is_fault(result) else 0


_COMMANDS = {
    "classify": _cmd_classify,
}


if __name__ == "__main__":
    sys.exit(main())

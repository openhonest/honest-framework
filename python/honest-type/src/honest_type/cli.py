"""honest-type CLI. The only I/O-bearing module in the package."""
from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="honest-type")
    sub = parser.add_subparsers(dest="command", required=True)

    p_classify = sub.add_parser("classify", help="Classify a token.")
    p_classify.add_argument("token", type=str)

    args = parser.parse_args(argv)
    return _COMMANDS[args.command](args)


def _cmd_classify(args: argparse.Namespace) -> int:
    # Minimal demo vocab: email / int / str-fallback.
    from honest_type import classify_token, vocabulary

    import re
    email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    int_re = re.compile(r"^-?\d+$")

    vocab = vocabulary({
        "email": lambda s: bool(email_re.match(s)),
        "int":   lambda s: bool(int_re.match(s)),
    })
    result = classify_token(args.token, vocab)
    print(json.dumps(result, indent=2))
    return 0


_COMMANDS = {
    "classify": _cmd_classify,
}


if __name__ == "__main__":
    sys.exit(main())

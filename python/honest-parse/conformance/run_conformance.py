"""honest-parse conformance runner.

Each case is data. Two kinds:
  - error: {source, expect_error} - parse the source and check whether the tree carries a
    syntax error (first_error_node), against the expectation.
  - text:  {source, expect_root_text} - the root node's text must span the whole source.
The runner parses and checks; no per-case hand-coded tests.

  uv run --package honest-parse python honest-parse/conformance/run_conformance.py
"""

import json
import sys
from pathlib import Path

from honest_parse import first_error_node, node_text, parse_python


def _check_error(case):
    root = parse_python(case["source"].encode("utf-8")).root_node
    has_error = first_error_node(root) is not None
    return has_error == case["expect_error"], f"error={has_error}"


def _check_text(case):
    source = case["source"].encode("utf-8")
    root = parse_python(source).root_node
    text = node_text(root, source)
    return text == case["expect_root_text"], f"got {text!r}"


_CHECKERS = {"error": _check_error, "text": _check_text}


def _kind(case):
    return "text" if "expect_root_text" in case else "error"


def run(suite_path):
    suite = json.loads(Path(suite_path).read_text(encoding="utf-8"))
    passed = 0
    failed = 0
    for case in suite["cases"]:
        ok, detail = _CHECKERS[_kind(case)](case)
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {case['id']} [{_kind(case)}]: {detail}")
    print(f"conformance: {passed} passed, {failed} failed, {passed + failed} total")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import laws_parse

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_parse.run()
    raise SystemExit(suite_status or laws_status)

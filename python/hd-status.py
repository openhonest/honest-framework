#!/usr/bin/env python
"""hd-status.py: the deterministic verdict on a .hd map, so no one calls it "clean" by eye.

Two roles, kept apart.

The explorer (build-map.py) SURFACES. It draws the map, finds real faults, and raises questions a
person must weigh. Its own law reserves a question for a person, so its exit code counts faults
only and a page of open questions still exits 0. That is correct for the explorer and is not a bug.

This script is the FRAMEWORK side. It reads the explorer's own answer and states one verdict that
counts BOTH faults and open questions, because "clean" is a claim about the whole page, not about
the fault count alone. The misattribution this removes: reading the explorer's fault count as a
certificate that the page is clean. The explorer surfaces; it never certifies. honest-check and the
commit gates remain the deterministic authority on whether code passes.

CLEAN requires zero faults AND zero open questions. A fault fails the exit code, because a fault is
a defect. An open question does not fail the exit code, because it is legitimate review, but it
forbids the word CLEAN and is counted in the output, so a question can never be dropped the way a
bare count hides it.
"""
import importlib.util
import sys
from pathlib import Path

EXPLORER_PATHS = (
    Path.home() / "dev/coolder/products/architecture-explorer/build-map.py",
    Path.home() / "dev/honest/ch-writers/products/architecture-explorer/build-map.py",
    Path.home() / "dev/honest/commercial-honest/products/architecture-explorer/build-map.py",
)


def load_build_map():
    found = next((p for p in EXPLORER_PATHS if p.exists()), None)
    if found is None:
        print("hd-status: explorer build-map.py not found beside the honest trees", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location("bm", found)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def status(hd_path):
    bm = load_build_map()
    path = Path(hd_path).resolve()
    drawn = bm._render_module(path)
    if "error" in drawn:
        return {"module": path.stem, "faults": 1, "questions": 0, "error": drawn["error"]}
    module = drawn["module"]
    faults = bm._findings(path, drawn)
    questions = [q for qs in bm._questions(module).values() for q in qs]
    return {"module": module["name"], "faults": len(faults), "questions": len(questions), "error": None}


def verdict(faults, questions):
    if faults:
        return "FAULTS"
    if questions:
        return "NEEDS-REVIEW"
    return "CLEAN"


def main():
    if len(sys.argv) != 2:
        print("usage: hd-status.py <module.hd>", file=sys.stderr)
        return 2
    report = status(sys.argv[1])
    word = verdict(report["faults"], report["questions"])
    print(f'{report["module"]}: {word} ({report["faults"]} fault(s), {report["questions"]} open question(s))')
    if report["error"]:
        print(f'  error: {report["error"]}', file=sys.stderr)
    return 1 if report["faults"] else 0


if __name__ == "__main__":
    sys.exit(main())

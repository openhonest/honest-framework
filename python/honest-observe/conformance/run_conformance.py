"""honest-observe conformance runner (sections 2, 3, 6).

Each case is data: a `build_event` case (envelope assembly/validation), a `matches` case
(projection filtering), or an `emit` case (the boundary, driven with a stand-in runtime). The
fold-based projection behaviour, which a data file cannot express, is in laws_ho.py.

  uv run --package honest-observe python honest-observe/conformance/run_conformance.py
"""

import asyncio
import json
import sys
from pathlib import Path

from honest_observe import build_event, emit, matches


def _check_build_event(case):
    spec = case["build_event"]
    result = build_event(**spec["args"])
    if case["expect"] == "ok":
        return "ok" in result and result["ok"] == case["expect_event"], f"got {result}"
    return "err" in result and result["err"]["code"] == case["expect_code"], f"got {result}"


def _check_matches(case):
    spec = case["matches"]
    got = matches(spec["event"], **spec.get("filters", {}))
    return got == case["expect"], f"got {got}"


class _Runtime:
    """A stand-in emit runtime (section 3): canned id/timestamp/sequence/version, an append that
    succeeds or fails per the case, recording what it was handed. Fixture - not linted."""

    def __init__(self, spec):
        self._spec = spec
        self.auth_fields = spec.get("auth_fields", [])
        self.meta_fields = spec.get("meta_fields", [])
        self.appended = []

    def event_id(self):
        return self._spec["event_id"]

    def timestamp(self):
        return self._spec["timestamp"]

    def sequence(self, aggregate_id):
        return self._spec["sequence"]

    def version(self, event_type):
        return self._spec["version"]

    async def append(self, event):
        self.appended.append(event)
        if self._spec.get("append_ok", True):
            return {"ok": {}}
        return {"err": {"code": "log_write_failed", "message": "boom", "category": "server", "detail": None}}


def _check_emit(case):
    spec = case["emit"]
    runtime = _Runtime(spec)
    result = asyncio.run(emit(spec["event_type"], spec["aggregate_type"], spec["aggregate_id"], spec["payload"], spec["context"], runtime))
    if case["expect"] == "ok":
        return "ok" in result and result["ok"]["event_id"] == case["expect_event_id"], f"got {result}"
    return "err" in result and result["err"]["code"] == case["expect_code"], f"got {result}"


_CHECKERS = {
    "build_event": _check_build_event,
    "matches": _check_matches,
    "emit": _check_emit,
}


def _kind(case):
    for kind in _CHECKERS:
        if kind in case:
            return kind
    return "matches"


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
    import laws_ho

    default = str(Path(__file__).parent / "suite.json")
    suite_status = run(sys.argv[1] if len(sys.argv) > 1 else default)
    laws_status = laws_ho.run()
    raise SystemExit(suite_status or laws_status)

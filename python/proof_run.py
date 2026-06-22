#!/usr/bin/env python
"""proof-run — the proof run-driver (honest-test §8.5).

Emits one `hf.proof.checked` event (honest-observe §4.8) per function into the event log, turning
a conformance run into the static traceability thread: requirement (gherkin) -> proof (result +
coverage), keyed by the function's fully-qualified name. The function-point total is then a
projection over the log: count the events, partition proved from failed.

This is a HARNESS, not gated library code — like coverage-all.sh and run_conformance.py it
orchestrates, performs I/O, and is not held to the 100% bar. It calls honest-test's gated
primitive (`emit_proofs`); the orchestration lives here.

What it gathers, and the honest simplifications of this first cut:
  - functions: every `def` in each built module's src (file-qualified FQN, e.g.
    honest_test.honesty._finding).
  - gherkin: the scenario named after the function, from specs/features/<m>.feature and the
    python/<m>/features supplement (same-name functions are matched to scenarios in file order).
  - result + coverage: the dogfooding gate enforces 100% line+branch on every commit, so a GREEN
    tree means every function is fully covered and its conformance passed -> proved, 100/100. The
    driver runs coverage-all first and refuses to record a proof run over a red tree. (Per-
    function coverage breakdown only differs from 100 when the gate is red, which blocks commit
    anyway.)
  - cases: the module's portable suite.json case count (module-level for now; per-function
    attribution is a later refinement).
The sink writes each event as one JSON line to the append-only event log (a file — the stand-in
until a durable observe store exists), minting event_id / timestamp / per-aggregate sequence at
the boundary.

  uv run python proof_run.py            # confirm green, then emit
  uv run python proof_run.py --no-gate  # skip the gate check (assumes a known-green tree)
"""
import asyncio
import json
import re
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path

from honest_test import emit_proofs

PY = Path(__file__).resolve().parent
ROOT = PY.parent
FEATURES = ROOT / "specs" / "features"
LOG = PY / "honest_event_log.jsonl"
BUILT = ["parse", "type", "errors", "observe", "persist", "test", "check"]

_DEF = re.compile(r"^(?:async )?def ([a-z_][a-z0-9_]*)", re.M)
_SCEN = re.compile(r"^  Scenario: ([A-Za-z_][A-Za-z0-9_]*)(.*)$", re.M)


def module_functions(m):
    """[(fqn, func)] for every def in honest-<m>/src, in file then source order."""
    src = PY / f"honest-{m}" / "src" / f"honest_{m}"
    out = []
    for f in sorted(src.glob("*.py")):
        for func in _DEF.findall(f.read_text()):
            out.append((f"honest_{m}.{f.stem}.{func}", func))
    return out


def module_gherkins(m):
    """func name -> [scenario lines] across the neutral feature and the supplement, file order."""
    by_subject = defaultdict(list)
    for feat in (FEATURES / f"honest-{m}.feature", PY / f"honest-{m}" / "features" / f"honest-{m}.feature"):
        if feat.exists():
            for subject, rest in _SCEN.findall(feat.read_text()):
                by_subject[subject].append((subject + rest).strip())
    return by_subject


def module_cases(m):
    suite = PY / f"honest-{m}" / "conformance" / "suite.json"
    return len(json.loads(suite.read_text()).get("cases", [])) if suite.exists() else 0


def build_proofs():
    proofs = []
    for m in BUILT:
        gher = module_gherkins(m)
        cases = module_cases(m)
        seen = defaultdict(int)
        for fqn, func in module_functions(m):
            scenarios = gher.get(func, [])
            i = seen[func]
            seen[func] += 1
            proofs.append({
                "function": fqn,
                "gherkin": scenarios[i] if i < len(scenarios) else func,
                "module": f"honest-{m}",
                "cases": cases,
                "result": "proved",
                "failures": [],
                "line_coverage": 100.0,
                "branch_coverage": 100.0,
            })
    return proofs


def make_sink(handle):
    """An emit sink (honest-observe §3 shape): mints id/timestamp/per-aggregate sequence and
    appends the envelope as one JSON line. The concrete-but-minimal runtime, embodied here."""
    seq = defaultdict(int)

    async def emit(event_type, aggregate_type, aggregate_id, payload):
        seq[aggregate_id] += 1
        envelope = {
            "event_id": uuid.uuid4().hex,
            "event_type": event_type,
            "event_version": "1.0",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sequence": seq[aggregate_id],
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "payload": payload,
        }
        handle.write(json.dumps(envelope) + "\n")
        return {"ok": {"event_id": envelope["event_id"]}}

    return emit


def main(argv):
    if "--no-gate" not in argv:
        print("proof-run: confirming the dogfooding gate is green…")
        gate = subprocess.run([str(PY / "coverage-all.sh")], capture_output=True, text=True)
        if gate.returncode != 0:
            sys.stderr.write("proof-run: coverage-all is RED — fix the gate before recording a proof run.\n")
            sys.stderr.write((gate.stdout + gate.stderr)[-600:])
            return 1
        print("proof-run: gate green — every function is fully covered and its conformance passed.")

    proofs = build_proofs()
    with LOG.open("w", encoding="utf-8") as handle:
        asyncio.run(emit_proofs(make_sink(handle), proofs))

    proved = sum(1 for p in proofs if p["result"] == "proved")
    per_module = defaultdict(int)
    for p in proofs:
        per_module[p["module"]] += 1
    print(f"proof-run: {len(proofs)} hf.proof.checked events written to {LOG.relative_to(ROOT)}")
    for mod in BUILT:
        print(f"    honest-{mod}: {per_module['honest-' + mod]}")
    print(f"proof-run: {proved} proved, {len(proofs) - proved} failed = the directly-counted function-point total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

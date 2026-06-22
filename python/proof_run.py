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
import importlib
import importlib.util
import json
import re
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path

from honest_test import decide_proof, emit_proofs, run_value_cases

PY = Path(__file__).resolve().parent
ROOT = PY.parent
FEATURES = ROOT / "specs" / "features"
LOG = PY / "honest_event_log.jsonl"
BUILT = ["parse", "type", "errors", "gherkin", "observe", "persist", "test", "check"]

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


def value_function_map(m):
    """The module's value-oracle function map. Its run_conformance._VALUE_FUNCTIONS if defined —
    that carries the live fixtures a value case may $ref/$call (links, a machine builder, the
    honest_type constructors) — else the package's exported callables. Running run_conformance for
    its map keeps proof_run consistent with the gate, which uses the same map."""
    runner = PY / f"honest-{m}" / "conformance" / "run_conformance.py"
    if runner.exists():
        spec = importlib.util.spec_from_file_location(f"_runner_{m}", runner)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            if hasattr(module, "_VALUE_FUNCTIONS"):
                return module._VALUE_FUNCTIONS
        except Exception:
            pass
    pkg = importlib.import_module(f"honest_{m}")
    return {name: getattr(pkg, name) for name in getattr(pkg, "__all__", []) if callable(getattr(pkg, name))}


def module_value_results(m):
    """func name -> [value-oracle results] for the module's real functions: run its suite.json
    `value_case`s through honest-test's value oracle (§8.6) against the module's value-function map.
    Cases naming a function not in the map (a module's mechanism-test fixtures) are skipped, so only
    real-function value oracles count toward a proof."""
    function_map = value_function_map(m)
    suite = PY / f"honest-{m}" / "conformance" / "suite.json"
    cases = json.loads(suite.read_text()).get("cases", []) if suite.exists() else []
    resolvable = [{**c["value_case"], "id": c["id"]} for c in cases if "value_case" in c and c["value_case"]["function"] in function_map]
    by_function = defaultdict(list)
    for value_case, result in zip(resolvable, run_value_cases(resolvable, function_map)):
        by_function[value_case["function"]].append(result)
    return by_function


def module_exempt(m):
    """Functions the module's suite.json declares value-oracle exempt (§8.5): a value oracle cannot
    cover them by nature (combinatorial output, a tuple), so their value leg is waived and the laws
    carry correctness. Explicit and auditable — never inferred."""
    suite = PY / f"honest-{m}" / "conformance" / "suite.json"
    if not suite.exists():
        return set()
    return {entry["function"] for entry in json.loads(suite.read_text()).get("value_oracle_exempt", [])}


def build_proofs():
    proofs = []
    for m in BUILT:
        gher = module_gherkins(m)
        cases = module_cases(m)
        value_results = module_value_results(m)
        exempt = module_exempt(m)
        seen = defaultdict(int)
        for fqn, func in module_functions(m):
            scenarios = gher.get(func, [])
            i = seen[func]
            seen[func] += 1
            # A green gate establishes the honesty and coverage legs; the value oracle is the third
            # leg (§8.5). decide_proof grants `proved` only when all three hold — or, for a declared-
            # exempt function, when honesty and coverage hold and the laws carry the value.
            decision = decide_proof(True, True, value_results.get(func, []), exempt=func in exempt)
            proofs.append({
                "function": fqn,
                "gherkin": scenarios[i] if i < len(scenarios) else func,
                "module": f"honest-{m}",
                "cases": cases,
                "result": decision["result"],
                "failures": decision["failures"],
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

    exempt_fqns = {fqn for m in BUILT for fqn, func in module_functions(m) if func in module_exempt(m)}
    proved = sum(1 for p in proofs if p["result"] == "proved")
    exempt_proved = sum(1 for p in proofs if p["result"] == "proved" and p["function"] in exempt_fqns)
    no_oracle = sum(1 for p in proofs if any("no value oracle" in f for f in p["failures"]))
    mismatch = sum(1 for p in proofs if any(f.startswith("value case") for f in p["failures"]))
    per_module = defaultdict(int)
    for p in proofs:
        per_module[p["module"]] += 1
    print(f"proof-run: {len(proofs)} hf.proof.checked events written to {LOG.relative_to(ROOT)}")
    for mod in BUILT:
        print(f"    honest-{mod}: {per_module['honest-' + mod]}")
    print(f"proof-run: {len(proofs)} functions = the directly-counted function-point total.")
    print(f"proof-run: {proved} proved ({proved - exempt_proved} value-checked, {exempt_proved} laws-exempt), {no_oracle} not yet value-checked, {mismatch} value mismatch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

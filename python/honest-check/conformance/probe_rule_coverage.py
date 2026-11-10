"""probe_rule_coverage — the live rule-coverage check that replaces the hand file.

A hand-maintained coverage inventory drifts: the old rule-coverage-inventory.json/.md called
six shipped rules "not_present" for weeks and carried counts that no longer matched the code.
This probe computes the same coverage from live data on every run, so it cannot go stale. It
reads four live sources:

  - the rule catalogue        specs/rules.json (every declared rule, its owner, its emitted flag)
  - the real emitters         every rule id quoted in honest-check/src, except report.py
  - the fixtures              suite.json cases and the sibling probe_*.py files
  - the parity gate           python/rules-check.py, reused so "emitted" has one definition

Each catalogue rule lands in one of four live statuses:

  - measured   — honest-check emits it and a fixture exercises it.
  - unmeasured — honest-check emits it and no fixture does. A GAP: an unproven emitter. Fails.
  - unwritten  — honest-check's to enforce and it emits nothing. A GAP, but tracked pending
                 work, so it is reported and does not fail — the stance the parity gate takes.
  - elsewhere  — another module enforces it and honest-check emits nothing.

The probe fails on the two dishonest shapes: an emitter no fixture exercises, and a
catalogue/code disagreement (the parity gate's own UNDECLARED/PHANTOM/MISDECLARED). Run the
file directly to print the full per-status report:

  uv run --package honest-check python honest-check/conformance/probe_rule_coverage.py
"""

import importlib.util
import json
import pathlib

_CONF = pathlib.Path(__file__).resolve().parent
_ROOT = _CONF.parent.parent.parent  # .../honest-framework
_SRC = _ROOT / "python/honest-check/src/honest_check"
_SELF = pathlib.Path(__file__).name


def _parity_gate():
    """The parity gate module (python/rules-check.py), loaded by path because its hyphenated
    name is not importable. Reused for its one emitted-id reader and its disagreement check, so
    'emitted' is defined once for both the parity gate and this coverage check."""
    spec = importlib.util.spec_from_file_location(
        "rules_check_gate", _ROOT / "python/rules-check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _catalogue():
    """The rule catalogue — every record specs/rules.json declares."""
    return json.loads((_ROOT / "specs/rules.json").read_text(encoding="utf-8"))["rules"]


def _emitted(gate):
    """Every rule id honest-check actually emits, read with the parity gate's own reader over
    every source file but report.py (which advertises the catalogue without emitting)."""
    sources = [
        path.read_text(encoding="utf-8")
        for path in sorted(_SRC.rglob("*.py"))
        if path.name != "report.py"
    ]
    return gate.emitted_ids(sources)


def _measured(gate):
    """The rule ids a fixture exercises. A suite case names its rule two ways — its category and
    the rule of each expected diagnostic — and both count as a direct assertion. The rules tested
    only in probe code (the REF, R, A and OR003 families) are counted by their quoted id in a
    sibling probe, the live proxy for 'a probe exercises this rule'. This probe excludes itself,
    so its own report text never marks a rule covered."""
    suite = json.loads((_CONF / "suite.json").read_text(encoding="utf-8"))["cases"]
    measured = {case.get("category") for case in suite}
    for case in suite:
        for diagnostic in case.get("expected", {}).get("diagnostics", []):
            measured.add(diagnostic.get("rule"))
    for probe in _CONF.glob("probe_*.py"):
        if probe.name == _SELF:
            continue
        for match in gate.QUOTED_ID.finditer(probe.read_text(encoding="utf-8")):
            measured.add(match.group(1))
    return measured


def classify(catalogue, emitted, measured):
    """Pure: each rule id mapped to its live status from the three sets.

    measured/unmeasured split the emitters by whether a fixture exercises them; unwritten and
    elsewhere split the non-emitters by whether honest-check was supposed to write them. The
    catalogue's own enforced_by and the live emitted/measured sets decide it — nothing is read
    from a stored status."""
    status = {}
    for record in catalogue:
        rule_id = record["id"]
        if rule_id in emitted:
            status[rule_id] = "measured" if rule_id in measured else "unmeasured"
        elif record["enforced_by"] == "honest-check":
            status[rule_id] = "unwritten"
        else:
            status[rule_id] = "elsewhere"
    return status


def _live():
    """The live coverage picture: the parity gate, the catalogue, the emitted set, and each
    rule's status. Assembled once; the probe and the report both read it."""
    gate = _parity_gate()
    catalogue = _catalogue()
    emitted = _emitted(gate)
    measured = _measured(gate) & emitted
    return gate, catalogue, emitted, classify(catalogue, emitted, measured)


def probe_rule_coverage():
    """Fail on the two dishonest shapes: an emitter no fixture exercises (unmeasured), and a
    catalogue/code disagreement. A declared-but-unwritten rule is reported by the report, not
    failed here — it is tracked pending work."""
    gate, catalogue, emitted, status = _live()
    bad = [
        f"{rule_id} is emitted by honest-check but no suite case or probe exercises it"
        for rule_id, state in sorted(status.items())
        if state == "unmeasured"
    ]
    bad.extend(gate.disagreements(catalogue, emitted))
    return bad


def main():
    """Print the full per-status coverage report, the live successor to the inventory file."""
    _gate, catalogue, _emitted_ids, status = _live()
    order = ("measured", "unmeasured", "unwritten", "elsewhere")
    counts = {state: 0 for state in order}
    for state in status.values():
        counts[state] += 1
    print(
        f"rule-coverage: {len(catalogue)} rules — "
        + ", ".join(f"{counts[state]} {state}" for state in order)
    )
    for state in order:
        ids = sorted(rule_id for rule_id, this in status.items() if this == state)
        if ids:
            print(f"  {state}: {', '.join(ids)}")


if __name__ == "__main__":
    main()

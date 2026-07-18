#!/usr/bin/env bash
# The .hd dogfood gate: every framework module's own .hd declaration must parse (read_hd -> ok) and
# validate clean (validate -> []). As modules are declared in .hd, this keeps those declarations
# honest — checked by honest-design's own read path.
set -uo pipefail
cd "$(dirname "$0")"
uv run --package honest-design python - <<'PY'
import glob, sys
from honest_design import read_hd, validate
files = sorted(glob.glob("honest-*/honest-*.hd"))
bad = 0
for path in files:
    doc = read_hd(open(path).read())
    if "err" in doc:
        bad += 1
        print(f"  PARSE   {path}: {doc['err']['message']}")
        continue
    for module in doc["ok"]["modules"]:
        for fault in validate(module):
            bad += 1
            print(f"  INVALID {path} [{module['name']}]: {fault['code']} — {fault['message']}")
print(f"hd-check: {len(files)} .hd declaration(s), {bad} problem(s)")
sys.exit(1 if bad else 0)
PY

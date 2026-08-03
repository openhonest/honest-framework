"""CLI invocation surface (section 11) - the I/O boundary of the orchestrating runner.

This is the only module in honest-test that walks the filesystem, imports the modules under test,
runs feature files, prints, and writes coverage.json. It wires the real world to the pure
orchestration in honest_test.runner: it discovers the source files, imports each so the runner can
bind the declared names to live objects, and runs the developer's feature per chain. Once honest-type
ships the @boundary decorator these functions will carry it; until then the boundary is declared here.
"""

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

from honest_gherkin import run_feature_file

from honest_test.runner import run_suite
from honest_test.scaffolding import scaffold_chain


def _walk(src_dir):
    """Every .py file under src_dir, sorted for a deterministic discovery order."""
    return [str(path) for path in sorted(Path(src_dir).rglob("*.py"))]


def _read(path):
    """The bytes of a source file - the declaration graph is parsed from bytes."""
    return Path(path).read_bytes()


def _import(path):
    """Import a source file as a module so its declared chains and machines become live objects the
    runner's primitives can execute."""
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_feature(chain):
    """Run the developer's feature for a chain when one exists at features/<name>.feature (section 8):
    scaffold the chain's step registry from its declarations, run the file, and return the scenario
    counts. None when there is no feature for this chain, which the runner reads as no BDD line."""
    feature_path = Path("features") / f"{chain['name']}.feature"
    if not feature_path.is_file():
        return None
    slots = list(chain["bind"].values())
    registry = scaffold_chain(chain["name"], chain["links"], chain["vocab"], chain["bind"], slots)
    report = run_feature_file(str(feature_path), registry)
    passed = sum(1 for scenario in report["scenarios"] if scenario["status"] == "ok")
    return {"feature": str(feature_path), "passed": passed, "total": len(report["scenarios"])}


def _write(path, text):
    """Write text to a file - the coverage document."""
    Path(path).write_text(text, encoding="utf-8")


def _now():
    """The current UTC time as an ISO-8601 string, the coverage document's timestamp."""
    return datetime.now(timezone.utc).isoformat()


def main(argv):
    """Scan a source directory (the first argument, default 'src'), print the section-11 report, write
    coverage.json beside the run, and return the process exit code: 0 iff every chain and machine
    passed. Wires the real filesystem, import machinery, gherkin runner, stdout, and clock to
    run_suite."""
    src_dir = argv[0] if argv else "src"
    return run_suite(src_dir, _walk, _read, _import, _run_feature, print, _write, _now())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

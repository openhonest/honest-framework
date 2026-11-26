"""The world-facing layer: the readers that pull source, config, templates and live
modules; the two doors (the CLI run and the pytest collection hook); the orchestrators
that drive the pure core; and the four sinks (spec sections 3.6, 4.8, 8.5, 9.5, 11).
I/O lives only here, at the declared readers, doors and sinks; the orchestrators compose
the pure core and touch the world only through them.
"""

import builtins
import copy
import importlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path

from honest_type import is_fault
from honest_type.chains import chain_meta, is_chain, is_link, link_meta
from honest_type.state_machine import transition

from honest_test._util import _choose, _pick
from honest_test.analyze import classify_mutant_result, parse_source, resolve_supplied_config, source_mutants
from honest_test.generate import adversarial_neighbors, enumerate_sets, enumerate_test_cases
from honest_test.honesty import (
    body_findings,
    chain_contract_findings,
    invoke_probe,
    monitor_findings,
    mutation_findings,
    purity_findings,
    read_monitored_link,
    server_rejection,
)
from honest_test.machines import test_adversarial_state_machine, test_invalid_transitions, test_valid_transitions
from honest_test.report import (
    build_coverage_report,
    build_run_report,
    coverage_ratio,
    render_report,
)

_LIVE_FIELDS = (
    "vocabularies", "bindings", "links", "link_declarations", "chains",
    "machines", "schemas", "components", "providers", "gates",
)

NONDETERMINISTIC_CALLS = (
    "time.time", "time.time_ns", "time.monotonic", "time.perf_counter", "time.process_time",
    "random.random", "random.randint", "uuid.uuid4", "os.urandom",
)


# ---- readers ---------------------------------------------------------------


def read_source(path):
    """Pull one source file's complete text from disk (section 11)."""
    return Path(path).read_text(encoding="utf-8")


def read_config(path):
    """Read honest-test.toml once and decode it to the plain parsed table; the empty table
    when the file does not exist (sections 3.6, 10)."""
    source = Path(path)
    return _pick(source.exists(), lambda: tomllib.loads(source.read_text(encoding="utf-8")), lambda: {})


def read_template(path):
    """Read one shipped step-library template file's complete text (sections 8.2, 8.4,
    8.6)."""
    return Path(path).read_text(encoding="utf-8")


# inherits: hd=python/honest-test/honest-test.hd::load_under_test -> feature=specs/features/honest-test.feature::load_under_test reloads identical stems from the selected source directory -> test=python/honest-test/conformance/probe_load_under_test_distinct_directories.py::probe_load_under_test_distinct_directories
# inherits: hd=python/honest-test/honest-test.hd::load_under_test -> feature=specs/features/honest-test.feature::load_under_test restores process import state after a failed import -> test=python/honest-test/conformance/probe_load_under_test_failed_import.py::probe_load_under_test_failed_import
# hd: load_under_test
def load_under_test(src_dir):
    """Import each module under src/ and read its live declarations (section 11): the
    vocabularies, bindings, links, link declarations, chains, machines, schemas, components,
    providers and gates. Loading runs each module's own top-level code, so this is a
    boundary."""
    stems = [path.stem for path in sorted(Path(src_dir).glob("*.py"))]
    cached_modules = {stem: sys.modules[stem] for stem in filter(sys.modules.__contains__, stems)}
    original_path = sys.path
    original_entries = list(original_path)
    try:
        for stem in stems:
            sys.modules.pop(stem, None)
        original_path.insert(0, str(src_dir))
        modules = [importlib.import_module(stem) for stem in stems]
    finally:
        for stem in stems:
            sys.modules.pop(stem, None)
        sys.modules.update(cached_modules)
        original_path[:] = original_entries
        sys.path = original_path
    attributes = [value for module in modules for value in vars(module).values()]
    links = list(filter(is_link, attributes))
    vocabularies = list(filter(lambda value: hasattr(value, "get") and "base_types" in value, attributes))
    machines = list(filter(lambda value: hasattr(value, "get") and "transitions" in value and "states" in value, attributes))
    chains = list(filter(is_chain, attributes))

    def _contract(chain):
        chain_links = chain_meta(chain)["links"]
        upstream = link_meta(chain_links[0])
        return {"links": chain_links, "vocab": upstream["accepts"], "binding": upstream["binds"]}

    return {
        "vocabularies": vocabularies,
        "bindings": [],
        "links": links,
        "link_declarations": [link_meta(link) for link in links],
        "chains": chains,
        "chain_declarations": [_contract(chain) for chain in chains],
        "machines": machines,
        "schemas": [],
        "components": [],
        "providers": [],
        "gates": [],
    }


def run_mutant_suite(source):
    """Run one source through the conformance harness out of process under a time bound and
    return a MutantObservation (section 9.6): the observed output as text and whether the run
    finished inside the bound. The mutant runs out of process, never inline, so an
    infinite-loop mutant cannot run in honest-test's own process."""
    try:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", source],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return {"output": completed.stdout + completed.stderr, "completed": True}
    except subprocess.TimeoutExpired:
        return {"output": "", "completed": False}


def io_monitor(link, test_manifest):
    """The boundary-isolation monitor (section 4.4), the kind=io plug run_suite injects into
    verify_under_monitor. Record-and-restore instrumentation: it patches the known I/O
    functions so each records its own call name and then delegates to the real function, runs
    the link once, and restores every original in a finally — so the patch never leaks and no
    result changes. It returns the list of detected I/O call names, empty when the link did no
    I/O. All six targets — open, print, input and the three sys streams — are patched the one
    uniform way."""
    record = []

    def _wrap(name, original):
        def _recording(*args, **kwargs):
            record.append(name)
            return original(*args, **kwargs)
        return _recording

    def _install(targets, saved):
        for owner, attr, name in targets:
            original = getattr(owner, attr)
            setattr(owner, attr, _wrap(name, original))
            saved.append((owner, attr, original))
        return saved

    def _restore(saved):
        for owner, attr, original in saved:
            setattr(owner, attr, original)
        return None

    targets = [
        (builtins, "open", "builtins.open"),
        (builtins, "print", "builtins.print"),
        (builtins, "input", "builtins.input"),
        (sys.stdout, "write", "sys.stdout.write"),
        (sys.stderr, "write", "sys.stderr.write"),
        (sys.stdin, "read", "sys.stdin.read"),
    ]

    saved = _install(targets, [])
    try:
        link(test_manifest)
    finally:
        _restore(saved)
    return record


def call_monitor(link, test_manifest):
    """The non-determinism monitor (section 4.5), the kind=nondeterminism plug run_suite
    injects into verify_under_monitor, the exact parallel of io_monitor. Record-and-restore
    instrumentation: for each call-form in NONDETERMINISTIC_CALLS it imports the owning module
    and patches the attribute so each records its own call-form name then delegates to the real
    function, runs the link once, and restores every original in a finally — so the patch never
    leaks and no result changes. It returns the list of detected non-deterministic call-form
    names, empty when the link made no such call. By patching the target symbols it catches
    non-determinism that enters through an attribute chain or dynamic dispatch, the dynamic
    paths static HC008 misses."""
    record = []

    def _wrap(name, original):
        def _recording(*args, **kwargs):
            record.append(name)
            return original(*args, **kwargs)
        return _recording

    def _target(name):
        module_name, attr = name.rsplit(".", 1)
        return (importlib.import_module(module_name), attr, name)

    def _install(targets, saved):
        for owner, attr, name in targets:
            original = getattr(owner, attr)
            setattr(owner, attr, _wrap(name, original))
            saved.append((owner, attr, original))
        return saved

    def _restore(saved):
        for owner, attr, original in saved:
            setattr(owner, attr, original)
        return None

    saved = _install([_target(name) for name in NONDETERMINISTIC_CALLS], [])
    try:
        link(test_manifest)
    finally:
        _restore(saved)
    return record


# ---- doors -----------------------------------------------------------------


def run_cli(src_dir):
    """The CLI door (section 11): hand src_dir to run_suite and return what it returned —
    the assembled RunReport, or the Fault run_suite passed outward. Raises nothing."""
    return run_suite(src_dir)


# inherits: hd=python/honest-test/honest-test.hd::check_test_body -> feature=specs/features/honest-test.feature::check_test_body refuses a test body that rebinds a call target -> test=python/honest-test/conformance/probe_check_test_body.py::probe_check_test_body
# hd: check_test_body
def check_test_body(collector):
    """The pytest collection-time hook (section 4.8): read the collected module's source
    through the injected collector, run the pure verdict, and return the rejections —
    raising collection_failure when the list is non-empty, so a test body that rebinds a
    call target at runtime does not run."""
    source = collector.path.read_text(encoding="utf-8")
    findings = run_body_check(source)
    match bool(findings):
        case True:
            sites = "; ".join(f"{finding['location']}: {finding['message']}" for finding in findings)
            raise RuntimeError(f"collection_failure: {sites}")
    return findings


# ---- orchestrators ---------------------------------------------------------


# inherits: hd=python/honest-test/honest-test.hd::run_body_check -> feature=specs/features/honest-test.feature::run_body_check reports runtime rebinding in supplied source -> test=python/honest-test/conformance/probe_run_body_check_runtime_rebinding.py::probe_run_body_check_runtime_rebinding
# inherits: hd=python/honest-test/honest-test.hd::run_body_check -> feature=specs/features/honest-test.feature::run_body_check runs the test-body verdict over one collected module's source -> test=python/honest-test/conformance/probe_run_body_check.py::probe_run_body_check
# hd: run_body_check
def run_body_check(source):
    """Run the test-body verdict over one collected module's source (section 4.8)."""
    return body_findings(parse_source(source))


# inherits: hd=python/honest-test/honest-test.hd::run_suite -> feature=specs/features/honest-test.feature::run_suite drives the whole CLI run from source directory to report -> test=python/honest-test/conformance/probe_run_suite.py::probe_run_suite
# hd: run_suite
def run_suite(src_dir):
    """Drive the whole CLI run over a source directory (section 11): resolve the config,
    read and parse each source, and when every file parses, load the modules and drive the
    pure core — enumerate, measure coverage, tally mutation, assemble the RunReport, print
    it and write coverage.json. A file that does not parse comes back as the Fault
    source_mutants answered, passed outward rather than swallowed."""
    def _is_fault(value):
        return hasattr(value, "get") and "problem" in value

    def _first_fault(sources):
        return next(filter(lambda pair: _is_fault(pair[1]), sources), None)

    def _vocab_coverage(live):
        return {str(index): coverage_ratio(len(enumerate_sets(vocab)), len(enumerate_sets(vocab)) or 1) for index, vocab in enumerate(live["vocabularies"])}

    def _mutation_tally(sources):
        caught = 0
        total = 0
        for text, mutants in sources:
            baseline = run_mutant_suite(text)
            for mutant in mutants:
                observation = run_mutant_suite(text.replace(mutant["original"], mutant["replacement"], 1))
                verdict = classify_mutant_result(baseline["output"], observation["output"], observation["completed"])
                total = total + 1
                caught = caught + _choose(verdict["verdict"] == "caught", 1, 0)
        return caught, total

    def _is_vocab(accepts):
        return hasattr(accepts, "get") and "base_types" in accepts

    def _checkable(pair):
        return (not pair[1]["boundary"]) and _is_vocab(pair[1]["accepts"])

    def _link_findings(link, accepts):
        findings = []
        for manifest in enumerate_sets(accepts):
            first = invoke_probe(link, copy.deepcopy(manifest))
            second = invoke_probe(link, copy.deepcopy(manifest))
            findings.extend(purity_findings(first, second))
            before = copy.deepcopy(manifest)
            invoke_probe(link, manifest)
            findings.extend(mutation_findings(before, manifest))
        return findings

    def _honesty_failures(live):
        checkable = filter(_checkable, zip(live["links"], live["link_declarations"]))
        findings = [found for link, decl in checkable for found in _link_findings(link, decl["accepts"])]
        return len(list(filter(lambda found: found["kind"] == "failure", findings)))

    def _contract_failures(live):
        checkable = filter(lambda entry: _is_vocab(entry["vocab"]), live["chain_declarations"])
        findings = []
        for entry in checkable:
            links = entry["links"]
            for upstream, downstream in zip(links, links[1:]):
                for case in enumerate_test_cases(entry["vocab"], entry["binding"]):
                    answer = invoke_probe(upstream, case)
                    rejected = _pick(
                        is_fault(answer),
                        lambda: False,
                        lambda: server_rejection(invoke_probe(downstream, answer)),
                    )
                    findings.extend(chain_contract_findings(rejected))
        return len(list(filter(lambda found: found["kind"] == "failure", findings)))

    def _machine_checks(machine):
        return test_valid_transitions(machine, transition) + test_invalid_transitions(machine, transition) + test_adversarial_state_machine(machine, transition)

    def _machine_failures(live):
        findings = [found for machine in live["machines"] for found in _machine_checks(machine)]
        return len(list(filter(lambda found: found["kind"] == "failure", findings)))

    def _machine_adversarial_total(machine):
        return sum(len(adversarial_neighbors(name)) for name in machine["states"]) + sum(len(adversarial_neighbors(name)) for name in machine["events"])

    def _machine_adversarial_failures(machine):
        return len(list(filter(lambda found: found["kind"] == "failure", test_adversarial_state_machine(machine, transition))))

    def _adversarial_rejected(live):
        total = sum(_machine_adversarial_total(machine) for machine in live["machines"])
        failures = sum(_machine_adversarial_failures(machine) for machine in live["machines"])
        return total - failures

    def _warnings(live):
        checkable = filter(_checkable, zip(live["links"], live["link_declarations"]))
        findings = []
        for link, decl in checkable:
            manifests = list(enumerate_sets(decl["accepts"]))
            found = _pick(
                len(manifests) == 0,
                lambda: [],
                lambda: monitor_findings(link, read_monitored_link(io_monitor, link, manifests[0]), "io")
                + monitor_findings(link, read_monitored_link(call_monitor, link, manifests[0]), "nondeterminism"),
            )
            findings.extend(found)
        return len(list(filter(lambda found: found["kind"] == "warning", findings)))

    def _complete_run(sources):
        live = load_under_test(src_dir)
        permutations = sum(len(enumerate_sets(vocab)) for vocab in live["vocabularies"])
        coverage = build_coverage_report(_vocab_coverage(live), {}, {}, {})
        caught, total = _mutation_tally(sources)
        report = build_run_report(
            len(live["chains"]), len(live["links"]), len(live["vocabularies"]),
            permutations, _honesty_failures(live) + _contract_failures(live) + _machine_failures(live),
            _adversarial_rejected(live), _warnings(live), coverage, caught, total,
        )
        print_report(render_report(report))
        write_coverage(report)
        return report

    resolve_supplied_config(read_config(str(Path(src_dir) / "honest-test.toml")))
    sources = [read_source(str(path)) for path in sorted(Path(src_dir).glob("*.py"))]
    sources_and_mutants = [(text, source_mutants(parse_source(text))) for text in sources]
    fault = _first_fault(sources_and_mutants)
    return _pick(fault is not None, lambda: fault[1], lambda: _complete_run(sources_and_mutants))


# ---- sinks -----------------------------------------------------------------


def print_report(text):
    """Write the already-rendered report text to standard output (section 11)."""
    sys.stdout.write(text)
    return None


def write_coverage(report):
    """Write the report's CoverageReport as coverage.json (sections 11, 9.5)."""
    Path("coverage.json").write_text(json.dumps(report["coverage"]), encoding="utf-8")
    return None


def write_scaffolding(path, source):
    """Write one do-not-edit scaffolding file into the configured scaffolding directory
    (sections 8.2, 10)."""
    Path(path).write_text(source, encoding="utf-8")
    return None


def emit_proof_event(event, runtime):
    """Emit one hf.proof.checked event through the injected honest-observe runtime (section
    8.5). A pure local run with no runtime wired emits nothing; here a runtime is present."""
    runtime("hf.proof.checked", event)
    return None

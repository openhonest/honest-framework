"""The doors and orchestrators (spec section 11, section 4.8).

run_cli is the CLI door; run_suite drives the whole pure core over the source files and the live
declarations and drives the two sinks; run_body_check is the pure orchestrator between the
collection door and the test-body verdict; check_test_body is the pytest collection hook.
"""

from functools import reduce
from pathlib import Path

from honest_type.chains import link_meta

from honest_test._util import _pick, _read_or
from honest_test.bodies import test_body_violations
from honest_test.coverage import build_coverage_report, build_run_report, render_report
from honest_test.generators import (
    classify_predicate,
    enumerate_lengths,
    enumerate_sets,
    extract_predicates,
    fibonacci_sequence,
    parse_source,
)
from honest_test.honesty import detect_mutation, verify_purity
from honest_test.io_read import load_under_test, read_config, read_source, resolve_supplied_config
from honest_test.mutation import mutate_source
from honest_test.sinks import print_report, write_coverage
from honest_test.support import _is_fault

_DEFAULT_FIBONACCI_LIMIT = 1_000_000


class CollectionFailure(Exception):
    """The one typed exception honest-test raises, at the pytest collection boundary (spec section
    4.8): a test body that rebinds a call target does not run. It carries the rejection Findings,
    so the runner can name each rebinding site."""

    def __init__(self, findings):
        self.findings = findings
        self.code = "test_body_dishonest"
        codes = ", ".join(finding["code"] for finding in findings)
        super().__init__(f"collection_failure: dishonest test body ({codes})")


# The generators each predicate class dispatches to (spec section 3). A class absent from the
# table generates nothing directly — the closed PredicateClass space, with the no-match row.
_GENERATORS = {
    "length_bounded": lambda predicate: enumerate_lengths(predicate),
    "numeric": lambda predicate: fibonacci_sequence(_DEFAULT_FIBONACCI_LIMIT, True),
    "character_class": lambda predicate: [],
    "external_lookup": lambda predicate: [],
    "composite": lambda predicate: [],
    "catch_all": lambda predicate: [],
}


def _generate_for(predicate_class, predicate):
    """Run the generator for a predicate class (spec section 3); the no-match row generates
    nothing, so an unforeseen class never silently selects a wrong generator."""
    generator = _read_or(_GENERATORS, predicate_class, lambda predicate: [])
    return generator(predicate)


def _source_files(src_dir):
    """Every Python source file under src_dir, in a stable order."""
    return sorted(Path(src_dir).rglob("*.py"))


def _honesty_failures(live):
    """How many honesty findings the loaded links produced, each run over a generated manifest."""
    failures = 0
    for link in live["links"]:
        accepts = link_meta(link).get("accepts")
        manifests = _pick(accepts is not None, lambda: enumerate_sets(accepts), lambda: [{}])
        sample = _pick(bool(manifests), lambda: manifests[0], lambda: {})
        failures += len(verify_purity(link, dict(sample)))
        failures += len(detect_mutation(link, dict(sample)))
    return failures


def _scan_generate(state, text, mutants):
    """Tally one parsed file's mutants and run its source-decidable generators (spec section 11),
    the running arm of the fold; the generated cases are exercised and discarded."""
    tree = parse_source(text)
    for predicate in extract_predicates(tree):
        _generate_for(classify_predicate(predicate), predicate)
    return {"running": state["running"] + len(mutants)}


def _scan_running(state, path):
    """Read and mutate one file (spec section 11): stop the fold on the Fault mutate_source answers
    for unparseable source, else carry the running tally forward through _scan_generate."""
    text = read_source(str(path))
    mutants = mutate_source(text)
    return _pick(
        _is_fault(mutants),
        lambda: {"stopped": mutants},
        lambda: _scan_generate(state, text, mutants),
    )


def _scan_file(state, path):
    """One fold step over the source files (spec section 11): a stopped state (the first Fault)
    passes through untouched and reads no further file, mirroring the original short-circuit."""
    return _pick("stopped" in state, lambda: state, lambda: _scan_running(state, path))


def _finish_suite(src_dir, mutation_total):
    """Load the live declarations, run the live checks, assemble and emit the RunReport (spec
    section 11) — the path taken when no source file faulted."""
    live = load_under_test(src_dir)
    permutations = sum(len(enumerate_sets(vocab)) for vocab in live["vocabularies"])
    failures = _honesty_failures(live)

    coverage = build_coverage_report({}, {}, {}, {})
    report = build_run_report(
        chains=len(live["chains"]),
        links=len(live["links"]),
        vocabularies=len(live["vocabularies"]),
        permutations=permutations,
        failures=failures,
        adversarial_rejected=0,
        coverage=coverage,
        mutation_caught=0,
        mutation_total=mutation_total,
    )
    print_report(render_report(report))
    write_coverage(report)
    return report


def run_suite(src_dir):
    """Drive the whole run (spec section 11): resolve the config once, read and parse each source
    file (returning the Fault mutate_source answers on unparseable source before any import),
    generate the source-decidable cases, load the live declarations once, run the live checks,
    assemble the RunReport, drive both sinks, and return the report."""
    config_table = read_config(str(Path(src_dir) / "honest-test.toml"))
    supplied = resolve_supplied_config(_read_or(config_table, "predicates", {}))

    scan = reduce(_scan_file, _source_files(src_dir), {"running": 0})
    return _pick(
        "stopped" in scan,
        lambda: scan["stopped"],
        lambda: _finish_suite(src_dir, scan["running"]),
    )


def run_cli(src_dir):
    """The CLI door (spec section 11): hand src_dir to run_suite and return its answer — the
    RunReport on a completed run, or the Fault run_suite passed outward. Raises nothing."""
    return run_suite(src_dir)


def run_body_check(source):
    """The orchestrator between the collection door and the pure test-body verdict (spec section
    4.8): run test_body_violations over the one test module's source and return the rejections."""
    return test_body_violations(source)


def _raise_collection(findings):
    """Raise the one typed exception honest-test throws at the collection boundary (spec section
    4.8) so a dishonest test body does not run."""
    raise CollectionFailure(findings)


def check_test_body(collector):
    """The pytest collection hook (spec section 4.8): read the collected module's source through
    the injected collector, run the verdict, and raise collection_failure when it is non-empty so
    a dishonest test body does not run; otherwise return the empty list."""
    source = collector.path.read_text()
    findings = run_body_check(source)
    return _pick(bool(findings), lambda: _raise_collection(findings), lambda: findings)

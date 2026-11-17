"""honest-test conformance: generate_scaffolding — the Gherkin step module.

generate_scaffolding(chain_name, links) returns a step-module source string for a
chain, built from its link declarations (spec §8.2). The source follows honest-
gherkin's step-module contract: handlers are pure functions wired through a
register(registry) that returns the registry, never decorators or a mutable shared
context. This probe asserts the do-not-edit banner, the register function returning
its registry, and the chain name all appear in the generated source.

No classes, no mocks. It calls the real honest_test.generate_scaffolding.
"""

from honest_test import generate_scaffolding


def probe_generate_scaffolding():
    bad = []
    chain_name = "create_user_pipeline"
    links = [{"name": "validate_user"}, {"name": "insert_user"}]

    source = generate_scaffolding(chain_name, links)
    if not isinstance(source, str):
        return [f"generate_scaffolding returned {source!r}, expected a source string"]
    if not source.strip():
        return ["generate_scaffolding returned an empty string"]

    if "do not edit" not in source.lower():
        bad.append("the scaffolding carries no do-not-edit banner")
    if "def register(registry)" not in source:
        bad.append("the scaffolding has no register(registry) function")
    if "return registry" not in source:
        bad.append("the scaffolding's register does not return the registry")
    if chain_name not in source:
        bad.append(f"the scaffolding does not name the chain {chain_name!r}")
    return bad


def run():
    messages = probe_generate_scaffolding()
    if messages:
        print(f"FAIL HTEST-probe [generate_scaffolding]: {messages}")
    print(f"generate_scaffolding: {0 if messages else 1} passed, {1 if messages else 0} failed, 1 total")
    return 1 if messages else 0


if __name__ == "__main__":
    raise SystemExit(run())

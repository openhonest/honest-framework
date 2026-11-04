"""Conformance fragment for the generate_scaffolding scenario (honest-test.feature).

Scenario: generate_scaffolding generates the Gherkin step scaffolding for a chain
  from its link declarations.
  Then it returns a step-module source string whose handlers are pure functions that
  take the immutable context plus bound captures and return a new context, wired
  through a register(registry) that returns the registry — never through decorators
  or a mutable shared context, matching honest-gherkin's step-module contract.
  And the developer writes only the .feature files against this scaffolding, which is
  marked do-not-edit.
  And it reads no world and returns the generated source as a string.

Cases are data; one pure probe feeds them to the real function and returns a list of
failure strings (empty when every case holds). No classes, no mocks: it calls the real
honest_test.generate_scaffolding on Link records in the shape honest-type's link_meta()
produces (name, accepts, binds, boundary, authorizes, emits).

The output is a source string, so the probe asserts STRUCTURAL properties the note
fixes, not an exact byte match:
  (a) non-empty;
  (b) a def register(registry) that returns the registry;
  (c) each link's name is referenced;
  (d) a do-not-edit marker is present;
  (e) no step decorators (@given/@when/@then/@step), since handlers are plain functions.

This is its own fragment file so other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py are untouched.
"""

from honest_test import generate_scaffolding


def _link(name, boundary=False, authorizes=False, emits=None):
    """A Link record in the shape honest-type's link_meta() produces."""
    return {
        "name": name,
        "accepts": None,
        "binds": None,
        "boundary": boundary,
        "authorizes": authorizes,
        "emits": emits if emits is not None else [],
    }


_CASES = [
    # A chain of two declared links. The scaffolding must name both links.
    {
        "given": {
            "chain_name": "signup_chain",
            "links": [
                _link("recognize_email", boundary=True),
                _link("persist_account", emits=["account_created"]),
            ],
        },
        "expect_link_names": ["recognize_email", "persist_account"],
    },
    # A three-link chain, to confirm every link's name is carried, not just the first.
    {
        "given": {
            "chain_name": "checkout_chain",
            "links": [
                _link("validate_cart", boundary=True),
                _link("charge_card"),
                _link("record_order", emits=["order_placed"]),
            ],
        },
        "expect_link_names": ["validate_cart", "charge_card", "record_order"],
    },
]

# Decorator forms the note forbids: handlers are plain functions, never decorators.
_FORBIDDEN_DECORATORS = ("@given", "@when", "@then", "@step")


def probe_generate_scaffolding():
    """generate_scaffolding returns a do-not-edit step module whose register(registry) returns the registry and whose decorator-free handlers name every link in the chain."""
    bad = []
    for case in _CASES:
        src = generate_scaffolding(**case["given"])

        if not isinstance(src, str):
            bad.append(
                f"generate_scaffolding({case['given']}) -> {type(src).__name__}, "
                f"expected a source string"
            )
            continue

        # (a) non-empty: the note says it returns the generated source as a string.
        if src.strip() == "":
            bad.append(
                f"generate_scaffolding({case['given']}) returned an empty string; "
                f"expected a step-module source"
            )
            continue

        # (b) register(registry) that returns the registry.
        if "def register(registry)" not in src:
            bad.append(
                f"generate_scaffolding({case['given']}) has no "
                f"'def register(registry)'"
            )
        if "return registry" not in src:
            bad.append(
                f"generate_scaffolding({case['given']}) register() does not "
                f"'return registry'"
            )

        # (c) each link's name is referenced.
        for name in case["expect_link_names"]:
            if name not in src:
                bad.append(
                    f"generate_scaffolding({case['given']}) does not reference "
                    f"link name {name!r}"
                )

        # (d) a do-not-edit marker is present (wording not fixed by the scenario).
        low = src.lower()
        if "do not edit" not in low and "do-not-edit" not in low:
            bad.append(
                f"generate_scaffolding({case['given']}) carries no do-not-edit marker"
            )

        # (e) no step decorators: handlers are plain functions, not decorated steps.
        for decorator in _FORBIDDEN_DECORATORS:
            if decorator in src:
                bad.append(
                    f"generate_scaffolding({case['given']}) uses forbidden step "
                    f"decorator {decorator!r}; handlers must be plain functions"
                )

    return bad


def run():
    bad = probe_generate_scaffolding()
    for line in bad:
        print(line)
    print(f"probe_generate_scaffolding: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

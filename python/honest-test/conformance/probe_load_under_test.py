"""Conformance fragment for the load_under_test scenario (honest-test.feature ~line 32).

Scenario: load_under_test imports each module under test to obtain its live declarations.
  Then it imports each module under src_dir, running each module's own top-level code
  into the running interpreter, so it is a boundary and not pure analysis.
  And it returns a LiveModules record carrying the live vocabularies, bindings, links,
  chains, machines, schemas, components, providers and gates for the orchestrator to
  thread into the checks that must call real functions.
  And it asks honest-type to tell a link from an ordinary function and read its declared
  vocabulary and binding off each imported module through the honest-type.link_meta seam.

load_under_test is a reader (a boundary): it imports real modules off the filesystem.
So this probe tests the REAL effect — it builds a fresh temp source directory holding
one tiny module that declares a live vocabulary (honest_type.vocabulary) and a live link
(honest_type.link, whose declared `accepts` is that vocabulary), points the real
load_under_test at that directory, and asserts the returned LiveModules record carries
the declarations found.

No mocks, no patching: it calls the real honest_type to build the declarations the temp
module holds, and the real honest_test.load_under_test to discover them. The absence case
is explicit — the temp module declares no state machine, schema, component, provider or
gate, so those lists must be empty.

This is its own fragment file so the other scenarios' fragments never collide with it.
run_conformance.py / laws_htest.py / suite.json are untouched.

DISCOVERY-CONTRACT GAP: section 11 of honest-test-architecture.md and the load_under_test
note say the loader "imports each module to obtain its live vocabularies, links, chains,
and state machines" and "ask[s] honest-type to tell a link from an ordinary function and
read its declared vocabulary and binding off it" — but neither pins HOW a module exposes
each declaration kind for discovery (a scan of module-level attributes? a registry? an
__all__ export? a src/ package layout?). The clearest interpretation grounded in the note
is encoded here: a module-level function honest-type's is_link recognizes is a link, and a
vocabulary is read off that link's declared `accepts` (link_meta). The vocabularies and
bindings discovery contract is flagged as a gap (owner: hd/spec).
"""

import os
import tempfile

from honest_type import is_link, link_meta, vocabulary

from honest_test import load_under_test

# The one declaration the temp module holds: a 3-member Set vocabulary, and a link whose
# declared `accepts` is that vocabulary and whose `emits` is a distinguishing literal.
_VOCAB = vocabulary({"color": {"red", "green", "blue"}})
_EMITS = "rendered_cell"

# The temp module's source. It imports the real honest_type (importable in the loading
# interpreter) and declares exactly one live link over exactly one live vocabulary, and
# nothing else — no state machine, schema, component, provider or gate.
_MODULE_SOURCE = '''\
import honest_type as ht

catalog = ht.vocabulary({"color": {"red", "green", "blue"}})


@ht.link(accepts=catalog, emits="rendered_cell")
def render_cell(manifest):
    return manifest
'''

# The kinds the temp module declares none of: each matching LiveModules list must be empty.
_ABSENT_KINDS = ("machines", "schemas", "components", "providers", "gates")


def probe_load_under_test():
    """load_under_test imports the module under src_dir and returns a LiveModules record carrying the live link it declared (recognized via is_link, its vocabulary read off link_meta), with empty lists for the kinds the module declares none of."""
    bad = []
    src_dir = tempfile.mkdtemp(prefix="probe_lut_")
    module_path = os.path.join(src_dir, "sample_module.py")
    with open(module_path, "w") as handle:
        handle.write(_MODULE_SOURCE)

    got = load_under_test(src_dir)

    if not isinstance(got, dict):
        bad.append(f"load_under_test({src_dir!r}) -> {got!r}, expected a LiveModules record (dict)")
        return bad

    links = got.get("links", [])
    if len(links) != 1:
        bad.append(
            f"load_under_test({src_dir!r})['links'] has {len(links)} entries, "
            f"expected 1 (the one declared link render_cell)"
        )
    else:
        the_link = links[0]
        if not is_link(the_link):
            bad.append(
                f"load_under_test({src_dir!r})['links'][0] is not recognized by "
                f"honest_type.is_link, expected the declared link"
            )
        else:
            emits = link_meta(the_link).get("emits")
            if emits != _EMITS:
                bad.append(
                    f"load_under_test({src_dir!r})['links'][0] link_meta emits={emits!r}, "
                    f"expected {_EMITS!r}"
                )

    # The vocabulary read off the link's declared `accepts` (the note's stated seam).
    vocabs = got.get("vocabularies", [])
    if _VOCAB not in vocabs:
        bad.append(
            f"load_under_test({src_dir!r})['vocabularies']={vocabs!r} does not carry the "
            f"declared vocabulary {_VOCAB!r}"
        )

    for kind in _ABSENT_KINDS:
        values = got.get(kind, None)
        if values != []:
            bad.append(
                f"load_under_test({src_dir!r})[{kind!r}]={values!r}, expected [] "
                f"(the module declares no {kind})"
            )

    return bad


def run():
    bad = probe_load_under_test()
    for line in bad:
        print(line)
    print(f"probe_load_under_test: {len(bad)} failure(s)")
    return bad


if __name__ == "__main__":
    import sys

    sys.exit(1 if run() else 0)

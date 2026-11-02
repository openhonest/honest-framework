"""extract_state_machines recognizes every state machine the source declares
(honest-check.hd, spec section 3.4, section 3.5). It is the public counterpart of the
state_machines honest-check builds in its declaration graph for the HC-SM rules:
honest-test hands in the parsed root, the source bytes, and the alias map, and
extract_state_machines returns one MachineDecl { name } per state machine the file
declares — the name bound to the machine.

A state machine is a module-level assignment whose right side is a `state_machine(...)`
call (recognized through the alias map, so a direct call and an aliased one both count);
name is the assignment target. Pins the contract: the name for a direct machine, the same
through an alias, and the empty list when the file declares none. A stub returning []
fails cases 1 and 2.
"""

_CASES = [
    # A direct state_machine(...) assignment: name is the target.
    {
        "source": (
            "from honest_type import state_machine\n"
            'door = state_machine(states, events, transitions, "closed")\n'
        ),
        "want": [{"name": "door"}],
    },
    # The same through an alias: `state_machine as sm`, then `sm(...)`.
    {
        "source": (
            "from honest_type import state_machine as sm\n"
            'gate = sm(states, events, transitions, "open")\n'
        ),
        "want": [{"name": "gate"}],
    },
    # A file with no state machine yields the empty list; a chain is not a state machine.
    {
        "source": "from honest_type import chain\nc = chain(a, b)\n",
        "want": [],
    },
    # A non-constructor call assigned to a name is not a state machine.
    {
        "source": "from honest_type import state_machine\nm = other(a, b)\n",
        "want": [],
    },
    # A dotted call is not a state machine: the called function is an attribute, not a bare
    # identifier, so it resolves to no constructor.
    {
        "source": "from honest_type import state_machine\nm = mod.state_machine(a)\n",
        "want": [],
    },
    # A state_machine call assigned to a non-identifier target is not a declaration.
    {
        "source": "from honest_type import state_machine\nobj.attr = state_machine(a, b, c, d)\n",
        "want": [],
    },
    # A bare `state_machine(...)` with no import is still recognized through the
    # constructor-name branch, which an aliased import would otherwise decide.
    {
        "source": 'door = state_machine(states, events, transitions, "closed")\n',
        "want": [{"name": "door"}],
    },
]


def probe_extract_state_machines():
    try:
        from honest_check.declgraph import extract_state_machines, resolve_aliases
    except ImportError as exc:
        return [
            f"cannot import extract_state_machines from honest_check.declgraph: {exc}"
        ]
    from honest_parse import parse

    bad = []
    for case in _CASES:
        source = case["source"].encode("utf-8")
        root = parse(source, "python").root_node
        aliases = resolve_aliases(root, source)
        got = extract_state_machines(root, source, aliases)
        if got != case["want"]:
            bad.append(
                f"extract_state_machines over {case['source']!r} -> {got!r}, "
                f"expected {case['want']!r}"
            )
    return bad

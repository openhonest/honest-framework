"""check_r006 (in cross_declaration) fires when a declared door transforms its input: a
boundary_in, boundary_out or reader whose body builds a record or renders a representation
rather than only touching the world and handing the value on (§HC-R006).

Pins six cases. Each gives a module .hd and a source file, both parsed through honest-design's
read_hd and honest-parse (not the function under test), and runs cross_declaration over them with
rule_ids ["HC-R006"]. A reader that builds a dict from the data it read fires; a reader that
returns the value it read passes; a reader that holds a comprehension fires; a boundary_out that
hands a record straight to json.dumps is at the format boundary and passes; a plain fn that builds
a record is not a door and is skipped; a door that passes a value straight through its own return
passes.

Spec authority: §HC-R006 (honest-check-architecture.md, line 1387).
"""

_CASES = [
    {
        "name": "HC-R006 fires on a reader that builds a record from read data",
        "hd": 'module m\n  reader fn load : (p: str) -> any side_effect reads "file"\n',
        "source": 'def load(p):\n    data = read(p)\n    return {"a": data, "b": data}\n',
        "want_fire": True,
    },
    {
        "name": "HC-R006 fires on a reader that holds a comprehension",
        "hd": 'module m\n  reader fn load : (p: str) -> any side_effect reads "file"\n',
        "source": 'def load(p):\n    rows = read(p)\n    return [row.strip() for row in rows]\n',
        "want_fire": True,
    },
    {
        "name": "HC-R006 clean when the reader passes the value through",
        "hd": 'module m\n  reader fn load : (p: str) -> any side_effect reads "file"\n',
        "source": 'def load(p):\n    return read(p)\n',
        "want_fire": False,
    },
    {
        "name": "HC-R006 clean at the format boundary (json.dumps)",
        "hd": 'module m\n  boundary_out fn write : (record: any, conn: any) -> any side_effect writes "file"\n',
        "source": 'def write(record, conn):\n    return conn.send(json.dumps({"k": record}))\n',
        "want_fire": False,
    },
    {
        "name": "HC-R006 skips a plain fn that builds a record",
        "hd": 'module m\n  fn shape : (data: any) -> any\n',
        "source": 'def shape(data):\n    return {"a": data, "b": data}\n',
        "want_fire": False,
    },
    {
        "name": "HC-R006 clean when a boundary_out writes the value it was handed",
        "hd": 'module m\n  boundary_out fn write : (text: str) -> bool side_effect writes "stdout"\n',
        "source": 'def write(text):\n    print(text)\n    return True\n',
        "want_fire": False,
    },
]


def probe_check_hc_r006():
    try:
        from honest_check.crossing import cross_declaration
    except ImportError as exc:
        return [f"cannot import cross_declaration: {exc}"]
    from honest_design import read_hd

    bad = []
    for case in _CASES:
        parsed = read_hd(case["hd"])
        if "ok" not in parsed:
            bad.append(f"{case['name']}: .hd did not parse: {parsed.get('err')!r}")
            continue
        declaration = parsed["ok"]["modules"][0]
        got = cross_declaration([{"path": "m.py", "text": case["source"]}], declaration, "", ["HC-R006"])
        if not isinstance(got, list):
            bad.append(f"{case['name']}: cross_declaration -> {got!r}, expected a list")
            continue
        fired = [d for d in got if d.get("rule_id") == "HC-R006"]
        if case["want_fire"] and not fired:
            bad.append(f"{case['name']}: HC-R006 did not fire, expected it to fire")
        elif not case["want_fire"] and fired:
            bad.append(f"{case['name']}: HC-R006 fired, expected it to stay silent")
        elif case["want_fire"] and fired and fired[0].get("severity") != "error":
            bad.append(f"{case['name']}: HC-R006 fired at {fired[0].get('severity')!r}, expected 'error'")
    return bad

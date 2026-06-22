"""honest-gherkin conformance: the generative proof (the behavioural circle).

What the data file cannot easily express: tag attachment, the And/But resolved kind, the
description capture, source-line tracking, and the malformed-input fault paths. Each probe
returns a list of failures; run() aggregates.
"""

import re

from honest_gherkin import (
    compile_pattern,
    empty_registry,
    match_step,
    parse_feature,
    register_step,
)


def _step(text):
    return {"kind": "given", "resolved_kind": "given", "text": text, "source_line": 1}


def _probe_registry():
    """empty_registry / register_step / match_step (§5, §5.1): registration is a value (never a
    global), register_step never mutates its argument, and match_step returns a Result with coerced
    captures — exactly one match -> ok, none -> step_unmatched, more than one -> ambiguous_step."""
    bad = []

    def handler(context):
        return context

    if empty_registry() != {"patterns": []}:
        bad.append("empty_registry should be a registry value with no patterns")

    # register_step appends and returns a NEW registry; the argument is untouched (no shared state).
    r0 = empty_registry()
    r1 = register_step(r0, "given", 'a user named "{name}"', handler)
    r2 = register_step(r1, "when", "they add {x:int}", handler)
    if r0["patterns"] != []:
        bad.append("register_step must not mutate its argument")
    if [p["kind"] for p in r2["patterns"]] != ["given", "when"]:
        bad.append(f"register_step should append in order: {[p['kind'] for p in r2['patterns']]}")
    if r2["patterns"][0]["handler"] is not handler:
        bad.append("the registered pattern should carry its handler")

    # Exactly one match -> ok(StepMatch) with the matched pattern and coerced captures.
    one = match_step(_step('a user named "Ada"'), r2)
    if "ok" not in one or one["ok"]["captures"] != {"name": "Ada"}:
        bad.append(f"a single str match should bind the capture: {one}")
    if one.get("ok", {}).get("pattern", {}).get("handler") is not handler:
        bad.append("the StepMatch should carry the matched pattern (handler included)")
    coerced = match_step(_step("they add 42"), r2)
    if "ok" not in coerced or coerced["ok"]["captures"] != {"x": 42}:
        bad.append(f"an int capture should be coerced to int, not left a string: {coerced}")

    # Zero matches -> step_unmatched; more than one -> ambiguous_step.
    none = match_step(_step("nothing matches this"), r2)
    if none.get("err", {}).get("code") != "step_unmatched":
        bad.append(f"no match should return step_unmatched: {none}")
    ambiguous = register_step(register_step(empty_registry(), "given", "a {x}", handler), "given", "{y} z", handler)
    amb = match_step(_step("a z"), ambiguous)
    if amb.get("err", {}).get("code") != "ambiguous_step":
        bad.append(f"more than one match should return ambiguous_step: {amb}")

    # A registered pattern that fails to compile cannot match: it is skipped, not raised.
    with_bad = register_step(register_step(empty_registry(), "given", "a {x:widget}", handler), "given", "good step", handler)
    skipped = match_step(_step("good step"), with_bad)
    if "ok" not in skipped:
        bad.append(f"a non-compiling pattern should be skipped, leaving the good match: {skipped}")
    only_bad = match_step(_step("a value"), register_step(empty_registry(), "given", "a {x:widget}", handler))
    if only_bad.get("err", {}).get("code") != "step_unmatched":
        bad.append(f"when only a non-compiling pattern is present, the step is unmatched: {only_bad}")
    return bad


def _probe_parse():
    """parse_feature (§3): the Feature IR, tags, resolved step kind, description, and the
    bad_feature_syntax faults."""
    bad = []

    source = (
        "Feature: Orders\n"
        "  Orders can be placed.\n"
        "\n"
        "  @smoke @fast\n"
        "  Scenario: place an order\n"
        "    Given an empty cart\n"
        "    And a logged-in user\n"
        "    When the order is placed\n"
        "    Then it is recorded\n"
        "    But no email is sent\n"
    )
    result = parse_feature(source, "orders.feature")
    if "ok" not in result:
        bad.append(f"a well-formed feature should parse: {result}")
        return bad
    feature = result["ok"]

    if feature["name"] != "Orders" or feature["source_path"] != "orders.feature":
        bad.append(f"feature name/path wrong: {feature['name']}, {feature['source_path']}")
    if feature["description"] != "Orders can be placed.":
        bad.append(f"description capture wrong: {feature['description']!r}")
    if feature["background_steps"] != []:
        bad.append("background_steps must be [] in M1")
    if len(feature["scenarios"]) != 1:
        bad.append(f"expected one scenario: {len(feature['scenarios'])}")
        return bad

    scenario = feature["scenarios"][0]
    if scenario["name"] != "place an order":
        bad.append(f"scenario name wrong: {scenario['name']!r}")
    if scenario["tags"] != ["@smoke", "@fast"]:
        bad.append(f"tags should attach to the next scenario: {scenario['tags']}")

    steps = scenario["steps"]
    if [s["kind"] for s in steps] != ["given", "and", "when", "then", "but"]:
        bad.append(f"literal step kinds wrong: {[s['kind'] for s in steps]}")
    # And/But resolve to the kind of the most recent Given/When/Then.
    if steps[1].get("resolved_kind") != "given" or steps[4].get("resolved_kind") != "then":
        bad.append(f"And/But resolved kind wrong: {[s.get('resolved_kind') for s in steps]}")
    if steps[0]["text"] != "an empty cart":
        bad.append(f"step text should have the keyword stripped: {steps[0]['text']!r}")
    if steps[0]["source_line"] != 6:
        bad.append(f"step source_line should be 1-based: {steps[0]['source_line']}")

    # Faults as data: a step before any scenario, and a nameless scenario.
    orphan = parse_feature("Feature: X\n  Given a step\n", "x.feature")
    if orphan.get("err", {}).get("code") != "bad_feature_syntax":
        bad.append(f"a step outside a scenario should fault: {orphan}")
    nameless = parse_feature("Feature: X\n\n  Scenario:\n    Given a\n", "x.feature")
    if nameless.get("err", {}).get("code") != "bad_feature_syntax":
        bad.append(f"a nameless scenario should fault: {nameless}")
    # Stray non-keyword text after a scenario (a description line outside the header) faults.
    stray = parse_feature("Feature: X\n\n  Scenario: s\n    Given a\n  loose text here\n", "x.feature")
    if stray.get("err", {}).get("code") != "bad_feature_syntax":
        bad.append(f"loose text outside a scenario should fault: {stray}")
    # No Feature line at all faults.
    no_feature = parse_feature("Scenario: s\n    Given a\n", "x.feature")
    if no_feature.get("err", {}).get("code") != "bad_feature_syntax":
        bad.append(f"a feature with no Feature line should fault: {no_feature}")
    return bad


def _probe_compile():
    """compile_pattern (§4): named captures per placeholder, recorded types, full-text anchoring,
    literal escaping, and the unknown-type fault. The regex dialect is the host's (§1.5), so the
    behaviour is checked by matching with the host engine, not by asserting the regex string."""
    bad = []

    # str (the default type): the capture binds a run of non-quote text.
    word = compile_pattern('say "{word}"')
    if "ok" not in word:
        bad.append(f"a valid pattern should compile: {word}")
        return bad
    match = re.match(word["ok"]["regex"], 'say "hello"')
    if match is None or match.group("word") != "hello":
        bad.append("the str capture should bind the quoted text")
    # Anchored full-text: a substring occurrence does not match.
    if re.match(word["ok"]["regex"], 'now say "hi" loudly') is not None:
        bad.append("the compiled pattern must be anchored (full-text, not substring)")

    # int and float types match signed numbers and record their types.
    nums = compile_pattern("n {x:int} f {y:float}")
    if nums["ok"]["captures"] != [{"name": "x", "type": "int"}, {"name": "y", "type": "float"}]:
        bad.append(f"captures should record name and type: {nums['ok']['captures']}")
    nm = re.match(nums["ok"]["regex"], "n -42 f 3.14")
    if nm is None or nm.group("x") != "-42" or nm.group("y") != "3.14":
        bad.append("int/float fragments should match signed numbers")
    if re.match(compile_pattern("{x:int}")["ok"]["regex"], "abc") is not None:
        bad.append("the int fragment should not match non-digits")

    # No placeholder: a literal pattern matches itself, and special characters are escaped.
    if re.match(compile_pattern("plain text")["ok"]["regex"], "plain text") is None:
        bad.append("a literal pattern should match itself")
    if re.match(compile_pattern("a.b")["ok"]["regex"], "axb") is not None:
        bad.append("a literal '.' should be escaped, not match any character")

    # Unknown placeholder type -> fault as data, never raised.
    if compile_pattern("a {x:widget}").get("err", {}).get("code") != "bad_feature_syntax":
        bad.append("an unknown placeholder type should return bad_feature_syntax")
    return bad


def run():
    probes = {"parse": _probe_parse(), "compile": _probe_compile(), "registry": _probe_registry()}
    violations = [(name, messages) for name, messages in probes.items() if messages]
    for name, messages in violations:
        print(f"FAIL HG-probe [{name}]: {messages}")
    passed = sum(1 for messages in probes.values() if not messages)
    print(f"HG laws: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())

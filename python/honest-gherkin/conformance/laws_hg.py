"""honest-gherkin conformance: the generative proof (the behavioural circle).

What the data file cannot easily express: tag attachment, the And/But resolved kind, the
description capture, source-line tracking, and the malformed-input fault paths. Each probe
returns a list of failures; run() aggregates.
"""

from honest_gherkin import parse_feature


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


def run():
    probes = {"parse": _probe_parse()}
    violations = [(name, messages) for name, messages in probes.items() if messages]
    for name, messages in violations:
        print(f"FAIL HG-probe [{name}]: {messages}")
    passed = sum(1 for messages in probes.values() if not messages)
    print(f"HG laws: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())

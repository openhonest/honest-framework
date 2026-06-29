"""honest-gherkin conformance: the generative proof (the behavioural circle).

What the data file cannot easily express: tag attachment, the And/But resolved kind, the
description capture, source-line tracking, and the malformed-input fault paths. Each probe
returns a list of failures; run() aggregates.
"""

import io
import re
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

import honest_gherkin.run as run_module
from honest_gherkin import (
    compile_pattern,
    empty_registry,
    fold_feature_report,
    match_step,
    parse_feature,
    register_step,
    run_scenario,
    run_step,
    step_fault,
)
from honest_gherkin.cli import (
    _discover_features,
    _load_steps,
    _parse_failure_report,
    main,
    run_feature_file,
)
from honest_gherkin.run import _classify_exception


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

    # The match-fault details are part of the fault (§7): assert them exactly. The unmatched detail
    # carries the step text; the ambiguous detail lists the competing patterns, ", "-separated in
    # registration order — this pins both message prefixes and the join separator.
    nomatch = match_step(_step("unheard of"), empty_registry())
    if nomatch.get("err", {}).get("detail") != "no registered step matches: 'unheard of'":
        bad.append(f"the unmatched detail should quote the step text: {nomatch}")
    two = register_step(register_step(empty_registry(), "given", "a {x}", handler), "given", "{y} z", handler)
    amb_detail = match_step(_step("a z"), two)
    if amb_detail.get("err", {}).get("detail") != "step matches more than one pattern: 'a {x}', '{y} z'":
        bad.append(f"the ambiguous detail should list the competing patterns: {amb_detail}")
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

    # Each fault detail is part of the fault (§7); assert them exactly, and that parse returns the
    # FIRST error when several occur (not the last).
    if nameless.get("err", {}).get("detail") != "line 3: scenario has no name":
        bad.append(f"nameless-scenario detail wrong: {nameless}")
    if orphan.get("err", {}).get("detail") != "line 2: step outside a scenario":
        bad.append(f"orphan-step detail wrong: {orphan}")
    if stray.get("err", {}).get("detail") != "line 5: unexpected text outside a scenario":
        bad.append(f"stray-text detail wrong: {stray}")
    if no_feature.get("err", {}).get("detail") != "no Feature declared":
        bad.append(f"no-Feature detail wrong: {no_feature}")
    two_errors = parse_feature("Feature: X\n  Given orphan\n  Scenario:\n    Given a\n", "x.feature")
    if two_errors.get("err", {}).get("detail") != "line 2: step outside a scenario":
        bad.append(f"parse should return the first error, not the last: {two_errors}")

    # A richer feature pins the state the simple probe leaves implicit: a comment is ignored (never
    # folded into the description), a multi-line description joins with single spaces, only @-tokens
    # become tags and they attach to the next scenario only (resetting between scenarios), the
    # scenario source_line is recorded, And/But resolve to the most recent Given/When/Then, and the
    # resolved kind resets at each scenario boundary.
    rich = (
        "Feature: Shop\n"
        "  It sells things.\n"
        "  Across the web.\n"
        "  # a comment, never part of the description\n"
        "  @smoke notatag\n"
        "  Scenario: checkout\n"
        "    Given a cart\n"
        "    And an item\n"
        "    When the order is placed\n"
        "    Then it totals\n"
        "    But nothing ships\n"
        "  @other\n"
        "  Scenario: refund\n"
        "    And a prior order\n"
    )
    rich_result = parse_feature(rich, "shop.feature")
    if "ok" not in rich_result:
        bad.append(f"the rich feature should parse: {rich_result}")
        return bad
    shop = rich_result["ok"]
    if shop["description"] != "It sells things. Across the web.":
        bad.append(f"description joins lines with single spaces and excludes comments: {shop['description']!r}")
    if len(shop["scenarios"]) != 2:
        bad.append(f"expected two scenarios: {len(shop['scenarios'])}")
        return bad
    checkout, refund = shop["scenarios"]
    if checkout["tags"] != ["@smoke"]:
        bad.append(f"only @-tokens attach as tags: {checkout['tags']}")
    if refund["tags"] != ["@other"]:
        bad.append(f"pending tags reset between scenarios: {refund['tags']}")
    if checkout["source_line"] != 6:
        bad.append(f"scenario source_line should be recorded 1-based: {checkout['source_line']}")
    if [s["resolved_kind"] for s in checkout["steps"]] != ["given", "given", "when", "then", "then"]:
        bad.append(f"And/But resolve to the most recent Given/When/Then: {[s['resolved_kind'] for s in checkout['steps']]}")
    if refund["steps"][0]["resolved_kind"] != "":
        bad.append(f"the resolved kind resets at each scenario boundary: {refund['steps'][0]['resolved_kind']!r}")
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

    # Unknown placeholder type -> fault as data, never raised; the detail is part of the fault (§7).
    unknown = compile_pattern("a {x:widget}")
    if unknown.get("err", {}).get("code") != "bad_feature_syntax":
        bad.append("an unknown placeholder type should return bad_feature_syntax")
    if unknown.get("err", {}).get("detail") != "unknown placeholder type 'widget' in pattern: a {x:widget}":
        bad.append(f"the unknown-type detail should name the type and pattern: {unknown}")

    # Anchored at BOTH ends (§4, full-text not substring). The leading ^: re.search (unlike re.match)
    # would otherwise find the pattern mid-string, so a leading-junk string must not match. The
    # trailing $: a valid prefix with trailing junk must not match under re.match either.
    if re.search(compile_pattern("plain text")["ok"]["regex"], "x plain text") is not None:
        bad.append("the compiled regex must be anchored at the start (^), not only the end")
    if re.match(compile_pattern("plain text")["ok"]["regex"], "plain text extra") is not None:
        bad.append("the compiled regex must be anchored at the end ($), not only the start")
    return bad


def _probe_run():
    """run_step / run_scenario / fold_feature_report / _classify_exception / _now_ms (§6, §7.1):
    fold steps over an empty immutable context, thread context through, stop at the first non-ok
    step, classify a caught handler exception into the fault vocabulary, and combine reports."""
    bad = []

    def set_user(context):
        return {**context, "user": "ada"}

    def keep(context):
        return None  # a falsey return is treated as the unchanged context (§6.1)

    def check_user(context):
        assert context.get("user") == "ada"
        return context

    def check_missing(context):
        assert context.get("user") == "missing"
        return context

    def boom(context):
        raise ValueError("kaboom")

    registry = empty_registry()
    registry = register_step(registry, "given", "a user named ada", set_user)
    registry = register_step(registry, "given", "nothing changes", keep)
    registry = register_step(registry, "then", "the user is ada", check_user)
    registry = register_step(registry, "then", "the user is missing", check_missing)
    registry = register_step(registry, "when", "it explodes", boom)

    def scenario(name, texts):
        steps = [{"kind": "given", "resolved_kind": "given", "text": t, "source_line": 1} for t in texts]
        return {"name": name, "steps": steps, "tags": [], "source_line": 1}

    # All steps ok: context threads through; status ok; duration is a non-negative int.
    passing = scenario("pass", ["a user named ada", "nothing changes", "the user is ada"])
    report = run_scenario(passing, [], registry)
    if report["status"] != "ok":
        bad.append(f"a passing scenario should be ok: {report}")
    if [r["status"] for r in report["step_results"]] != ["ok", "ok", "ok"]:
        bad.append(f"every executed step should be ok: {[r['status'] for r in report['step_results']]}")
    if not isinstance(report["duration_ms"], int) or report["duration_ms"] < 0:
        bad.append(f"duration_ms should be a non-negative int: {report['duration_ms']!r}")

    # Background steps run first, and their context threads into the scenario's own steps.
    bg_step = {"kind": "given", "resolved_kind": "given", "text": "a user named ada", "source_line": 1}
    bg_report = run_scenario(scenario("bg", ["the user is ada"]), [bg_step], registry)
    if bg_report["status"] != "ok":
        bad.append(f"background should run first and thread context into the scenario: {bg_report}")

    # A failing Then (assertion) stops the scenario; the failed step is reported, later steps are not.
    failing = scenario("fail", ["a user named ada", "the user is missing", "the user is ada"])
    fr = run_scenario(failing, [], registry)
    if fr["status"] != "err":
        bad.append(f"a failing scenario should be err: {fr}")
    if len(fr["step_results"]) != 2:
        bad.append(f"M1 stops at the first non-ok step and does not report the rest: {fr['step_results']}")
    last = fr["step_results"][-1]
    if last["status"] != "failed" or last["fault"]["code"] != "assertion_failed":
        bad.append(f"an assertion failure -> failed / assertion_failed: {last}")
    if last["fault"]["scenario_name"] != "fail":
        bad.append(f"the fault should carry the scenario name: {last['fault']}")

    # Any other handler exception -> errored / step_errored.
    err_report = run_scenario(scenario("boom", ["it explodes"]), [], registry)
    eb = err_report["step_results"][-1]
    if err_report["status"] != "err" or eb["status"] != "errored" or eb["fault"]["code"] != "step_errored":
        bad.append(f"a non-assertion exception -> errored / step_errored: {err_report}")

    # An unmatched step -> unmatched / step_unmatched (no exception involved); ok steps before it stand.
    um = run_scenario(scenario("um", ["this matches nothing"]), [], registry)
    ub = um["step_results"][-1]
    if um["status"] != "err" or ub["status"] != "unmatched" or ub["fault"]["code"] != "step_unmatched":
        bad.append(f"an unmatched step -> unmatched / step_unmatched: {um}")

    # An ambiguous step -> ambiguous / ambiguous_step.
    amb_registry = register_step(register_step(empty_registry(), "given", "a {x}", set_user), "given", "{y} thing", set_user)
    amb = run_scenario(scenario("amb", ["a thing"]), [], amb_registry)
    ab = amb["step_results"][-1]
    if amb["status"] != "err" or ab["status"] != "ambiguous" or ab["fault"]["code"] != "ambiguous_step":
        bad.append(f"an ambiguous step -> ambiguous / ambiguous_step: {amb}")

    # _classify_exception directly: AssertionError is the specific row, anything else hits the catch-all.
    if _classify_exception(AssertionError("x")) != ("failed", "assertion_failed"):
        bad.append("AssertionError should classify as failed / assertion_failed")
    if _classify_exception(KeyError("x")) != ("errored", "step_errored"):
        bad.append("a non-assertion exception should hit the catch-all errored / step_errored")

    # fold_feature_report: total_passed counts ok scenarios; the rest fail; metadata is carried.
    feature = {"name": "F", "description": "", "scenarios": [], "background_steps": [], "source_path": "f.feature"}
    combined = fold_feature_report(feature, [report, fr, bg_report])
    if combined["total_passed"] != 2 or combined["total_failed"] != 1:
        bad.append(f"fold should count ok vs non-ok scenarios: {combined}")
    if combined["feature_name"] != "F" or combined["source_path"] != "f.feature":
        bad.append(f"fold should carry the feature name and path: {combined}")

    # The scenario report carries its name (pins the "name" key/value in run_scenario's return).
    if report["name"] != "pass":
        bad.append(f"run_scenario should carry the scenario name: {report['name']!r}")

    # run_step directly (§6.1): assert the FULL return for each path, so every key (result/step/
    # status/fault/context), the echoed step, and the threaded context are pinned — not just status.
    def grab(context):
        return {**context, "seen": True}

    direct = register_step(empty_registry(), "given", "advance", grab)
    ok_out = run_step(_step("advance"), {"x": 1}, direct, "sc")
    if ok_out != {"result": {"step": _step("advance"), "status": "ok", "fault": None}, "context": {"x": 1, "seen": True}}:
        bad.append(f"run_step ok path: full shape wrong: {ok_out}")
    miss = run_step(_step("no such step"), {"x": 1}, direct, "sc")
    if miss["result"]["step"] != _step("no such step") or miss["result"]["status"] != "unmatched" or miss["context"] != {"x": 1}:
        bad.append(f"run_step unmatched path: step echoed, status, context unchanged: {miss}")

    # The errored detail is the exception message; a message-less exception falls back to the class
    # name (pins `str(exc) or type(exc).__name__` — both operands).
    def boom(context):
        raise ValueError("kaboom")

    def blank_boom(context):
        raise ValueError()

    direct = register_step(register_step(direct, "when", "explode", boom), "when", "implode", blank_boom)
    boom_step = {"kind": "when", "resolved_kind": "when", "text": "explode", "source_line": 1}
    spoke = run_step(boom_step, {"y": 2}, direct, "sc")
    if spoke["result"]["step"] != boom_step or spoke["result"]["status"] != "errored" or spoke["context"] != {"y": 2} or spoke["result"]["fault"]["detail"] != "kaboom":
        bad.append(f"run_step errored path: step/status/context/message detail wrong: {spoke}")
    blank = run_step({"kind": "when", "resolved_kind": "when", "text": "implode", "source_line": 1}, {}, direct, "sc")
    if blank["result"]["fault"]["detail"] != "ValueError":
        bad.append(f"a message-less exception should use the class name as detail: {blank}")

    # duration_ms is milliseconds: stub the clock (the one sanctioned impure seam, §6.2) to a known
    # delta and assert the *1000.0 conversion factor exactly.
    saved_clock = run_module.time.perf_counter
    ticks = iter([10.0, 12.5])
    run_module.time.perf_counter = lambda: next(ticks)
    try:
        timed = run_scenario(scenario("timed", ["a user named ada"]), [], registry)
    finally:
        run_module.time.perf_counter = saved_clock
    if timed["duration_ms"] != 2500:
        bad.append(f"duration_ms should convert seconds to ms via *1000.0: {timed['duration_ms']}")
    return bad


def _probe_io():
    """run_feature_file / _discover_features / _load_steps / main / _parse_failure_report (§8): the
    single I/O boundary. A well-formed feature runs and passes; a parse failure is surfaced as a
    failing report, never swallowed; the CLI threads --steps modules and maps results to exit codes."""
    bad = []
    here = Path(__file__).parent
    sample = str(here / "_sample.feature")

    # _load_steps threads the registry through a real step module's register(registry) (§8.2).
    registry = _load_steps(["_sample_steps"], empty_registry())
    if len(registry["patterns"]) != 2:
        bad.append(f"_load_steps should thread register() through the module: {registry}")

    # A runnable feature with matching steps passes every scenario; the report carries its path.
    report = run_feature_file(sample, registry)
    if report["total_failed"] != 0 or report["total_passed"] < 1:
        bad.append(f"a runnable feature should pass: {report}")
    if report["source_path"] != sample:
        bad.append(f"the report should carry the source path: {report['source_path']!r}")

    with tempfile.TemporaryDirectory() as directory:
        # A parse failure is surfaced as a failing report carrying bad_feature_syntax, not raised.
        broken_path = Path(directory) / "broken.feature"
        broken_path.write_text("Feature: X\n  Given an orphan step\n", encoding="utf-8")
        broken = run_feature_file(str(broken_path), registry)
        fault = broken["scenarios"][0]["step_results"][0]["fault"]
        if broken["total_failed"] != 1 or fault["code"] != "bad_feature_syntax":
            bad.append(f"a parse failure should be a failing report carrying bad_feature_syntax: {broken}")

        # _discover_features: a directory is searched recursively; a single file is taken as-is.
        (Path(directory) / "extra.feature").write_text("Feature: A\n\n  Scenario: s\n    Given x\n", encoding="utf-8")
        found = _discover_features(directory)
        if len(found) != 2 or not all(str(path).endswith(".feature") for path in found):
            bad.append(f"_discover_features should find every .feature under a directory: {found}")
        if _discover_features(sample) != [Path(sample)]:
            bad.append(f"_discover_features on a single file should return just that file: {_discover_features(sample)}")

    # _parse_failure_report directly: one failing scenario carrying the fault, metadata set.
    pf_fault = step_fault("bad_feature_syntax", "no Feature declared")
    pf = _parse_failure_report("x.feature", pf_fault)
    if pf["total_failed"] != 1 or pf["scenarios"][0]["step_results"][0]["fault"] is not pf_fault:
        bad.append(f"_parse_failure_report should carry the fault as a single failure: {pf}")

    # main maps results to exit codes: a passing run exits 0; an all-unmatched run exits 1.
    if main(["run", sample, "--steps", "_sample_steps"]) != 0:
        bad.append("a passing run should exit 0")
    if main(["run", sample]) != 1:
        bad.append("a run with no registered steps should exit 1 (every step unmatched)")

    # main prints one summary line per feature; assert the observable output, not just the exit code,
    # so the format string and the print loop are pinned.
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main(["run", sample, "--steps", "_sample_steps"])
    if f"{sample}: 1 passed, 0 failed" not in buffer.getvalue():
        bad.append(f"main should print the per-feature summary line: {buffer.getvalue()!r}")

    # main(None) reads sys.argv (the real CLI entry); the argv slice and `import sys` are pinned here.
    saved_argv = sys.argv
    sys.argv = ["honest-gherkin", "run", sample, "--steps", "_sample_steps"]
    try:
        argv_status = main(None)
    finally:
        sys.argv = saved_argv
    if argv_status != 0:
        bad.append("main(None) should read sys.argv[1:] and exit 0 on a passing run")

    # The subcommand is required: no subcommand exits via argparse, never falls through to run.
    try:
        main([])
        bad.append("main([]) with no subcommand should exit via argparse (required=True)")
    except SystemExit:
        pass
    return bad


def run():
    probes = {
        "parse": _probe_parse(),
        "compile": _probe_compile(),
        "registry": _probe_registry(),
        "run": _probe_run(),
        "io": _probe_io(),
    }
    violations = [(name, messages) for name, messages in probes.items() if messages]
    for name, messages in violations:
        print(f"FAIL HG-probe [{name}]: {messages}")
    passed = sum(1 for messages in probes.values() if not messages)
    print(f"HG laws: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())

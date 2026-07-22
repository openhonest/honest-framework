"""honest-check conformance: the HC laws + boundary-shell coverage (the circle).

honest-check's input is unbounded source, so its behavioural circle is necessarily
example-based (the verification model: the structural rules are complete by form, but the
suite that exercises them is per-rule positive/negative examples, not an enumeration). This
harness carries the HC laws (honest-conformance-suite.md): HC-2 (determinism) and HC-4 (no
false negative on a mandatory rule — every rule flags its violation and stays silent on clean
code), plus exhaustive coverage of the I/O shells the conformance suite never touches: the
CLI, the LSP server, the output formats, config resolution, the startup hook, and inline
suppression. The shells are exercised in-process with temp files and injected streams.

The conformance directory is outside the honest-check gate, so it may read/write files, drive
argv and stdio, and feed deliberately-malformed config.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

from honest_check import HonestCheckError, check_source, startup_check
from honest_check.cli import _discover_css, _discover_files, _discover_js, _discover_templates, _find_config, _load_config, _load_manifest, _template_roots, main as cli_main, watch
from honest_check.rules import is_fixable
from honest_check.config import (
    empty_config,
    is_excluded,
    normalize_config,
    resolve_paths,
    resolve_severity,
)
from honest_check.diagnostics import diagnostic
from honest_check.formats import (
    counts,
    filter_by_rule,
    filter_by_severity,
    has_errors,
    render,
    supported_formats,
)
from honest_check.lsp import (
    _code_actions,
    _definition_location,
    _document_symbols,
    _hover_contents,
    _on_initialize,
    _publish,
    _read_message,
    _response,
    _write_message,
    dispatch,
    serve,
    to_lsp_diagnostic,
)
from honest_check.watchlists import IO_WATCH_LIST, NONDETERMINISTIC_WATCH_LIST, matches_watchlist

_CLEAN = "def add(a, b):\n    return a + b\n"
_VIOLATION = "class Widget:\n    pass\n"  # HC-P003: class declaration
# A go-to-definition fixture: make (def, line 0), V (assignment, line 2), ghost (undefined, line 4).
_DEFN_DOC = "def make():\n    return 1\nV = make()\nx = V\nz = ghost\n"
# A workspace-symbol fixture: a vocabulary, a binding, a chain, plus non-symbol assignments.
_SYMBOL_DOC = (
    "from honest_type import vocabulary, binding, chain\n"
    "Colors = vocabulary({'a': {'x'}})\n"
    "Bind = binding({'a': 's'})\n"
    "Flow = chain(f, g)\n"
    "n = 1\n"
    "m = other()\n"
    "d = mod.thing()\n"
)
_SYNTAX_ERROR = "def (:\n    pass\n"  # HC-SYN: unparseable — a startup-eligible rule


# --------------------------------------------------------------------------- formats


def _probe_formats():
    bad = []
    diags = [
        diagnostic("HC003", "error", "f.py", 1, 1, 'a class & <tag> "q"'),
        diagnostic("HC-P001", "warning", "f.py", 2, 1, "branch"),
        diagnostic("HC-P006", "info", "f.py", 3, 1, "note"),
    ]

    # Exact human output: a location+rule line plus an indented message line per diagnostic, then a summary.
    human_expected = (
        "f.py:1:1: error HC003\n"
        '  a class & <tag> "q"\n'
        "f.py:2:1: warning HC-P001\n"
        "  branch\n"
        "f.py:3:1: info HC-P006\n"
        "  note\n"
        "Found 1 error(s), 1 warning(s), 1 info(s)."
    )
    if render(diags, "human") != human_expected:
        bad.append(f"render human mismatch: {render(diags, 'human')!r}")

    # Exact GitHub-annotation output: one ::level line per diagnostic; info maps to notice.
    github_expected = (
        '::error file=f.py,line=1,col=1,title=HC003::a class & <tag> "q"\n'
        "::warning file=f.py,line=2,col=1,title=HC-P001::branch\n"
        "::notice file=f.py,line=3,col=1,title=HC-P006::note"
    )
    if render(diags, "github") != github_expected:
        bad.append(f"render github mismatch: {render(diags, 'github')!r}")

    # Exact JUnit XML: escaped message attribute and body; failures = errors + warnings.
    junit_expected = (
        '<testsuites name="honest-check" failures="2" tests="3">\n'
        '  <testsuite name="honest-check" failures="2" tests="3">\n'
        '    <testcase name="HC003:1" classname="f.py">\n'
        '      <failure message="a class &amp; &lt;tag&gt; &quot;q&quot;">f.py:1:1 error HC003</failure>\n'
        "    </testcase>\n"
        '    <testcase name="HC-P001:2" classname="f.py">\n'
        '      <failure message="branch">f.py:2:1 warning HC-P001</failure>\n'
        "    </testcase>\n"
        '    <testcase name="HC-P006:3" classname="f.py">\n'
        '      <failure message="note">f.py:3:1 info HC-P006</failure>\n'
        "    </testcase>\n"
        "  </testsuite>\n"
        "</testsuites>"
    )
    if render(diags, "junit") != junit_expected:
        bad.append(f"render junit mismatch: {render(diags, 'junit')!r}")

    # JSON: structure + values via parse, and 4-space indentation via the raw text.
    json_text = render(diags, "json")
    expected_payload = {
        "version": "0.1",
        "summary": {"errors": 1, "warnings": 1, "infos": 1},
        "diagnostics": [
            {"rule": "HC003", "severity": "error", "file": "f.py", "line": 1, "col": 1, "message": 'a class & <tag> "q"', "fixable": False},
            {"rule": "HC-P001", "severity": "warning", "file": "f.py", "line": 2, "col": 1, "message": "branch", "fixable": False},
            {"rule": "HC-P006", "severity": "info", "file": "f.py", "line": 3, "col": 1, "message": "note", "fixable": False},
        ],
    }
    if json.loads(json_text) != expected_payload:
        bad.append(f"render json structure mismatch: {json_text!r}")
    if '\n    "version": "0.1"' not in json_text:
        bad.append(f"render json should use 4-space indentation: {json_text!r}")

    # render dispatches by name; supported_formats is the sorted renderer set.
    if supported_formats() != ["github", "human", "json", "junit"]:
        bad.append(f"supported_formats should be the sorted renderer names: {supported_formats()}")

    # Defaults reached only by an off-vocabulary severity (the pure renderers accept any dict):
    # counts tallies from a zero base, the rank default (0) sits at the info floor, and the GitHub
    # level falls back to notice.
    weird = diagnostic("HCX", "weird", "f.py", 9, 9, "w")
    if counts([weird]) != {"error": 0, "warning": 0, "info": 0, "weird": 1}:
        bad.append(f"counts should tally an unseen severity from a zero base: {counts([weird])}")
    if filter_by_severity([weird], "warning") != []:
        bad.append("an unranked severity (default rank 0) sits below the warning floor")
    if filter_by_severity([weird], "info") != [weird]:
        bad.append("an unranked severity (default rank 0) meets the info floor")
    if render([weird], "github") != "::notice file=f.py,line=9,col=9,title=HCX::w":
        bad.append(f"an unmapped severity renders as the notice default: {render([weird], 'github')!r}")

    # GitHub flattens newlines in a message to single spaces.
    nl = diagnostic("HCN", "error", "f.py", 5, 5, "two\nlines")
    if render([nl], "github") != "::error file=f.py,line=5,col=5,title=HCN::two lines":
        bad.append(f"github should flatten newlines to spaces: {render([nl], 'github')!r}")

    # The empty report still summarises, and the pure predicates/filters hold.
    if render([], "human") != "Found 0 error(s), 0 warning(s), 0 info(s).":
        bad.append(f"empty human render should be just the summary: {render([], 'human')!r}")
    total = counts(diags)
    if (total["error"], total["warning"], total["info"]) != (1, 1, 1):
        bad.append(f"counts wrong: {total}")
    if len(filter_by_severity(diags, "info")) != 3 or len(filter_by_severity(diags, "error")) != 1:
        bad.append("filter_by_severity floor wrong")
    if len(filter_by_severity(diags, "bogus")) != 2:  # unknown minimum -> default warning floor
        bad.append("filter_by_severity default floor wrong")
    if len(filter_by_rule(diags, frozenset({"HC003"}), frozenset())) != 1:
        bad.append("filter_by_rule(only) wrong")
    if len(filter_by_rule(diags, frozenset(), frozenset({"HC003"}))) != 2:
        bad.append("filter_by_rule(suppress) wrong")
    if not has_errors(diags) or has_errors(diags[1:]):
        bad.append("has_errors wrong")
    return bad


# --------------------------------------------------------------------------- config


def _probe_exports():
    import honest_check

    bad = []
    expect = ["Diagnostic", "check_source", "startup_check", "HonestCheckError"]
    if sorted(getattr(honest_check, "__all__", [])) != sorted(expect):
        bad.append(f"__all__ should be exactly the public surface: {getattr(honest_check, '__all__', None)}")
    missing = [n for n in expect if not hasattr(honest_check, n)]
    if missing:
        bad.append(f"__all__ names not importable: {missing}")
    return bad


def _probe_config():
    bad = []
    full = normalize_config({"check": {"paths": ["src/"], "exclude": ["x/**"], "severity": "error"}, "rules": {"disable": ["HC003"]}})
    if full["paths"] != ["src/"] or full["severity"] != "error" or full["disable"] != ["HC003"] or full["exclude"] != ["x/**"]:
        bad.append(f"normalize_config wrong: {full}")
    if full["templates"] != "" or normalize_config({"check": {"templates": "tpl/"}})["templates"] != "tpl/":
        bad.append(f"normalize_config should read the templates directory, empty by default: {full['templates']!r}")
    # A per-rule value that is not a mapping (no .items) is not kept as rule_config; only dict configs are.
    nondict = normalize_config({"rules": {"disable": ["HC003"], "HC003": "notamapping", "HC-OR003": {"min_run": 4}}})
    if nondict["rule_config"] != {"HC-OR003": {"min_run": 4}}:
        bad.append(f"only mapping rule values are kept as rule_config: {nondict['rule_config']}")
    # "disable" is dropped from rule_config by *name*, even when its value is a mapping with .items —
    # so the exclusion is the name check, not only the has-items check.
    disable_map = normalize_config({"rules": {"disable": {"HC003": True}, "HC-OR003": {"min_run": 4}}})
    if disable_map["rule_config"] != {"HC-OR003": {"min_run": 4}}:
        bad.append(f"disable is excluded from rule_config by name even when a mapping: {disable_map['rule_config']}")
    if empty_config()["severity"] != "warning":
        bad.append("empty_config default severity wrong")
    configured = normalize_config({"rules": {"disable": ["HC003"], "HC-OR003": {"min_run": 4}}, "startup": {"on_error": "halt"}})
    if configured["rule_config"] != {"HC-OR003": {"min_run": 4}} or configured["startup_on_error"] != "halt":
        bad.append(f"normalize_config should keep per-rule config and startup on_error: {configured}")
    if empty_config()["rule_config"] != {} or empty_config()["startup_on_error"] is not None:
        bad.append("empty_config should have no rule config and no startup on_error")
    if not is_excluded("a/migrations/x.py", ["**/migrations/**"]) or is_excluded("a/x.py", ["**/migrations/**"]):
        bad.append("is_excluded wrong")
    if resolve_severity("error", "warning") != "error" or resolve_severity(None, "info") != "info" or resolve_severity(None, None) != "warning":
        bad.append("resolve_severity precedence wrong")
    if resolve_paths(["a"], ["b"]) != ["a"] or resolve_paths([], ["b"]) != ["b"] or resolve_paths([], []) != ["."]:
        bad.append("resolve_paths precedence wrong")
    return bad


# --------------------------------------------------------------------------- cli


def _run_cli(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli_main(argv)
    return code, out.getvalue(), err.getvalue()


def _probe_cli():
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "clean.py"
        clean.write_text(_CLEAN, encoding="utf-8")
        dirty = Path(tmp) / "dirty.py"
        dirty.write_text(_VIOLATION, encoding="utf-8")

        code, _, _ = _run_cli([str(clean)])
        if code != 0:
            bad.append(f"clean file should exit 0, got {code}")
        code, out, _ = _run_cli([str(dirty), "--format", "json"])
        if code != 1 or "HC" not in out:
            bad.append(f"violation should exit 1 with output, got {code} {out[:60]}")
        # A clean file in a format that emits nothing produces no output line.
        _run_cli([str(clean), "--format", "github"])
        # --no-rule suppresses a rule: dirty's only finding (HC-P003) drops, so the run passes.
        code, _, _ = _run_cli([str(dirty), "--no-rule", "HC-P003"])
        if code != 0:
            bad.append(f"--no-rule HC-P003 should suppress the only error and exit 0, got {code}")
        # --rule keeps only the named rule: asking for a different rule filters HC-P003 out.
        code, _, _ = _run_cli([str(dirty), "--rule", "HC-SYN"])
        if code != 0:
            bad.append(f"--rule HC-SYN should keep only HC-SYN, filtering out HC-P003, exit 0, got {code}")
        # Every --severity choice is accepted (not an argparse usage error).
        for sev in ("error", "warning", "info"):
            code, _, _ = _run_cli([str(dirty), "--severity", sev])
            if code == 2:
                bad.append(f"--severity {sev} should be an accepted choice, got a usage error")
        # Explicit valid config is read and normalized.
        cfg = Path(tmp) / "honest-check.toml"
        cfg.write_text('[check]\nseverity = "error"\n', encoding="utf-8")
        _run_cli([str(dirty), "--config", str(cfg)])
        # A malformed config is an exit-2 usage failure.
        bad_cfg = Path(tmp) / "bad.toml"
        bad_cfg.write_text("this is = = not toml", encoding="utf-8")
        code, _, err = _run_cli([str(dirty), "--config", str(bad_cfg)])
        if code != 2 or "cannot load config" not in err:
            bad.append(f"malformed config should exit 2 with a message, got {code} {err[:60]}")
        # A path that cannot be read is an exit-2 failure with a message.
        code, _, err = _run_cli([str(Path(tmp) / "does_not_exist.py")])
        if code != 2 or "cannot read source" not in err:
            bad.append(f"missing source file should exit 2 with a message, got {code} {err[:60]}")
        # --fix reports that nothing is auto-fixable (honest-check's rules need restructuring).
        code, _, err = _run_cli([str(dirty), "--fix"])
        if code != 1 or "auto-fixable" not in err or "restructuring" not in err:
            bad.append(f"--fix should run and report no auto-fixable corrections: {code} {err[:80]}")
        # Directory input: _discover_files expands a directory to its sorted .py files, honouring excludes.
        if _discover_files([str(tmp)], []) != sorted([clean, dirty]):
            bad.append(f"_discover_files should expand a directory to its .py files: {_discover_files([str(tmp)], [])}")
        if _discover_files([str(tmp)], ["*/dirty.py"]) != [clean]:
            bad.append("_discover_files should drop files matching an exclude glob")
        # --watch runs the check; with no trigger stream (EOF) it runs once and returns its code.
        code, _, _ = _run_cli([str(clean), "--watch"])
        if code != 0:
            bad.append(f"--watch on a clean tree should run once and exit 0, got {code}")
        # The JSON fixable field is computed (false for every structural rule), not hardcoded.
        _, out, _ = _run_cli([str(dirty), "--format", "json"])
        if '"fixable": false' not in out:
            bad.append("json output should carry a computed fixable field")

    # HC002's first-link boundary check wired through the CLI: a template directory in the config makes
    # every checked file run the boundary check against the scanned templates (spec section 4.2).
    with tempfile.TemporaryDirectory() as tmp:
        app = (
            "from honest_type import link, vocabulary, chain\n"
            "V = vocabulary({'qty': {'1'}, 'sku': {'a'}})\n"
            "@link(accepts=V, emits=V)\n"
            "def validate(x):\n    return x\n"
            "c = chain(validate)\n"
            "ROUTES = {('POST', '/api/orders'): c}\n"
        )
        Path(tmp, "app.py").write_text(app, encoding="utf-8")
        tdir = Path(tmp, "templates")
        tdir.mkdir()
        cfg = Path(tmp, "honest-check.toml")
        cfg.write_text(f'[check]\ntemplates = "{tdir}"\n', encoding="utf-8")
        orders = Path(tdir, "orders.html")
        # A template that sends only qty: the first link also needs sku, so HC002 fires (exit 1).
        orders.write_text('<form hx-post="/api/orders"><input name="qty"></form>', encoding="utf-8")
        code, out, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg), "--format", "json"])
        if code != 1 or "HC002" not in out:
            bad.append(f"a first link needing a field no template sends should fire HC002: {code} {out[:80]}")
        # Send both fields: the boundary supplies the accepts, so the run is clean (exit 0).
        orders.write_text('<form hx-post="/api/orders"><input name="qty"><input name="sku"></form>', encoding="utf-8")
        code, _, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg)])
        if code != 0:
            bad.append(f"a first link the templates fully supply should be clean, got {code}")
        # _discover_templates: a configured dir yields its .html files; no dir or a missing one yields none.
        if _discover_templates(str(tdir)) != [orders]:
            bad.append(f"_discover_templates should list the .html under the configured dir: {_discover_templates(str(tdir))}")
        if _discover_templates("") != [] or _discover_templates(str(Path(tmp, "nope"))) != []:
            bad.append("_discover_templates should be empty for no dir or a missing dir")

    # HC-REF001 wired through the CLI: a template action targeting no mounted route is a dead reference,
    # resolved against the project-wide route union (spec section 4.2; "Every reference resolves").
    with tempfile.TemporaryDirectory() as tmp:
        # The first link is a boundary link, exempt from HC002, so this test isolates HC-REF001.
        app = (
            "from honest_type import link, vocabulary, chain\n"
            "V = vocabulary({'qty': {'1'}})\n"
            "@link(accepts=V, emits=V, boundary=True)\n"
            "def validate(x):\n    return x\n"
            "c = chain(validate)\n"
            "ROUTES = {('GET', '/dashboard'): c}\n"
        )
        Path(tmp, "app.py").write_text(app, encoding="utf-8")
        tdir = Path(tmp, "templates")
        tdir.mkdir()
        cfg = Path(tmp, "honest-check.toml")
        cfg.write_text(f'[check]\ntemplates = "{tdir}"\n', encoding="utf-8")
        page = Path(tdir, "page.html")
        # A button whose hx-get targets a route nothing mounts: the dead reference fires HC-REF001.
        page.write_text('<button hx-get="/ghost">Go</button>', encoding="utf-8")
        code, out, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg), "--format", "json"])
        if code != 1 or "HC-REF001" not in out:
            bad.append(f"a template action targeting no mounted route should fire HC-REF001: {code} {out[:80]}")
        # Point it at the mounted route: the reference resolves, so the run is clean.
        page.write_text('<button hx-get="/dashboard">Go</button>', encoding="utf-8")
        code, _, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg)])
        if code != 0:
            bad.append(f"a template action targeting a mounted route should be clean, got {code}")
        # The route union is project-wide: a target mounted in a second file resolves, no false positive.
        page.write_text('<button hx-get="/elsewhere">Go</button>', encoding="utf-8")
        Path(tmp, "more.py").write_text(app.replace("/dashboard", "/elsewhere"), encoding="utf-8")
        code, _, _ = _run_cli([str(Path(tmp, "app.py")), str(Path(tmp, "more.py")), "--config", str(cfg)])
        if code != 0:
            bad.append(f"a target mounted in another checked file should resolve, got {code}")

    # HC-REF002 wired through the CLI: an include/extends target must resolve to a template in the search
    # path — the templates dir plus its sibling atoms/ and molecules/ roots (honest-components).
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "app.py").write_text("x = 1\n", encoding="utf-8")
        tdir = Path(tmp, "templates")
        tdir.mkdir()
        atoms = Path(tmp, "atoms", "button")
        atoms.mkdir(parents=True)
        atoms.joinpath("button.html").write_text("<button>x</button>", encoding="utf-8")
        Path(tdir, "base.html").write_text("<html></html>", encoding="utf-8")
        cfg = Path(tmp, "honest-check.toml")
        cfg.write_text(f'[check]\ntemplates = "{tdir}"\n', encoding="utf-8")
        page = Path(tdir, "page.html")
        # extends a real base, includes a real atom (resolved via the atoms/ root), and a missing template.
        page.write_text('{% extends "base.html" %}{% include "button/button.html" %}{% include "ghost.html" %}', encoding="utf-8")
        code, out, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg), "--format", "json"])
        if code != 1 or "HC-REF002" not in out or "ghost.html" not in out:
            bad.append(f"a dangling include target should fire HC-REF002: {code} {out[:100]}")
        # Point it at a real template: every include/extends now resolves, so the run is clean.
        page.write_text('{% extends "base.html" %}{% include "button/button.html" %}', encoding="utf-8")
        code, _, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg)])
        if code != 0:
            bad.append(f"resolvable include/extends targets should be clean, got {code}")
        # _template_roots discovers the templates dir plus the existing sibling atoms/ (molecules/ absent).
        roots = _template_roots(str(tdir))
        if roots != [tdir, Path(tmp, "atoms")]:
            bad.append(f"_template_roots should be the templates dir plus existing sibling roots: {roots}")
        if _template_roots("") != []:
            bad.append("_template_roots is empty when no templates dir is configured")

    # HC-REF003 wired through the CLI: a class a template references must resolve to a class the component
    # stylesheets define (union across the search roots).
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "app.py").write_text("x = 1\n", encoding="utf-8")
        tdir = Path(tmp, "templates")
        tdir.mkdir()
        atoms = Path(tmp, "atoms", "button")
        atoms.mkdir(parents=True)
        atoms.joinpath("button.css").write_text(".button { color: red } .button--primary {}", encoding="utf-8")
        cfg = Path(tmp, "honest-check.toml")
        cfg.write_text(f'[check]\ntemplates = "{tdir}"\n', encoding="utf-8")
        page = Path(tdir, "page.html")
        # references a defined class and a typo'd one.
        page.write_text('<button class="button buton">x</button>', encoding="utf-8")
        code, out, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg), "--format", "json"])
        if code != 1 or "HC-REF003" not in out or "buton" not in out:
            bad.append(f"a class no stylesheet defines should fire HC-REF003: {code} {out[:100]}")
        # Fix the class: every reference now resolves, so the run is clean.
        page.write_text('<button class="button button--primary">x</button>', encoding="utf-8")
        code, _, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg)])
        if code != 0:
            bad.append(f"classes the stylesheets define should be clean, got {code}")
        if _discover_css(str(Path(tmp, "atoms"))) != [atoms / "button.css"]:
            bad.append(f"_discover_css should list the .css files under a dir: {_discover_css(str(Path(tmp, 'atoms')))}")
        if _discover_css("") != []:
            bad.append("_discover_css is empty when no directory is given")
        # HC-REF003's runtime half: a class a .js module emits via classList must resolve too. The page is
        # clean; button.js emits a defined class and a typo'd one.
        atoms.joinpath("button.js").write_text('el.classList.add("button"); n.classList.add("buton");', encoding="utf-8")
        code, out, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg), "--format", "json"])
        if code != 1 or "HC-REF003" not in out or "buton" not in out:
            bad.append(f"a class a JS module emits that no stylesheet defines should fire HC-REF003: {code} {out[:100]}")
        if _discover_js(str(Path(tmp, "atoms"))) != [atoms / "button.js"]:
            bad.append(f"_discover_js should list the .js files under a dir: {_discover_js(str(Path(tmp, 'atoms')))}")
        if _discover_js("") != []:
            bad.append("_discover_js is empty when no directory is given")

    # HC-REF004 wired through the CLI: an authored hf-* value must resolve to honest-format's declared
    # vocabulary, read from the configured manifest.
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "app.py").write_text("x = 1\n", encoding="utf-8")
        tdir = Path(tmp, "templates")
        tdir.mkdir()
        manifest = Path(tmp, "manifest.json")
        manifest.write_text('{"formats": ["currency", "date"], "inputTypes": ["cents", "auto"], "options": {"hf-phone-format": ["us"]}}', encoding="utf-8")
        cfg = Path(tmp, "honest-check.toml")
        cfg.write_text(f'[check]\ntemplates = "{tdir}"\nformat_manifest = "{manifest}"\n', encoding="utf-8")
        page = Path(tdir, "page.html")
        # a typo'd format value; hf-decimals is a free value and must not fire.
        page.write_text('<span hf-format="curency" hf-decimals="2">1</span>', encoding="utf-8")
        code, out, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg), "--format", "json"])
        if code != 1 or "HC-REF004" not in out or "curency" not in out:
            bad.append(f"an hf-format value naming no member should fire HC-REF004: {code} {out[:120]}")
        # Fix the value: it now resolves against the manifest, so the run is clean.
        page.write_text('<span hf-format="currency" hf-decimals="2">1</span>', encoding="utf-8")
        code, _, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg)])
        if code != 0:
            bad.append(f"a resolvable hf-format value should be clean, got {code}")
        # _load_manifest parses the configured manifest; an absent path or missing file is None.
        if _load_manifest(str(manifest))["formats"] != ["currency", "date"]:
            bad.append("_load_manifest should parse the configured manifest")
        if _load_manifest("") is not None or _load_manifest(str(Path(tmp, "nope.json"))) is not None:
            bad.append("_load_manifest is None when no path is configured or the file is absent")
        # A malformed manifest is a boundary error: exit 2.
        manifest.write_text("{ not json", encoding="utf-8")
        code, _, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg)])
        if code != 2:
            bad.append(f"a malformed manifest should exit 2, got {code}")

    # HC-REF004 for components wired through the CLI: an authored hc-* attribute must resolve to
    # honest-components' declared behaviour vocabulary, read from the configured component manifest.
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "app.py").write_text("x = 1\n", encoding="utf-8")
        tdir = Path(tmp, "templates")
        tdir.mkdir()
        components = Path(tmp, "components.json")
        components.write_text('{"behaviors": ["switch", "accordion"], "options": {"hc-accordion-mode": ["single", "multi"]}}', encoding="utf-8")
        cfg = Path(tmp, "honest-check.toml")
        cfg.write_text(f'[check]\ntemplates = "{tdir}"\ncomponent_manifest = "{components}"\n', encoding="utf-8")
        page = Path(tdir, "page.html")
        # a typo'd behaviour name names no module and fires.
        page.write_text("<button hc-swich>x</button>", encoding="utf-8")
        code, out, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg), "--format", "json"])
        if code != 1 or "HC-REF004" not in out or "hc-swich" not in out:
            bad.append(f"a typo'd hc-* behaviour should fire HC-REF004: {code} {out[:120]}")
        # Fix the name and use a valid option: the run is clean.
        page.write_text('<button hc-switch>x</button><div hc-accordion hc-accordion-mode="single">y</div>', encoding="utf-8")
        code, _, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg)])
        if code != 0:
            bad.append(f"a resolvable hc-* attribute should be clean, got {code}")

    # HC-ST002 wired through the CLI: a client module that keeps a copy of a slot the templates declare
    # as user state is a second source of truth, and the run fails.
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "app.py").write_text("x = 1\n", encoding="utf-8")
        tdir = Path(tmp, "templates")
        tdir.mkdir()
        Path(tdir, "page.html").write_text(
            "<body><script>const appManifest = { search: { selector: '#q', read: 'value' } }</script></body>",
            encoding="utf-8")
        shadow = Path(tdir, "app.js")
        shadow.write_text("const search = 'copy'\n", encoding="utf-8")
        cfg = Path(tmp, "honest-check.toml")
        cfg.write_text(f'[check]\ntemplates = "{tdir}"\n', encoding="utf-8")
        code, out, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg), "--format", "json"])
        if code != 1 or "HC-ST002" not in out or "search" not in out:
            bad.append(f"a module-level copy of a declared user-state slot should fire HC-ST002: {code} {out[:140]}")
        # Read it fresh instead of keeping it, and the run is clean.
        shadow.write_text("const unrelated = 1\n", encoding="utf-8")
        code, _, _ = _run_cli([str(Path(tmp, "app.py")), "--config", str(cfg)])
        if code != 0:
            bad.append(f"a module that keeps no copy of user state should be clean, got {code}")

    # The watch loop re-runs once per trigger line and returns the last code at EOF.
    runs = {"n": 0}

    def _count():
        runs["n"] += 1
        return runs["n"]

    if watch(_count, io.BytesIO(b"\n\n")) != 3 or runs["n"] != 3:
        bad.append("watch should run once plus once per trigger line")
    if is_fixable("HC-NOPE"):
        bad.append("is_fixable should be false for a structural rule with no conservative fix")

    # The ancestor config search: chdir into a tree that carries honest-check.toml.
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "honest-check.toml").write_text('[check]\nseverity = "warning"\n', encoding="utf-8")
        Path(tmp, "src.py").write_text(_CLEAN, encoding="utf-8")
        saved = os.getcwd()
        os.chdir(tmp)
        try:
            found_cfg = _find_config(None)
            if found_cfg is None or not found_cfg.is_file():
                bad.append(f"ancestor search should return the real honest-check.toml file: {found_cfg}")
            _run_cli(["src.py"])
        finally:
            os.chdir(saved)
    if _load_config(None) != empty_config():
        bad.append("_load_config(None) should be the empty config")
    # --lsp routes into the server; feed it an empty stdin (EOF -> 0). serve() uses the binary
    # buffers of stdin/stdout, so the fakes must expose .buffer.
    saved_in, saved_out = sys.stdin, sys.stdout
    sys.stdin = type("_S", (), {"buffer": io.BytesIO(b"")})()
    sys.stdout = type("_S", (), {"buffer": io.BytesIO()})()
    try:
        if cli_main(["--lsp"]) != 0:
            bad.append("--lsp should return the server's exit code")
    finally:
        sys.stdin, sys.stdout = saved_in, saved_out

    # main(None) reads sys.argv[1:] — the program name dropped, the real arguments kept. With a dirty
    # first path and a clean second, both are checked, so the run fails (exit 1). argv[0:] would treat
    # the program name as a path (exit 2); argv[2:] would drop the dirty path (exit 0).
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "clean.py"
        clean.write_text(_CLEAN, encoding="utf-8")
        dirty = Path(tmp) / "dirty.py"
        dirty.write_text(_VIOLATION, encoding="utf-8")
        saved_argv = sys.argv
        # argv[0] is a name that resolves to no file or directory, so argv[0:] (keeping it as a path)
        # fails to read it and exits 2, distinct from the real argv[1:] exit 1.
        sys.argv = ["prog-does-not-exist.invalid", str(dirty), str(clean)]
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = cli_main(None)
            if code != 1:
                bad.append(f"main(None) should read sys.argv[1:] and check both paths (exit 1), got {code}")
        finally:
            sys.argv = saved_argv

        # The --watch dispatch reads the trigger stream (sys.stdin.buffer) only when --watch is given.
        # Inject a stdin buffer and check whether main consumed it: a plain run must leave it untouched.
        for flag, should_consume in (([], False), (["--watch"], True)):
            buffer = io.BytesIO(b"trigger\n")
            saved_in = sys.stdin
            sys.stdin = type("_S", (), {"buffer": buffer})()
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    cli_main([*flag, str(clean)])
            finally:
                sys.stdin = saved_in
            if (buffer.tell() > 0) != should_consume:
                bad.append(f"--watch={bool(flag)} should consume stdin={should_consume}, consumed={buffer.tell() > 0}")

    # --help renders the full help: the program name, the description, and every argument's help string.
    # COLUMNS is widened so argparse does not wrap a phrase across lines.
    saved_cols = os.environ.get("COLUMNS")
    os.environ["COLUMNS"] = "200"
    help_out = io.StringIO()
    try:
        with contextlib.redirect_stdout(help_out), contextlib.redirect_stderr(io.StringIO()):
            cli_main(["--help"])
    except SystemExit:
        pass
    finally:
        if saved_cols is None:
            os.environ.pop("COLUMNS", None)
        else:
            os.environ["COLUMNS"] = saved_cols
    help_text = help_out.getvalue()
    for phrase in (
        "usage: honest-check",  # the program name in the usage line (prog=)
        "pre-auto-generation honesty gate",
        "files or directories to check",
        "run as a Language Server over stdio",
        "path to honest-check.toml",
        "run only this rule (repeatable)",
        "suppress this rule (repeatable)",
        "apply auto-fixable corrections",
        "re-run on each trigger line from stdin",
    ):
        if phrase not in help_text:
            bad.append(f"--help should include {phrase!r}")
    return bad


# --------------------------------------------------------------------------- lsp


def _frame(obj):
    data = json.dumps(obj).encode("utf-8")
    return f"Content-Length: {len(data)}\r\n\r\n".encode("ascii") + data


def _probe_lsp():
    bad = []
    # The full stdio loop: initialize, open a violating doc, then exit.
    stream = (
        _frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        + _frame({"method": "textDocument/didOpen", "params": {"textDocument": {"uri": "f.py", "text": _VIOLATION}}})
        + _frame({"method": "exit"})
    )
    sink = io.BytesIO()
    if serve(io.BytesIO(stream), sink) != 0:
        bad.append("serve should return 0 on exit")
    if b"publishDiagnostics" not in sink.getvalue():
        bad.append("serve did not publish diagnostics for an opened document")
    # A message carrying an extra (non-Content-Length) header line exercises the header loop.
    extra = b"Content-Type: x\r\n" + _frame({"method": "exit"})
    if serve(io.BytesIO(extra), io.BytesIO()) != 0:
        bad.append("serve should skip unknown headers and still parse the message")
    # EOF immediately.
    if serve(io.BytesIO(b""), io.BytesIO()) != 0:
        bad.append("serve should return 0 on EOF")
    # A zero-length body is treated as EOF too.
    if serve(io.BytesIO(b"Content-Length: 0\r\n\r\n"), io.BytesIO()) != 0:
        bad.append("serve should return 0 on an empty body")
    # _read_message of a bare stream is None.
    if _read_message(io.BytesIO(b"")) is not None:
        bad.append("_read_message of EOF should be None")
    # Every handler routes; the document store threads through (didOpen records text, hover reads it).
    empty = {}
    dispatch(empty, "initialized", None, {})
    opened, _ = dispatch(empty, "textDocument/didOpen", None, {"textDocument": {"uri": "f.py", "text": _VIOLATION}})
    if opened.get("f.py") != _VIOLATION:
        bad.append("didOpen should record the document text in the store")
    changed, _ = dispatch(empty, "textDocument/didChange", None, {"textDocument": {"uri": "f.py"}, "contentChanges": [{"text": _CLEAN}]})
    if changed.get("f.py") != _CLEAN:
        bad.append("didChange should update the document text in the store")
    dispatch(empty, "textDocument/didChange", None, {"textDocument": {"uri": "f.py"}, "contentChanges": []})
    dispatch(empty, "textDocument/didSave", None, {})
    closed, close_msgs = dispatch(opened, "textDocument/didClose", None, {"textDocument": {"uri": "f.py"}})
    if not close_msgs or "f.py" in closed:
        bad.append("didClose should publish an empty diagnostic set and drop the document")
    if dispatch(empty, "shutdown", 9, {})[1][0]["id"] != 9:
        bad.append("shutdown should respond to its id")
    if dispatch(empty, "totally/unknown", None, {})[1] != []:
        bad.append("an unknown method should be a no-op")
    # Hover over a violating line returns the rule and message; an unflagged line returns null.
    hover_hit = dispatch(opened, "textDocument/hover", 2, {"textDocument": {"uri": "f.py"}, "position": {"line": 0, "character": 0}})[1][0]
    if "HC-P003" not in (hover_hit["result"]["contents"]["value"] if hover_hit["result"] else ""):
        bad.append(f"hover over a violation should return its rule documentation: {hover_hit}")
    hover_miss = dispatch(opened, "textDocument/hover", 3, {"textDocument": {"uri": "f.py"}, "position": {"line": 99, "character": 0}})[1][0]
    if hover_miss["result"] is not None:
        bad.append("hover over an unflagged line should return null")
    # Go-to-definition resolves an identifier to its assignment or function definition in the file.
    defn_store, _ = dispatch(empty, "textDocument/didOpen", None, {"textDocument": {"uri": "d.py", "text": _DEFN_DOC}})

    def _definition(line, char):
        return dispatch(defn_store, "textDocument/definition", 1, {"textDocument": {"uri": "d.py"}, "position": {"line": line, "character": char}})[1][0]["result"]

    if (_definition(3, 4) or {}).get("range", {}).get("start", {}).get("line") != 2:
        bad.append(f"definition of V's use should point at its assignment on line 2: {_definition(3, 4)}")
    if (_definition(2, 4) or {}).get("range", {}).get("start", {}).get("line") != 0:
        bad.append(f"definition of make's use should point at its def on line 0: {_definition(2, 4)}")
    if _definition(4, 4) is not None:
        bad.append("definition of an undefined name should be null")
    if _definition(0, 3) is not None:
        bad.append("definition at a non-identifier position should be null")
    # workspace/symbol lists the vocabulary, binding, and chain declarations across open documents.
    sym_store, _ = dispatch(empty, "textDocument/didOpen", None, {"textDocument": {"uri": "s.py", "text": _SYMBOL_DOC}})
    all_symbols = dispatch(sym_store, "workspace/symbol", 7, {"query": ""})[1][0]["result"]
    names = sorted(s["name"] for s in all_symbols)
    if names != ["Bind", "Colors", "Flow"]:
        bad.append(f"workspace/symbol should list the vocabulary, binding, and chain declarations: {names}")
    filtered = dispatch(sym_store, "workspace/symbol", 8, {"query": "col"})[1][0]["result"]
    if [s["name"] for s in filtered] != ["Colors"]:
        bad.append(f"workspace/symbol should filter by the query substring: {filtered}")
    # codeAction offers a suppression directive for each diagnostic in the requested range.
    action_in = dispatch(opened, "textDocument/codeAction", 9, {"textDocument": {"uri": "f.py"}, "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}}})[1][0]["result"]
    if len(action_in) != 1 or "HC-P003" not in action_in[0]["title"] or "honest: ignore HC-P003" not in action_in[0]["edit"]["changes"]["f.py"][0]["newText"]:
        bad.append(f"codeAction should offer a suppression directive for the violation: {action_in}")
    action_out = dispatch(opened, "textDocument/codeAction", 10, {"textDocument": {"uri": "f.py"}, "range": {"start": {"line": 5, "character": 0}, "end": {"line": 5, "character": 0}}})[1][0]["result"]
    if action_out != []:
        bad.append("codeAction outside a violation's line should offer nothing")
    lsp = to_lsp_diagnostic(diagnostic("HC003", "error", "f.py", 1, 1, "m"))
    if lsp["severity"] != 1:
        bad.append("error should map to LSP severity 1")
    return bad


_HC_P003_MESSAGE = (
    "Class 'Widget' has no declared base. Honest Code permits class definitions only as subclasses "
    "of TypedDict, Protocol, ABC, or a declared Exception. Use a TypedDict for data shapes or a pure function."
)


def _probe_lsp_exact():
    """Pin the exact JSON-RPC payloads the LSP helpers build (section 2.2). The handler tests above
    assert routing and a few fields; here every response/notification dict, every offset conversion,
    and the severity/kind maps are pinned exactly, so a swapped key, an emptied string, or an
    off-by-one in the 1-based <-> 0-based conversion is caught."""
    bad = []

    # to_lsp_diagnostic: 1-based honest-check -> 0-based LSP, end character one past the start.
    if to_lsp_diagnostic(diagnostic("HC003", "error", "f.py", 3, 5, "msg")) != {
        "range": {"start": {"line": 2, "character": 4}, "end": {"line": 2, "character": 5}},
        "severity": 1,
        "code": "HC003",
        "source": "honest-check",
        "message": "msg",
    }:
        bad.append(f"to_lsp_diagnostic exact payload wrong: {to_lsp_diagnostic(diagnostic('HC003', 'error', 'f.py', 3, 5, 'msg'))}")
    # The max(..., 0) floor: a 1-based (1, 1) clamps to (0, 0), not (-1)/(1).
    start = to_lsp_diagnostic(diagnostic("X", "warning", "u", 1, 1, "m"))["range"]["start"]
    if start != {"line": 0, "character": 0}:
        bad.append(f"to_lsp_diagnostic should clamp the 1-based origin to (0, 0): {start}")
    # The severity map, including the default for an off-vocabulary severity.
    for sev, code in (("error", 1), ("warning", 2), ("info", 3), ("bogus", 3)):
        if to_lsp_diagnostic(diagnostic("X", sev, "u", 2, 2, "m"))["severity"] != code:
            bad.append(f"to_lsp_diagnostic severity map: {sev} should be {code}")

    # _on_initialize: the full capability advertisement.
    _store, init_msgs = _on_initialize({}, 1, {})
    if init_msgs != [{
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "capabilities": {
                "textDocumentSync": 1,
                "hoverProvider": True,
                "definitionProvider": True,
                "workspaceSymbolProvider": True,
                "codeActionProvider": True,
            },
            "serverInfo": {"name": "honest-check", "version": "0.1"},
        },
    }]:
        bad.append(f"_on_initialize capabilities payload wrong: {init_msgs}")

    # _response and _publish: the JSON-RPC envelope and the publishDiagnostics notification.
    if _response(5, {"k": 1}) != {"jsonrpc": "2.0", "id": 5, "result": {"k": 1}}:
        bad.append(f"_response envelope wrong: {_response(5, {'k': 1})}")
    if _publish("u.py", "") != {
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {"uri": "u.py", "diagnostics": []},
    }:
        bad.append(f"_publish notification of a clean doc wrong: {_publish('u.py', '')}")

    # _hover_contents: markdown of the rule and message on the line, None elsewhere.
    if _hover_contents(_VIOLATION, "f.py", {"line": 0}) != {
        "kind": "markdown",
        "value": f"**HC-P003**: {_HC_P003_MESSAGE}",
    }:
        bad.append(f"_hover_contents exact payload wrong: {_hover_contents(_VIOLATION, 'f.py', {'line': 0})}")
    if _hover_contents(_VIOLATION, "f.py", {"line": 50}) is not None:
        bad.append("_hover_contents off a flagged line should be None")

    # _definition_location: the identifier at (3, 4) ('V' in 'x = V') resolves to its assignment target.
    if _definition_location(_DEFN_DOC, "d.py", {"line": 3, "character": 4}) != {
        "uri": "d.py",
        "range": {"start": {"line": 2, "character": 0}, "end": {"line": 2, "character": 1}},
    }:
        bad.append(f"_definition_location exact payload wrong: {_definition_location(_DEFN_DOC, 'd.py', {'line': 3, 'character': 4})}")
    if _definition_location(_DEFN_DOC, "d.py", {"line": 4, "character": 4}) is not None:
        bad.append("_definition_location of an undefined name should be None")
    if _definition_location(_DEFN_DOC, "d.py", {"line": 0, "character": 3}) is not None:
        bad.append("_definition_location at a non-identifier position should be None")

    # _document_symbols: each declaration with its SymbolKind (vocabulary 5, binding 8, chain 12).
    if _document_symbols(_SYMBOL_DOC, "s.py") != [
        {"name": "Colors", "kind": 5, "location": {"uri": "s.py", "range": {"start": {"line": 1, "character": 0}, "end": {"line": 1, "character": 6}}}},
        {"name": "Bind", "kind": 8, "location": {"uri": "s.py", "range": {"start": {"line": 2, "character": 0}, "end": {"line": 2, "character": 4}}}},
        {"name": "Flow", "kind": 12, "location": {"uri": "s.py", "range": {"start": {"line": 3, "character": 0}, "end": {"line": 3, "character": 4}}}},
    ]:
        bad.append(f"_document_symbols exact payload wrong: {_document_symbols(_SYMBOL_DOC, 's.py')}")

    # _code_actions: a suppression edit appended at the end of the diagnostic's line.
    if _code_actions(_VIOLATION, "f.py", {"start": {"line": 0}, "end": {"line": 0}}) != [{
        "title": "Suppress HC-P003 with a directive",
        "kind": "quickfix",
        "edit": {"changes": {"f.py": [{
            "range": {"start": {"line": 0, "character": 13}, "end": {"line": 0, "character": 13}},
            "newText": "  # honest: ignore HC-P003",
        }]}},
    }]:
        bad.append(f"_code_actions exact payload wrong: {_code_actions(_VIOLATION, 'f.py', {'start': {'line': 0}, 'end': {'line': 0}})}")
    # A range that does not cover the diagnostic line yields nothing.
    if _code_actions(_VIOLATION, "f.py", {"start": {"line": 5}, "end": {"line": 5}}) != []:
        bad.append("_code_actions outside the diagnostic line should be empty")

    # _read_message / _write_message framing round-trip.
    payload = {"jsonrpc": "2.0", "id": 7, "method": "x"}
    sink = io.BytesIO()
    _write_message(sink, payload)
    framed = sink.getvalue()
    body = json.dumps(payload).encode("utf-8")
    if framed != f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body:
        bad.append(f"_write_message framing wrong: {framed!r}")
    if _read_message(io.BytesIO(framed)) != payload:
        bad.append("_read_message should parse a framed message back to its dict")
    # A header block with no Content-Length leaves the length at its 0 default: the zero-length body
    # reads as EOF -> None (pins `content_length = 0` and the empty-body guard).
    if _read_message(io.BytesIO(b"X-Foo: bar\r\n\r\nbody")) is not None:
        bad.append("_read_message with no Content-Length header should be None")

    # _node_at uses a half-open span: a position exactly at an identifier's end_point does NOT match.
    # 'V' in 'x = V' spans (3,4)..(3,5); position (3,5) is past it, so there is no definition.
    if _definition_location(_DEFN_DOC, "d.py", {"line": 3, "character": 5}) is not None:
        bad.append("_node_at end_point is exclusive: a position at the span end should not match")

    # _document_symbols maps validate_all to SymbolKind 12 (Function), like chain.
    va_symbols = _document_symbols("W = validate_all()\n", "v.py")
    if [(s["name"], s["kind"]) for s in va_symbols] != [("W", 12)]:
        bad.append(f"_document_symbols should map validate_all to kind 12: {va_symbols}")

    # _code_actions over a wider range: a violation on a line strictly inside [start, end] is offered,
    # which pins the `end` lookup (not collapsed to start_line) and the inclusive range comparison.
    multi = "\n\nclass Widget:\n    pass\n"  # HC-P003 on line 3 (1-based) -> diagnostic_line 2
    actions = _code_actions(multi, "m.py", {"start": {"line": 0}, "end": {"line": 5}})
    if len(actions) != 1 or actions[0]["edit"]["changes"]["m.py"][0]["range"]["start"]["line"] != 2:
        bad.append(f"_code_actions should offer a fix for a diagnostic inside a wider range: {actions}")

    # dispatch routes 'initialize' to the capability advertisement (pins the handler-table key).
    routed = dispatch({}, "initialize", 1, {})[1]
    if not routed or routed[0].get("result", {}).get("capabilities", {}).get("hoverProvider") is not True:
        bad.append(f"dispatch('initialize') should route to the capabilities response: {routed}")

    # serve: 'exit' stops the loop before later messages are processed (pins the exit check); and a
    # request's id is carried back on its response (pins message.get('id')).
    exit_first = _frame({"method": "exit"}) + _frame({"method": "textDocument/didOpen", "params": {"textDocument": {"uri": "f.py", "text": _VIOLATION}}})
    sink = io.BytesIO()
    serve(io.BytesIO(exit_first), sink)
    if b"publishDiagnostics" in sink.getvalue():
        bad.append("serve should stop at 'exit' and not process the following didOpen")
    id_stream = _frame({"jsonrpc": "2.0", "id": 42, "method": "shutdown", "params": {}}) + _frame({"method": "exit"})
    sink = io.BytesIO()
    serve(io.BytesIO(id_stream), sink)
    if b'"id": 42' not in sink.getvalue():
        bad.append("serve should carry a request's id onto its response")

    # didClose: the exact clearing notification (an empty diagnostic set) and the document dropped.
    closed, close_msgs = dispatch({"f.py": _VIOLATION}, "textDocument/didClose", None, {"textDocument": {"uri": "f.py"}})
    if close_msgs != [{
        "jsonrpc": "2.0",
        "method": "textDocument/publishDiagnostics",
        "params": {"uri": "f.py", "diagnostics": []},
    }] or "f.py" in closed:
        bad.append(f"didClose exact notification wrong: {close_msgs}")

    # serve threads params through: a didOpen publishes diagnostics for the document's own uri.
    open_stream = _frame({"method": "textDocument/didOpen", "params": {"textDocument": {"uri": "x.py", "text": _VIOLATION}}}) + _frame({"method": "exit"})
    sink = io.BytesIO()
    serve(io.BytesIO(open_stream), sink)
    if b'"uri": "x.py"' not in sink.getvalue():
        bad.append("serve should publish diagnostics for the opened document's uri")

    # _hover_contents defaults a missing position line to 0 (-> honest-check line 1).
    if _hover_contents(_VIOLATION, "f.py", {}) != {"kind": "markdown", "value": f"**HC-P003**: {_HC_P003_MESSAGE}"}:
        bad.append("_hover_contents should default a missing line to 0 (honest-check line 1)")

    # _definition_location defaults missing line/character to 0: on a doc with an identifier at (0,0)
    # the empty position resolves there (line 0), not line 1.
    defn_doc = "V = make()\nx = V\n"
    loc = _definition_location(defn_doc, "u.py", {})
    if (loc or {}).get("range", {}).get("start", {}).get("line") != 0:
        bad.append(f"_definition_location should default the position to (0, 0): {loc}")

    # _code_actions defaults a missing start line to 0, so a line-0 diagnostic is still in range.
    if len(_code_actions(_VIOLATION, "f.py", {"start": {}, "end": {"line": 0}})) != 1:
        bad.append("_code_actions should default a missing start line to 0")

    # didChange uses the LAST content change (full-text sync), not the first.
    changed, _ = dispatch({}, "textDocument/didChange", None, {"textDocument": {"uri": "f.py"}, "contentChanges": [{"text": "FIRST"}, {"text": "LAST"}]})
    if changed.get("f.py") != "LAST":
        bad.append(f"didChange should apply the last content change: {changed.get('f.py')!r}")
    return bad


# --------------------------------------------------------------------------- startup


# Each startup-eligible rule (section 2.3), with a snippet that triggers it and the severity it
# emits at. A directive that empties or drops any member of _STARTUP_ELIGIBLE stops that rule
# being collected; the per-rule assertion below catches it. HC-SYN is covered by _SYNTAX_ERROR.
_STARTUP_ELIGIBLE_CASES = [
    ("error", ["HC001"], "from honest_type import chain\ndef step(x):\n    return x\nc = chain(step)\n"),
    ("error", ["HC002"], "from honest_type import vocabulary, link, chain\nA = vocabulary({'a': {'x'}})\nB = vocabulary({'b': {'y'}})\n@link(accepts=A, emits=A)\ndef first(x):\n    return x\n@link(accepts=B, emits=B)\ndef second(x):\n    return x\nc = chain(first, second)\n"),
    ("error", ["HC003"], "from honest_type import vocabulary\nV = vocabulary({'a': {'x', 'y'}, 'b': {'y', 'z'}})\n"),
    ("error", ["HC006"], "from honest_type import vocabulary, composed\nV = vocabulary({'a': {'x'}}, composed_types=[composed('combo', requires={'ghost': 1})])\n"),
    ("error", ["HC007"], "from honest_type import chain\nc = chain()\n"),
    ("info", ["HC011"], "from honest_type import vocabulary, predicate\nV = vocabulary({'a': predicate(p)})\n"),
    ("error", ["HC-SM01", "HC-SM02"], "from honest_type import state_machine, vocabulary\nm = state_machine(states=vocabulary({'s': {'open', 'closed'}}), events=vocabulary({'e': {'shut'}}), initial='open', terminal=['closed'], transitions={('bad', 'badev'): 'closed'})\n"),
    ("error", ["HC-SM05"], "from honest_type import state_machine, vocabulary\nm = state_machine(states=vocabulary({'s': {'open', 'closed'}}), events=vocabulary({'e': {'shut'}}), initial='ghost', terminal=['closed'], transitions={('open', 'shut'): 'closed'})\n"),
]


def _startup_stderr(path, **kwargs):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        startup_check([str(path)], **kwargs)
    return err.getvalue()


def _probe_startup():
    bad = []
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "clean.py"
        clean.write_text(_CLEAN, encoding="utf-8")
        dirty = Path(tmp) / "dirty.py"
        dirty.write_text(_SYNTAX_ERROR, encoding="utf-8")  # HC-SYN is startup-eligible

        startup_check([str(clean)])  # clean: returns, no handler
        if "HC" not in _startup_stderr(dirty, on_error="warn"):
            bad.append("startup_check warn should print to stderr")
        # A clean tree must not invoke the handler at all: with on_error='raise' it must return,
        # not raise (the `if not diagnostics: return` guard is load-bearing).
        try:
            startup_check([str(clean)], on_error="raise")
        except HonestCheckError:
            bad.append("startup_check on a clean tree must not invoke the error handler")
        try:
            startup_check([str(dirty)], on_error="raise")
            bad.append("startup_check raise should raise HonestCheckError")
        except HonestCheckError:
            pass
        # halt prints the report to stderr AND exits with code 1 (not 0, not 2).
        halt_err = io.StringIO()
        try:
            with contextlib.redirect_stderr(halt_err):
                startup_check([str(dirty)], on_error="halt")
            bad.append("startup_check halt should SystemExit")
        except SystemExit as exit_signal:
            if exit_signal.code != 1:
                bad.append(f"startup_check halt should exit with code 1, got {exit_signal.code}")
            if "HC" not in halt_err.getvalue():
                bad.append("startup_check halt should print the report to stderr before exiting")
        # Directory input exercises the rglob branch of _collect.
        startup_check([tmp], on_error="warn")
        # A severity that does not match the finding filters it out: HC-SYN is an error, so asking
        # for warnings yields nothing. (Pins the AND in the collect filter: an `or` would still
        # collect the eligible-but-wrong-severity finding.)
        if _startup_stderr(dirty, on_error="warn", severity="warning") != "":
            bad.append("a severity mismatch should filter the finding out, producing no output")

        # Every startup-eligible rule is actually collected at the severity it emits. Emptying or
        # dropping a member of _STARTUP_ELIGIBLE silences exactly one rule, caught here.
        rule_file = Path(tmp) / "rule.py"
        for severity, rules, source in _STARTUP_ELIGIBLE_CASES:
            rule_file.write_text(source, encoding="utf-8")
            report = _startup_stderr(rule_file, on_error="warn", severity=severity)
            for rule in rules:
                if rule not in report:
                    bad.append(f"startup_check should collect eligible rule {rule}: {report!r}")
            # The SM snippet emits two findings; the report joins them with a newline (not concatenated).
            if len(rules) > 1 and report.count("\n") < len(rules):
                bad.append(f"_format_report should join findings with newlines: {report!r}")
    return bad


# The normative watch lists (section 4.2): every entry must be trapped, so the table is pinned
# exactly. Emptying or dropping any entry changes the frozenset and is caught here.
_EXPECTED_IO_WATCH = frozenset({
    "open", "pathlib.Path.open", "pathlib.Path.read_text", "pathlib.Path.write_text",
    "pathlib.Path.read_bytes", "pathlib.Path.write_bytes", "os.open", "os.read", "os.write",
    "os.remove", "os.rename", "os.mkdir", "os.rmdir", "os.listdir", "os.walk",
    "shutil.copy", "shutil.move", "shutil.rmtree", "tempfile.*", "mmap.mmap",
    "subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_output",
    "os.system", "os.popen", "os.execvp", "os.spawn*", "os.fork",
    "socket.*", "http.client.*", "urllib.request.*", "urllib.urlopen",
    "requests.*", "httpx.*", "aiohttp.*", "urllib3.*", "smtplib.*",
    "ftplib.*", "poplib.*", "imaplib.*", "telnetlib.*", "ssl.*",
    "print", "input", "sys.stdout.write", "sys.stderr.write", "sys.stdin.read", "logging.*",
    "psycopg2.connect", "psycopg.connect", "asyncpg.connect",
    "sqlite3.connect", "aiosqlite.connect", "pymongo.MongoClient", "redis.Redis",
})
_EXPECTED_ND_WATCH = frozenset({
    "random.*", "secrets.*", "uuid.uuid1", "uuid.uuid3", "uuid.uuid4", "uuid.uuid5", "os.urandom",
    "time.time", "time.time_ns", "time.monotonic", "time.perf_counter", "time.process_time",
    "time.sleep", "datetime.datetime.now", "datetime.datetime.utcnow", "datetime.datetime.today",
    "datetime.date.today",
    "os.environ", "os.getenv", "os.getlogin", "os.getpid", "os.getppid", "os.getcwd", "os.uname",
    "os.environ.get", "getpass.getpass", "getpass.getuser", "platform.*", "sys.argv", "sys.version",
    "sys.path",
    "threading.current_thread", "threading.get_ident", "threading.active_count",
    "multiprocessing.current_process", "multiprocessing.cpu_count", "asyncio.get_event_loop",
    "asyncio.current_task", "id",
})
_EXPECTED_IO_WATCH_JS = frozenset({
    "fs.*", "fsp.*",
    "fetch", "http.request", "https.request", "navigator.sendBeacon",
    "localStorage.*", "sessionStorage.*", "indexedDB.*", "caches.*",
    "process.stdout.write", "process.stderr.write", "process.stdin.*",
    "console.log", "console.error", "console.warn", "console.info", "console.debug",
    "pg.*", "mongodb.*", "redis.*", "mysql.*", "sqlite3.*",
})
_EXPECTED_ND_WATCH_JS = frozenset({
    "Math.random", "crypto.getRandomValues", "crypto.randomUUID", "Symbol",
    "Date.now", "performance.now", "process.cwd",
})


def _probe_watchlist():
    bad = []
    io_list = IO_WATCH_LIST["python"]
    # The tables are exactly the normative set (every entry trapped, nothing dropped or emptied).
    if IO_WATCH_LIST != {"python": _EXPECTED_IO_WATCH, "javascript": _EXPECTED_IO_WATCH_JS}:
        bad.append("IO_WATCH_LIST drifted from the normative set")
    if NONDETERMINISTIC_WATCH_LIST != {"python": _EXPECTED_ND_WATCH, "javascript": _EXPECTED_ND_WATCH_JS}:
        bad.append("NONDETERMINISTIC_WATCH_LIST drifted from the normative set")

    # Matcher: the three entry forms, and the boundaries that pin the matching logic.
    if matches_watchlist("", io_list):
        bad.append("an empty call name matches nothing")
    if not matches_watchlist("os.spawnvp", io_list):  # bare-wildcard entry os.spawn*
        bad.append("os.spawnvp should match the bare-wildcard entry os.spawn*")
    if not matches_watchlist("subprocess.run", io_list):  # exact
        bad.append("subprocess.run should match exactly")
    if not matches_watchlist("requests.get", io_list):  # dotted-wildcard requests.*
        bad.append("requests.get should match the dotted-wildcard entry requests.*")
    # A dotted-wildcard also matches the bare module name (name == prefix): requests matches requests.*
    if not matches_watchlist("requests", io_list):
        bad.append("the bare module name should match its dotted-wildcard entry (name == prefix)")
    # A dotted-wildcard requires the dot: requestsX (no dot after the prefix) must NOT match requests.*
    if matches_watchlist("requestsX", io_list):
        bad.append("a dotted-wildcard must require the separating dot, not a bare prefix")
    # A bare-wildcard prefix is exact up to the '*': os.spaw (one char short of os.spawn*) must NOT match.
    if matches_watchlist("os.spaw", io_list):
        bad.append("a bare-wildcard prefix must be exact: os.spaw is short of os.spawn*")
    # An exact entry is not a prefix match: os.for (one char short of os.fork) must NOT match.
    if matches_watchlist("os.for", io_list):
        bad.append("an exact entry must not match a shorter prefix (os.for vs os.fork)")
    # An unlisted name returns the boolean False, not None (identity, to pin the final return).
    if matches_watchlist("totally.unlisted", io_list) is not False:
        bad.append("an unlisted name must return the boolean False")
    return bad


# --------------------------------------------------------------------------- suppression + determinism (HC-2)


def _probe_suppression():
    bad = []
    snippets = {
        "ignore": "class Widget:  # honest: ignore HC-P003\n    pass\n",
        "disable_block": "# honest: disable HC-P003\nclass A:\n    pass\n# honest: enable HC-P003\n",
        "disable_to_eof": "# honest: disable HC-P003\nclass A:\n    pass\n",
        "multi_rule": "# honest: disable HC-P003, HC-P001\nclass A:\n    pass\n",
        "disabled_then_outside": "# honest: disable HC-P003\n# honest: enable HC-P003\nclass A:\n    pass\n",
        "enable_without_disable": "# honest: enable HC-P003\nclass A:\n    pass\n",
        "not_a_directive": "# just a comment\nclass A:\n    pass\n",
        "unknown_verb": "# honest: frobnicate HC-P003\nclass A:\n    pass\n",
        "bare_verb": "# honest: disable\nclass A:\n    pass\n",
    }
    for label, source in snippets.items():
        diags = check_source(source, label)
        # A suppressed class violation is downgraded to info, not dropped (section 7.4).
        if label in ("ignore", "disable_block", "disable_to_eof", "multi_rule"):
            if not any(d["rule"] in ("HC-P003", "HC003") and d["severity"] == "info" for d in diags):
                bad.append(f"{label}: class violation should be downgraded to info: {[(d['rule'], d['severity']) for d in diags]}")
        else:
            if not any(d["rule"] in ("HC-P003", "HC003") and d["severity"] == "error" for d in diags):
                bad.append(f"{label}: class violation should remain an error: {[(d['rule'], d['severity']) for d in diags]}")
    return bad


def _probe_suppression_internals():
    """Pin the pure suppression functions directly (section 7): directive parsing, comment-only
    collection in line order, range building, and inclusive range membership. The end-to-end
    downgrade-to-info path is covered by _probe_suppression; this pins the internals the pipeline
    relies on so the parse/collect/membership logic is not merely exercised but proved."""
    from honest_parse import parse_python

    from honest_check.suppression import (
        _parse_directive,
        build_suppressions,
        collect_directives,
        dead_directives,
        is_suppressed,
        unexplained_directives,
    )

    bad = []

    # Valid directives return (verb, frozenset(rules), reason). Multi-rule works comma-separated,
    # comma+space, space-separated, and comma-without-space — the comma becomes a space (not deleted)
    # and the line tail is kept whole (split maxsplit keeps every rule). The reason is everything
    # after the first colon, stripped; absent means the empty string.
    valid = {
        "# honest: ignore HC-P003": ("ignore", frozenset({"HC-P003"}), ""),
        "# honest: disable HC-P003": ("disable", frozenset({"HC-P003"}), ""),
        "# honest: enable HC-P003": ("enable", frozenset({"HC-P003"}), ""),
        "# honest: disable HC-P003, HC-P001": ("disable", frozenset({"HC-P003", "HC-P001"}), ""),
        "# honest: disable HC-P003,HC-P001": ("disable", frozenset({"HC-P003", "HC-P001"}), ""),
        "# honest: disable HC-P003 HC-P001": ("disable", frozenset({"HC-P003", "HC-P001"}), ""),
        "# honest: disable HC-P003: the reason": ("disable", frozenset({"HC-P003"}), "the reason"),
        "# honest: ignore HC-P003:   spaced   ": ("ignore", frozenset({"HC-P003"}), "spaced"),
        "# honest: disable HC-P003, HC-P001: two rules, one reason": (
            "disable",
            frozenset({"HC-P003", "HC-P001"}),
            "two rules, one reason",
        ),
    }
    for text, expected in valid.items():
        got = _parse_directive(text)
        if got != expected:
            bad.append(f"_parse_directive({text!r}) -> {got!r}, want {expected!r}")

    # None for: a plain comment, a comment whose body only starts with a verb after a non-"honest:"
    # prefix (the tag offset must match exactly), a bare "honest:" with no verb, and an unknown verb.
    for text in (
        "# just a comment",
        "# xxxxxxxignore HC-P003",
        "# honest:",
        "# honest: frobnicate HC-P003",
    ):
        got = _parse_directive(text)
        if got is not None:
            bad.append(f"_parse_directive({text!r}) -> {got!r}, want None")

    # collect_directives keeps only real comment nodes: a directive inside a string literal is ignored,
    # a plain comment does not crash collection, and the kept directive carries its 1-based line and column.
    src = b'x = "# honest: disable HC-P003"\n# honest: ignore HC-P001: why\n# plain comment\n'
    collected = collect_directives(parse_python(src).root_node, src)
    if collected != [(2, 1, "ignore", frozenset({"HC-P001"}), "why")]:
        bad.append(f"collect_directives (string-literal ignored, plain kept safe): {collected}")

    # Order is load-bearing: a disable then a later enable forms a closed range; an enable *before*
    # a disable is a no-op and the disable runs to EOF. The two orderings give different ranges, so
    # the directives must be processed in line order.
    de = b"# honest: disable HC-P003\nclass A:\n    pass\n# honest: enable HC-P003\n"
    inline, ranges = build_suppressions(parse_python(de).root_node, de, 4)
    if inline != {} or ranges != {"HC-P003": [(1, 4)]}:
        bad.append(f"build_suppressions disable->enable closed range: {inline} {ranges}")
    ed = b"# honest: enable HC-P003\nclass A:\n    pass\n# honest: disable HC-P003\n"
    inline2, ranges2 = build_suppressions(parse_python(ed).root_node, ed, 4)
    if inline2 != {} or ranges2 != {"HC-P003": [(4, 4)]}:
        bad.append(f"build_suppressions enable(noop)->disable-to-EOF: {inline2} {ranges2}")

    # Directives are ordered by line, never by column. Here the no-op enable sits at a high column
    # on line 1 and the disable at column 1 on line 2: ordering by column would process the disable
    # first and pair it with the earlier enable, closing a backwards range.
    cols = b"x = 1  # honest: enable HC-P003\n# honest: disable HC-P003: reason\nclass A:\n    pass\n"
    inline_c, ranges_c = build_suppressions(parse_python(cols).root_node, cols, 4)
    if inline_c != {} or ranges_c != {"HC-P003": [(2, 4)]}:
        bad.append(f"build_suppressions must order directives by line, not column: {ranges_c}")

    # An inline ignore records the comment's own line and opens no range.
    ign = b"class A:  # honest: ignore HC-P003\n    pass\n"
    inline3, ranges3 = build_suppressions(parse_python(ign).root_node, ign, 2)
    if inline3 != {1: {"HC-P003"}} or ranges3 != {}:
        bad.append(f"build_suppressions inline ignore: {inline3} {ranges3}")

    # is_suppressed: inclusive at both range endpoints, excluded one line outside either end.
    rng = {"HC-P003": [(5, 10)]}
    for line, want in {3: False, 4: False, 5: True, 7: True, 10: True, 11: False}.items():
        got = is_suppressed("HC-P003", line, {}, rng)
        if got != want:
            bad.append(f"is_suppressed at line {line}: {got}, want {want}")
    if not is_suppressed("HC-P003", 1, {1: {"HC-P003"}}, {}):
        bad.append("is_suppressed should honour an inline ignore on the line")
    if is_suppressed("HC-P999", 7, {}, rng):
        bad.append("is_suppressed should be False for a rule with no suppressions")

    # dead_directives (HC-SUP001). An inline ignore is live only when the rule fired on its own
    # line; a disable only when the rule fired inside the range that this very directive opened.
    ignore_dir = [(3, 5, "ignore", frozenset({"HC-P003"}), "why")]
    if dead_directives(ignore_dir, {}, frozenset({("HC-P003", 3)})) != []:
        bad.append("dead_directives: a live inline ignore must not be reported")
    if dead_directives(ignore_dir, {}, frozenset({("HC-P003", 4)})) != [(3, 5, "HC-P003")]:
        bad.append("dead_directives: an ignore whose rule fired on another line is dead")
    disable_dir = [(1, 1, "disable", frozenset({"HC-P003"}), "why")]
    open_range = {"HC-P003": [(1, 9)]}
    if dead_directives(disable_dir, open_range, frozenset({("HC-P003", 4)})) != []:
        bad.append("dead_directives: a live disable must not be reported")
    if dead_directives(disable_dir, open_range, frozenset({("HC-P001", 4)})) != [(1, 1, "HC-P003")]:
        bad.append("dead_directives: a disable whose rule never fired is dead")
    if dead_directives(disable_dir, open_range, frozenset({("HC-P003", 40)})) != [(1, 1, "HC-P003")]:
        bad.append("dead_directives: a hit outside the opened range does not revive the disable")
    # Liveness is inclusive at both ends of the opened range, and excluded one line outside either end.
    for hit_line, want_dead in {0: True, 1: False, 5: False, 9: False, 10: True}.items():
        got = dead_directives(disable_dir, open_range, frozenset({("HC-P003", hit_line)}))
        if bool(got) != want_dead:
            bad.append(f"dead_directives: hit at line {hit_line} of range (1, 9) -> dead={bool(got)}")
    # A redundant second disable opens no range of its own, so it is dead even though the rule fired.
    if dead_directives(
        [(2, 1, "disable", frozenset({"HC-P003"}), "why")], open_range, frozenset({("HC-P003", 4)})
    ) != [(2, 1, "HC-P003")]:
        bad.append("dead_directives: a redundant second disable is dead")
    # enable only closes a block; it suppresses nothing and is never dead.
    if dead_directives([(9, 1, "enable", frozenset({"HC-P003"}), "")], open_range, frozenset()) != []:
        bad.append("dead_directives: enable is never dead")
    # Several rules on one directive are judged one by one, in rule order.
    two = [(1, 1, "disable", frozenset({"HC-P001", "HC-P003"}), "why")]
    if dead_directives(two, {"HC-P003": [(1, 9)]}, frozenset({("HC-P003", 4)})) != [(1, 1, "HC-P001")]:
        bad.append("dead_directives: each rule on a multi-rule directive is judged separately")

    # unexplained_directives (HC-SUP002): ignore and disable need a reason, enable does not.
    mixed = [
        (1, 1, "disable", frozenset({"HC-P003"}), ""),
        (2, 7, "ignore", frozenset({"HC-P001"}), ""),
        (3, 1, "disable", frozenset({"HC-P003"}), "explained"),
        (4, 1, "enable", frozenset({"HC-P003"}), ""),
    ]
    if unexplained_directives(mixed) != [(1, 1), (2, 7)]:
        bad.append(f"unexplained_directives: {unexplained_directives(mixed)}")

    # The suppression rules cannot be suppressed: naming one opens no range and records no ignore.
    uns = b"# honest: disable HC-SUP001, HC-P003: attempt\nclass A:\n    pass\n"
    inline4, ranges4 = build_suppressions(parse_python(uns).root_node, uns, 3)
    if inline4 != {} or ranges4 != {"HC-P003": [(1, 3)]}:
        bad.append(f"build_suppressions must drop unsuppressable rules: {inline4} {ranges4}")
    uns_ignore = b"class A:  # honest: ignore HC-SUP002: attempt\n    pass\n"
    inline5, _ = build_suppressions(parse_python(uns_ignore).root_node, uns_ignore, 2)
    if inline5 != {1: set()}:
        bad.append(f"an inline ignore of an unsuppressable rule records nothing: {inline5}")
    return bad


def _probe_determinism():
    """HC-2: the same source yields the same diagnostics on every run."""
    sources = [_CLEAN, _VIOLATION, "if x == 1:\n    y = 1\nelif x == 2:\n    y = 2\nelse:\n    y = 3\n"]
    bad = []
    for source in sources:
        if check_source(source, "d.py") != check_source(source, "d.py"):
            bad.append("check_source is not deterministic")
    return bad


def _probe_routes():
    """The route-map reader (honest-page §9): extract_routes reads a declared ROUTES mapping into a list
    of {method, path, chain}, skipping any entry whose key is not a two-string tuple or whose value is
    not a chain identifier, and any assignment that is not a ROUTES dictionary. Parsed, never run."""
    from honest_parse import parse_python

    from honest_check.declgraph import extract_routes

    bad = []
    source = (
        b"ROUTES = {\n"
        b'    ("POST", "/api/orders"): create_order_chain,\n'
        b'    ("GET", "/api/items"): fetch_items_chain,\n'
        b"}\n"
        b"OTHER = {1: 2}\n"
    )
    routes = extract_routes(parse_python(source).root_node, source)
    if routes != [
        {"method": "POST", "path": "/api/orders", "chain": "create_order_chain"},
        {"method": "GET", "path": "/api/items", "chain": "fetch_items_chain"},
    ]:
        bad.append(f"extract_routes should read the ROUTES map and ignore other assignments: {routes}")

    # Malformed entries are skipped: a splat, a one-string tuple, a non-tuple key, a non-identifier chain.
    malformed = (
        b"ROUTES = {\n"
        b"    **base_routes,\n"
        b'    ("POST",): only_one,\n'
        b'    "/api/x": bare_string_key,\n'
        b'    ("GET", "/ok"): valid_chain,\n'
        b'    ("POST", "/bad"): "not_an_identifier",\n'
        b"}\n"
    )
    only_valid = extract_routes(parse_python(malformed).root_node, malformed)
    if only_valid != [{"method": "GET", "path": "/ok", "chain": "valid_chain"}]:
        bad.append(f"extract_routes should skip splats and malformed entries: {only_valid}")

    # A ROUTES bound to a non-dictionary, and a module with no ROUTES at all, both yield no routes.
    if extract_routes(parse_python(b"ROUTES = []\n").root_node, b"ROUTES = []\n") != []:
        bad.append("a non-dictionary ROUTES yields no routes")
    if extract_routes(parse_python(b"x = 1\n").root_node, b"x = 1\n") != []:
        bad.append("a module with no ROUTES declaration yields no routes")
    return bad


def _probe_hc_st001():
    """HC-ST001 fires on every persisted-state write executor (bare and honest_persist-qualified)
    outside an I/O boundary, stays silent inside a boundary, exempts honest-persist's own boundary
    layer (by path), and skips a module-level call with no enclosing function."""
    bad = []
    for name in ("transaction", "apply", "execute", "execute_many"):
        bare = f"from honest_persist import {name}\ndef save(rows, conn):\n    {name}(rows, conn)\n"
        if "HC-ST001" not in [d["rule"] for d in check_source(bare, "app/orders.py")]:
            bad.append(f"HC-ST001 should fire on {name}() outside a boundary")
        qualified = f"import honest_persist\ndef save(rows, conn):\n    honest_persist.{name}(rows, conn)\n"
        if "HC-ST001" not in [d["rule"] for d in check_source(qualified, "app/orders.py")]:
            bad.append(f"HC-ST001 should fire on honest_persist.{name}() outside a boundary")
    at_boundary = "from honest_persist import transaction\n@boundary\ndef save(rows, conn):\n    transaction(rows, conn)\n"
    if [d for d in check_source(at_boundary, "app/orders.py") if d["rule"] == "HC-ST001"]:
        bad.append("HC-ST001 should not fire inside a boundary function")
    non_write = "def total(rows):\n    return sum(rows)\n"
    if [d for d in check_source(non_write, "app/orders.py") if d["rule"] == "HC-ST001"]:
        bad.append("HC-ST001 should not fire on a call that is not a persisted-state write")
    write = "from honest_persist import transaction\ndef save(rows, conn):\n    transaction(rows, conn)\n"
    if [d for d in check_source(write, "honest_persist/instrumented.py") if d["rule"] == "HC-ST001"]:
        bad.append("HC-ST001 must not police honest-persist's own boundary layer")
    top_level = "from honest_persist import transaction\ntransaction(rows, conn)\n"
    if [d for d in check_source(top_level, "app/x.py") if d["rule"] == "HC-ST001"]:
        bad.append("HC-ST001 should skip a module-level call with no enclosing function")
    return bad


def run():
    probes = {
        "hc_st001": _probe_hc_st001(),
        "exports": _probe_exports(),
        "routes": _probe_routes(),
        "formats": _probe_formats(),
        "config": _probe_config(),
        "cli": _probe_cli(),
        "lsp": _probe_lsp(),
        "lsp_exact": _probe_lsp_exact(),
        "startup": _probe_startup(),
        "suppression": _probe_suppression(),
        "suppression_internals": _probe_suppression_internals(),
        "watchlist": _probe_watchlist(),
        "determinism": _probe_determinism(),
    }
    violations = [(name, msgs) for name, msgs in probes.items() if msgs]
    passed = sum(1 for msgs in probes.values() if not msgs)
    for name, msgs in violations:
        print(f"FAIL HC-shell [{name}]: {msgs}")
    print(f"HC laws/shells: {passed} passed, {len(violations)} failed, {len(probes)} total")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(run())

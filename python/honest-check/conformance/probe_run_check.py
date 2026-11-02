"""run_check orchestrates the whole CLI path and returns the exit code (or, in crossing
mode, the declaration-read Fault it routes outward).

The first cases pin the exit code: a class .py fails the gate (1), a clean .py passes (0),
a crossing run over a missing .hd routes a Fault outward, and a crossing run over an
agreeing .hd exits 0.

The base-mode scenarios then pin the three whole-program passes run_check wires in and the
grammar filters that feed them. Each writes a small tree, runs run_check, and reads the
rendered report for a rule id:

  - check_references over the template, stylesheet and script files (_REFERENCE_GRAMMARS):
    a template or script class with no stylesheet fires HC-REF003; a stylesheet that defines
    the class clears it; a template include with no target fires HC-REF002. One scenario per
    reference grammar (html, jinja, css, javascript), so dropping a grammar from the filter
    moves a finding.
  - check_auth over the code files (_CODE_GRAMMARS): a Python authorizing link with no
    provider fires HC-A001.
  - check_roles over the code files grouped by nearest module .hd: a Python orphan fires
    HC-R001.

The path scenarios pin nearest_hd_path and declaration_at, which decide whether a module's
.hd is found and parsed, and so whether a declared-but-undecorated function counts as roled.
A valid .hd one directory up clears the orphan; a .hd under a directory not named honest-*
is not consulted, so the orphan stands; a malformed .hd reads as NOTHING and the orphan
stands without a crash.

Real temp trees; stdout captured so the rendered report stays quiet; cwd set to the temp
dir so no stray honest-check.toml ancestor changes the adoption level, restored in finally.
"""

import contextlib
import io
import os
import tempfile

_CASES = [
    {"source": "class Report:\n    pass\n", "expect": 1},
    {"source": "x = 1\n", "expect": 0},
]

_HANDLER_AND_ORPHAN = "@boundary\ndef handler(m):\n    return m\n\n\ndef save(m):\n    return m\n"
_MODULE_HD = (
    "module honest-foo\n"
    '  boundary_in fn handler : (m: str) -> str side_effect reads "x"\n'
    '  boundary_in fn save : (m: str) -> str side_effect reads "y"\n'
)

# Base-mode scenarios: a tree of files, and the rule id the rendered report must carry
# (present True) or must not carry (present False). Each isolates one pass and the grammar
# filter that feeds it.
_BASE_SCENARIOS = [
    {
        "name": "HC-REF002 template include target missing (html)",
        "files": {"main.html": '{% include "missing.html" %}\n'},
        "rule": "HC-REF002",
        "present": True,
    },
    {
        "name": "HC-REF002 template include target missing (jinja)",
        "files": {"main.jinja": '{% include "missing.jinja" %}\n'},
        "rule": "HC-REF002",
        "present": True,
    },
    {
        "name": "HC-REF003 script class undefined (javascript)",
        "files": {"app.js": 'element.classList.add("card");\n'},
        "rule": "HC-REF003",
        "present": True,
    },
    {
        "name": "HC-REF003 cleared by a stylesheet that defines the class (css)",
        "files": {
            "main.html": '<div class="card">x</div>\n',
            "style.css": ".card { color: red; }\n",
        },
        "rule": "HC-REF003",
        "present": False,
    },
    {
        "name": "HC-A001 authorizing link, no provider registered (python)",
        "files": {"pay.py": "@link(authorizes=True)\ndef pay(m):\n    return charge(m)\n"},
        "rule": "HC-A001",
        "present": True,
    },
    {
        "name": "HC-R001 orphan, no module declaration (python)",
        "files": {"m.py": _HANDLER_AND_ORPHAN},
        "rule": "HC-R001",
        "present": True,
    },
    # A valid honest-foo.hd one directory above declares save roled, so the orphan clears.
    {
        "name": "HC-R001 cleared by a declaration found up the ancestor walk",
        "files": {
            "honest-foo/honest-foo.hd": _MODULE_HD,
            "honest-foo/sub/m.py": _HANDLER_AND_ORPHAN,
        },
        "rule": "HC-R001",
        "present": False,
    },
    # The .hd sits under a directory not named honest-*, so nearest_hd_path never consults
    # it; save is undeclared and the orphan stands.
    {
        "name": "HC-R001 stands when the .hd dir is not named honest-*",
        "files": {
            "pkg/pkg.hd": 'module pkg\n  boundary_in fn save : (m: str) -> str side_effect reads "y"\n',
            "pkg/m.py": _HANDLER_AND_ORPHAN,
        },
        "rule": "HC-R001",
        "present": True,
    },
    # A malformed honest-foo.hd reads as NOTHING, so save is undeclared and the orphan
    # stands. declaration_at must swallow the parse fault, not pass it on as a declaration.
    {
        "name": "HC-R001 stands under a malformed module .hd, without a crash",
        "files": {
            "honest-foo/honest-foo.hd": "this is not a valid declaration @@@\n",
            "honest-foo/sub/m.py": _HANDLER_AND_ORPHAN,
        },
        "rule": "HC-R001",
        "present": True,
    },
]


def _run_tree(run_check, files):
    """Write files (relative paths) into a fresh temp dir, run run_check over that dir with
    stdout captured and cwd set inside it, and return (result, stdout, raised)."""
    start = os.getcwd()
    with tempfile.TemporaryDirectory() as directory:
        for relative, text in files.items():
            path = os.path.join(directory, relative)
            os.makedirs(os.path.dirname(path) or directory, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        buffer = io.StringIO()
        raised = None
        result = None
        try:
            os.chdir(directory)
            with contextlib.redirect_stdout(buffer):
                result = run_check([directory])
        except Exception as exc:
            raised = exc
        finally:
            os.chdir(start)
        return result, buffer.getvalue(), raised


def probe_run_check():
    try:
        from honest_check import run_check
    except ImportError as exc:
        return [f"cannot import run_check: {exc}"]

    bad = []
    start = os.getcwd()
    for case in _CASES:
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "source.py"), "w", encoding="utf-8") as fh:
                fh.write(case["source"])
            buf = io.StringIO()
            try:
                os.chdir(d)
                with contextlib.redirect_stdout(buf):
                    got = run_check([d])
            finally:
                os.chdir(start)
            try:
                code = int(got)
            except (ValueError, TypeError):
                bad.append(
                    f"run_check over {case['source']!r} -> {got!r}, "
                    f"not an exit code; expected {case['expect']}"
                )
                continue
            if code != case["expect"]:
                bad.append(
                    f"run_check over {case['source']!r} -> {code}, expected {case['expect']}"
                )

    # Crossing mode with a --declaration that names no readable file: run_check routes
    # the read Fault straight outward as its own answer, checking nothing (§HC-R002).
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "m.py"), "w", encoding="utf-8") as fh:
            fh.write("def present(x):\n    return x\n")
        buf = io.StringIO()
        try:
            os.chdir(d)
            with contextlib.redirect_stdout(buf):
                got = run_check(["--declaration", os.path.join(d, "missing.hd"), d])
        finally:
            os.chdir(start)
        if not (isinstance(got, dict) and "problem" in got):
            bad.append(
                f"run_check crossing a missing .hd -> {got!r}, expected a Fault with 'problem'"
            )

    # Crossing mode with a valid --declaration and --exports that agree with the code:
    # cross_declaration finds nothing, so the run exits 0.
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "m.py"), "w", encoding="utf-8") as fh:
            fh.write("def clean_fn(x):\n    return x\n")
        hd = os.path.join(d, "m.hd")
        with open(hd, "w", encoding="utf-8") as fh:
            fh.write("module m\n\n  fn clean_fn : (x: str) -> str\n")
        exports = os.path.join(d, "exports.py")
        with open(exports, "w", encoding="utf-8") as fh:
            fh.write('__all__ = ["clean_fn"]\n')
        buf = io.StringIO()
        try:
            os.chdir(d)
            with contextlib.redirect_stdout(buf):
                got = run_check(
                    ["--declaration", hd, "--exports", exports, "--rule", "HC-REF005", d]
                )
        finally:
            os.chdir(start)
        if int(got) != 0:
            bad.append(
                f"run_check crossing an agreeing .hd -> {got!r}, expected exit 0"
            )

    # Base mode where a honest-<name>/honest-<name>.hd governs the file, alongside a
    # non-code (.css) file the role and auth passes skip: the class still fails the gate.
    with tempfile.TemporaryDirectory() as d:
        mod = os.path.join(d, "honest-foo")
        os.mkdir(mod)
        with open(os.path.join(mod, "honest-foo.hd"), "w", encoding="utf-8") as fh:
            fh.write("module honest-foo\n\n  fn noop : (x: str) -> str\n")
        with open(os.path.join(mod, "x.py"), "w", encoding="utf-8") as fh:
            fh.write("class Report:\n    pass\n")
        with open(os.path.join(mod, "style.css"), "w", encoding="utf-8") as fh:
            fh.write(".a { color: red; }\n")
        buf = io.StringIO()
        try:
            os.chdir(d)
            with contextlib.redirect_stdout(buf):
                got = run_check([d])
        finally:
            os.chdir(start)
        out = buf.getvalue()
        if int(got) != 1:
            bad.append(f"run_check base mode under a module .hd -> {got!r}, expected exit 1")
        if "HC-P003" not in out:
            bad.append(f"run_check base mode under a module .hd is missing HC-P003; got {out!r}")

    # The base-mode passes and the grammar filters that feed them.
    for scenario in _BASE_SCENARIOS:
        result, out, raised = _run_tree(run_check, scenario["files"])
        if raised is not None:
            bad.append(f"{scenario['name']}: run_check raised {type(raised).__name__}: {raised}")
            continue
        try:
            int(result)
        except (ValueError, TypeError):
            bad.append(f"{scenario['name']}: run_check -> {result!r}, not an exit code")
            continue
        here = scenario["rule"] in out
        if scenario["present"] and not here:
            bad.append(f"{scenario['name']}: expected {scenario['rule']} in the report, got {out!r}")
        if not scenario["present"] and here:
            bad.append(
                f"{scenario['name']}: expected no {scenario['rule']} in the report, got {out!r}"
            )

    return bad

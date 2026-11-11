"""The filesystem readers and the stdout writer — the CLI path's I/O boundary.

read_source, discover_files, load_config and load_project_config are the readers; they
touch the filesystem and nothing else. write_report is the one output boundary. The pure
core (check_source) and the pure report functions never open a file or print: the world
is touched only here.
"""

import fnmatch
import json
import os
import tomllib

from honest_design import read_hd
from honest_parse import language_of

from honest_check.report import _LEVEL_ORDER

# The adoption levels section 9.4 defines, as a membership set. load_project_config resolves
# the [check] adoption value against this, so only a declared AdoptionLevel leaves the
# boundary. _LEVEL_ORDER is report's single source of the ordered levels; this mirrors its
# membership so the two never drift.
_ADOPTION_LEVELS = frozenset(_LEVEL_ORDER)


def read_source(path):
    """Pull one file's complete text from disk and return it verbatim (section 3.2).

    path is a concrete source file discover_files already kept; read_source only reads.
    """
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def discover_files(paths, exclude):
    """Walk each path and keep the recognized, non-excluded source files (section 3.2).

    A file is kept when honest-parse recognizes its extension (language_of returns ok) and
    no exclude glob matches it; a directory is walked recursively; a path of an
    unrecognized extension and a non-source file are dropped here, so every path that
    reaches read_source is a concrete, recognized source file.
    """
    def recognized(candidate):
        return "ok" in language_of(candidate)

    def excluded(candidate):
        base = os.path.basename(candidate)
        return any(
            fnmatch.fnmatch(candidate, glob) or fnmatch.fnmatch(base, glob)
            for glob in exclude
        )

    found = []
    for path in paths:
        if os.path.isfile(path):
            if recognized(path) and not excluded(path):
                found.append(path)
        elif os.path.isdir(path):
            for root, _dirs, files in os.walk(path):
                for name in sorted(files):
                    full = os.path.join(root, name)
                    if recognized(full) and not excluded(full):
                        found.append(full)
    return found


def load_config():
    """Resolve the nearest-ancestor honest-check.toml [rules] into a RuleConfig (section 3.1).

    honest-check's one configurable rule is HC-OR003, whose setting min_run has no built-in
    default: a project that sets min_run = N resolves to {"HC-OR003": {"min_run": N}}, and a
    project that sets nothing — or has no honest-check.toml — resolves to the empty map,
    because there is nothing to fill in.
    """
    def find_toml():
        directory = os.getcwd()
        while True:
            candidate = os.path.join(directory, "honest-check.toml")
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(directory)
            if parent == directory:
                return None
            directory = parent

    toml_path = find_toml()
    if toml_path is None:
        return {}
    with open(toml_path, "rb") as handle:
        data = tomllib.load(handle)
    return resolve_rule_config(data)


def resolve_rule_config(data):
    """Build the [rules] RuleConfig from a parsed honest-check.toml table (section 3.1). Pure:
    load_config does the read and hands the table here, so the config record is assembled off the
    boundary (§HC-R006). honest-check's one configurable rule is HC-OR003, whose min_run has no
    built-in default, so the config is {"HC-OR003": {"min_run": N}} when the project sets min_run
    and the empty map otherwise, because there is nothing to fill in."""
    rules = data["rules"] if "rules" in data else {}
    or003 = rules["HC-OR003"] if "HC-OR003" in rules else {}
    if "min_run" in or003:
        return {"HC-OR003": {"min_run": or003["min_run"]}}
    return {}


def load_project_config():
    """Read the nearest-ancestor honest-check.toml [check] section (section 3.1, section 9.4).

    exclude is the glob list [check] exclude declares, the empty list when unset; adoption is
    the declared AdoptionLevel, resolved to 'Declared' (the strictest) when the key is absent
    or names no level the vocabulary carries, because silence never buys leniency. A different
    slice of the same file than load_config reads: the [rules] per-rule settings live there,
    the [check] section lives here.
    """
    def find_toml():
        directory = os.getcwd()
        while True:
            candidate = os.path.join(directory, "honest-check.toml")
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(directory)
            if parent == directory:
                return None
            directory = parent

    toml_path = find_toml()
    if toml_path is None:
        return resolve_project_config({})
    with open(toml_path, "rb") as handle:
        data = tomllib.load(handle)
    return resolve_project_config(data)


def resolve_project_config(data):
    """Build the [check] ProjectConfig from a parsed honest-check.toml table (section 3.1,
    section 9.4). Pure: load_project_config does the read and hands the table here, so the record
    is built off the boundary, not in it. exclude is the glob list, the empty list when unset;
    adoption is the declared AdoptionLevel, resolved to 'Declared' (the strictest) when the key
    is absent or names no level the vocabulary carries; format_manifest is the path, the empty
    string when unset. An empty table yields the default config, which is what the reader hands
    this when no honest-check.toml exists."""
    check = data["check"] if "check" in data else {}
    adoption = check["adoption"] if "adoption" in check else "Declared"
    return {
        "exclude": check["exclude"] if "exclude" in check else [],
        "adoption": adoption if adoption in _ADOPTION_LEVELS else "Declared",
        "format_manifest": check["format_manifest"] if "format_manifest" in check else "",
    }


def read_format_manifest(path):
    """Read honest-format's emitted manifest.json from a configured path and return the
    FormatVocabulary it carries — each enumerated hf-* attribute name mapped to its closed
    list of allowed values — or NOTHING (None) when no manifest is configured or it cannot be
    read as that shape (section 9.4, §HC-REF004).

    path is the [check] format_manifest value load_project_config read. An empty path means no
    manifest is configured, so the reader answers None and stands HC-REF004 down rather than
    resolving hf-* values against an empty vocabulary — the rule runs only where an application
    declares which honest-format vocabulary its templates target. The spec states no fault for a
    configured path that is missing or does not parse, so read_format_manifest names none and
    answers None there too, the same posture read_source takes for a file unreadable after
    discovery. It reads the filesystem and does nothing else: it does not scan templates, scrape
    the runtime's dispatch tables, or check.
    """
    if not path:
        return None
    try:
        with open(path, "rb") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict):
        return None
    return manifest


def read_fault(problem, remedy):
    """Build read_declaration's Fault — the {problem, remedy} record a failed .hd read answers
    with (§HC-R002). Pure: read_declaration detects the failure at the boundary and names the two
    sentences here, so the fault record is assembled off the boundary (§HC-R006)."""
    return {"problem": problem, "remedy": remedy}


def read_declaration(hd_path):
    """Read the named .hd from disk, parse it through honest-design's read_hd, and return the
    one parsed module (a Declaration), or a Fault when the .hd is missing or does not parse
    (section 2.1, §HC-R002).

    The declaration is the gate's own ground truth, so a run that cannot read it must fail,
    never pass quietly: the Fault is honest-check's own {problem, remedy} record, a value that
    travels by return. run_check routes it outward and the door discharges it as exit code 2.
    read_declaration reads and parses and does nothing else — it does not check, and it does
    not construct the declaration shape, which is honest-design's to own.

    hd_path is the filesystem path named by --declaration; run_check calls this only when that
    value is non-empty. Its one side effect is reading the filesystem.
    """
    if not os.path.isfile(hd_path):
        return read_fault(
            f"the declaration path {hd_path!r} named by --declaration does not name a "
            "readable file.",
            "correct the --declaration path to the module's .hd.",
        )
    with open(hd_path, "r", encoding="utf-8") as handle:
        text = handle.read()
    parsed = read_hd(text)
    if "ok" not in parsed:
        return read_fault(
            f"honest-design could not parse the declaration at {hd_path!r}: "
            f"{parsed.get('err')!r}.",
            "fix the declaration so honest-design can parse it.",
        )
    modules = parsed["ok"]["modules"]
    return modules[0]


def write_report(text):
    """Print the already-rendered report to stdout and return whether the write completed.

    text is the finished report a format function produced; write_report only writes — it
    neither formats nor decides anything. It is a terminus: it calls nothing inward.
    """
    print(text)
    return True

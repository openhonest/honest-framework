"""The filesystem readers and the stdout writer — the CLI path's I/O boundary.

read_source, discover_files, load_config and load_project_config are the readers; they
touch the filesystem and nothing else. write_report is the one output boundary. The pure
core (check_source) and the pure report functions never open a file or print: the world
is touched only here.
"""

import fnmatch
import os
import tomllib

from honest_parse import language_of


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
    rules = data.get("rules", {})
    or003 = rules.get("HC-OR003", {})
    if "min_run" in or003:
        return {"HC-OR003": {"min_run": or003["min_run"]}}
    return {}


def load_project_config():
    """Read the nearest-ancestor honest-check.toml [check] section (section 3.1, section 9.4).

    exclude is the glob list [check] exclude declares, the empty list when unset; adoption is
    the declared AdoptionLevel, resolved to 'Declared' (the strictest) when the key is absent,
    because silence never buys leniency. A different slice of the same file than load_config
    reads: the [rules] per-rule settings live there, the [check] section lives here.
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
        return {"exclude": [], "adoption": "Declared"}
    with open(toml_path, "rb") as handle:
        data = tomllib.load(handle)
    check = data.get("check", {})
    return {
        "exclude": check.get("exclude", []),
        "adoption": check.get("adoption", "Declared"),
    }


def write_report(text):
    """Print the already-rendered report to stdout and return whether the write completed.

    text is the finished report a format function produced; write_report only writes — it
    neither formats nor decides anything. It is a terminus: it calls nothing inward.
    """
    print(text)
    return True

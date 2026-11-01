"""The orchestrator the door hands its paths to (honest-check.hd: check_paths, role orchestrator).

It pulls the project's resolved rule_config once with load_config at the start
of the run and applies that one map to every file: for each path it was given it
pulls that file's text with read_source and runs check_source over it under that
same rule_config, folding every file's diagnostics into one flat list in the
order the paths were given. One resolved configuration governs the whole run, so
no file is checked under different settings and the result does not depend on how
many files there are.

Each file's grammar is detected by honest-parse from the file's extension inside
check_source, so a mixed tree checks file by file with no language threaded
through here. An empty path list folds nothing and returns [].
"""

from honest_check.check_source import check_source
from honest_check.load_config import load_config
from honest_check.read_source import read_source
from honest_check.types import Diagnostic


def check_paths(paths: list[str]) -> list[Diagnostic]:
    """Read each path, check it under the one resolved config, and fold the
    findings into one flat list in path order."""
    rule_config = load_config()
    findings: list[Diagnostic] = []
    for path in paths:
        source = read_source(path)
        findings.extend(check_source(source, path, rule_config))
    return findings

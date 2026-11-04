"""The two sinks (spec section 11, section 9.5): the human report to stdout, coverage.json to disk.

Each only writes: the rendering and the measuring are the pure core's, so a door never transforms
its input (HC-R006), beyond encoding the coverage record to its JSON file form.
"""

import json


def print_report(text):
    """Write the already-rendered report text to standard output and nothing else (spec section
    11). Returns NOTHING; its one side effect is writing stdout."""
    print(text)


def write_coverage(report):
    """Write the report's CoverageReport as coverage.json in the working directory (spec sections
    11, 9.5). Returns NOTHING; its one side effect is writing the file."""
    with open("coverage.json", "w", encoding="utf-8") as handle:
        json.dump(report["coverage"], handle)

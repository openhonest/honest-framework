# scenario: load_under_test reloads identical stems from the selected source directory
# inherits: hd=python/honest-test/honest-test.hd::load_under_test -> feature=specs/features/honest-test.feature::load_under_test reloads identical stems from the selected source directory

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from honest_test import load_under_test


def probe_load_under_test_distinct_directories():
    prefix = f"_honest_load_{uuid4().hex}"
    sibling, target = f"{prefix}_a_sibling", f"{prefix}_z_target"
    original_path = sys.path
    original_entries = list(original_path)
    failures = []
    try:
        with TemporaryDirectory() as temporary:
            ambient = Path(temporary) / "ambient"
            ambient.mkdir()
            (ambient / f"{target}.py").write_text(
                "from honest_type import link\n"
                "@link()\n"
                "def selected(manifest):\n"
                "    return ('ambient', None)\n",
                encoding="utf-8",
            )
            original_path.insert(0, str(ambient))
            entries_at_load = list(original_path)
            for marker in ("first", "second"):
                directory = Path(temporary) / marker
                directory.mkdir()
                (directory / f"{target}.py").write_text(
                    "from honest_type import link\n"
                    "identity = object()\n"
                    "@link()\n"
                    "def selected(manifest):\n"
                    f"    return ({marker!r}, identity)\n",
                    encoding="utf-8",
                )
                (directory / f"{sibling}.py").write_text(
                    "from honest_type import link\n"
                    f"import {target} as peer\n"
                    "@link()\n"
                    "def sibling_view(manifest):\n"
                    "    return peer.selected(manifest)\n",
                    encoding="utf-8",
                )
                live = load_under_test(str(directory))
                links = {link.__name__: link for link in live["links"]}
                if set(links) != {"selected", "sibling_view"}:
                    failures.append(f"{marker} directory returned the wrong live links: {links!r}")
                else:
                    selected_marker, selected_identity = links["selected"]({})
                    sibling_marker, sibling_identity = links["sibling_view"]({})
                    if (selected_marker, sibling_marker) != (marker, marker):
                        failures.append(
                            f"{marker} directory produced markers {(selected_marker, sibling_marker)!r}"
                        )
                    if selected_identity is not sibling_identity:
                        failures.append(f"{marker} sibling used a second instance of the selected module")
                if sys.path is not original_path or sys.path != entries_at_load:
                    failures.append(f"{marker} load did not restore sys.path identity and contents")
                if sys.modules.get("json") is not json:
                    failures.append(f"{marker} load replaced the unrelated json binding")
                if any(stem in sys.modules for stem in (sibling, target)):
                    failures.append(f"{marker} load leaked a temporary module binding")
    finally:
        original_path[:] = original_entries
        vars(sys)["path"] = original_path
        sys.modules["json"] = json
        sys.modules.pop(sibling, None)
        sys.modules.pop(target, None)
    return failures


def run():
    failures = probe_load_under_test_distinct_directories()
    for failure in failures:
        print(f"FAIL load_under_test distinct directories: {failure}")
    return int(bool(failures))

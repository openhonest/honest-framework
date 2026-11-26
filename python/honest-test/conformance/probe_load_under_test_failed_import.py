# scenario: load_under_test restores process import state after a failed import
# inherits: hd=python/honest-test/honest-test.hd::load_under_test -> feature=specs/features/honest-test.feature::load_under_test restores process import state after a failed import

import importlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from honest_test import load_under_test


def probe_load_under_test_failed_import():
    stem = f"_honest_load_{uuid4().hex}"
    original_path = sys.path
    original_entries = list(original_path)
    failures = []
    try:
        with TemporaryDirectory() as temporary:
            cached_dir = Path(temporary) / "cached"
            selected_dir = Path(temporary) / "selected"
            cached_dir.mkdir()
            selected_dir.mkdir()
            (cached_dir / f"{stem}.py").write_text("origin = 'cached'\n", encoding="utf-8")
            (selected_dir / f"{stem}.py").write_text(
                "raise RuntimeError('selected module failed during import')\n", encoding="utf-8"
            )
            sys.path.insert(0, str(cached_dir))
            try:
                cached = importlib.import_module(stem)
            finally:
                sys.path.pop(0)

            try:
                load_under_test(str(selected_dir))
            except RuntimeError as error:
                if str(error) != "selected module failed during import":
                    failures.append(f"expected the selected module's import error, got {error!r}")
            else:
                failures.append("the selected file's import error never propagated")
            if sys.modules.get(stem) is not cached:
                failures.append("the original same-stem module binding was lost or replaced")
            if sys.modules.get("json") is not json:
                failures.append("the unrelated json module binding was lost or replaced")
            if sys.path is not original_path or sys.path != original_entries:
                failures.append("the failed load did not restore sys.path identity and contents")
    finally:
        original_path[:] = original_entries
        vars(sys)["path"] = original_path
        sys.modules["json"] = json
        sys.modules.pop(stem, None)
    return failures


def run():
    failures = probe_load_under_test_failed_import()
    for failure in failures:
        print(f"FAIL load_under_test failed import: {failure}")
    return int(bool(failures))

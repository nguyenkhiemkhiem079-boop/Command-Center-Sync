"""Protected test-suite entrypoint executed against an isolated candidate overlay."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
import types
import unittest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overlay", required=True)
    parser.add_argument("--test-files-json", required=True)
    args = parser.parse_args()
    overlay = Path(args.overlay).resolve(strict=True)
    tests_root = (overlay / "tests").resolve(strict=True)
    files = json.loads(Path(args.test_files_json).read_text(encoding="utf-8"))
    actual = sorted(p.relative_to(overlay).as_posix() for p in tests_root.glob("test_*.py"))
    if sorted(files) != actual:
        raise SystemExit("TRUSTED_TEST_FILE_SET_MISMATCH")
    if (overlay / "tests" / "__init__.py").is_file() is False:
        raise SystemExit("TRUSTED_TEST_PACKAGE_MISSING")

    # Keep Python/installed dependencies ahead of candidate paths. Load each
    # trusted test module by its exact protected filename instead of discovery,
    # which prepends the candidate root and could shadow the stdlib.
    sys.path.append(str(overlay))
    package = types.ModuleType("tests")
    package.__path__ = [str(tests_root)]
    package.__package__ = "tests"
    sys.modules["tests"] = package
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for relative in sorted(files):
        module_name = "tests." + Path(relative).stem
        module = importlib.import_module(module_name)
        suite.addTests(loader.loadTestsFromModule(module))
    if suite.countTestCases() == 0:
        raise SystemExit("TRUSTED_TEST_SUITE_EMPTY")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

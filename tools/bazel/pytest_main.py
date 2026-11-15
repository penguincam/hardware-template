"""Bazel entry point that runs pytest over paths given as arguments.

Used by the pytest_test macro in defs.bzl. Paths are workspace-relative and
resolved inside the test's runfiles tree. Exit code is pytest's.
"""

import os
import sys

import pytest

if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    args = ["-q", "-p", "no:cacheprovider", "--import-mode=importlib"] + sys.argv[1:]
    sys.exit(pytest.main(args))

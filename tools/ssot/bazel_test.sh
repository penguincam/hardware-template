#!/usr/bin/env bash
# Bazel entry for //:ssot_test: run tools/ssot/test.sh from the runfiles tree
# (sh_test copies its src to the target name, so test.sh's own relative
# lib.sh lookup needs the real path). Needs the Nix devShell tools on PATH.
set -euo pipefail
exec "${TEST_SRCDIR:?}/_main/tools/ssot/test.sh" "$@"

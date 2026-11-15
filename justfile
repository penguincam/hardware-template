# The justfile is the only command entrypoint. Each area owns one module under just/.
set shell := ["bash", "-euo", "pipefail", "-c"]

import 'just/ssot.just'
import 'just/build.just'
import 'just/fab.just'
import 'just/sheet.just'
import 'just/hooks.just'
import 'just/template.just'

bazel := env_var_or_default("BAZEL", "bazelisk")

default:
    @just --list --unsorted

# Verify the local toolchain and repo invariants.
doctor:
    #!/usr/bin/env bash
    set -uo pipefail
    fail=0
    for t in dhall dhall-to-json dhall-to-yaml bazelisk just uv jq yq; do
      if command -v "$t" >/dev/null; then printf '  ok   %s\n' "$t"; else printf '  MISS %s\n' "$t"; fail=1; fi
    done
    # Same search order as tools/bazel/orca_profiles.find_orca (slice_check macro).
    orca="${ORCA_SLICER:-}"
    [[ -n "$orca" ]] || orca="$(command -v orca-slicer || command -v OrcaSlicer || true)"
    app="/Applications/OrcaSlicer.app/Contents/MacOS/OrcaSlicer"
    [[ -n "$orca" ]] || { [[ -x "$app" ]] && orca="$app"; }
    if [[ -n "$orca" ]]; then echo "  ok   orca-slicer ($orca; slice_check runs once a profile is in third_party/slicer_profiles)"
    else echo "  info orca-slicer absent (slice checks skip; Linux devShell or app install)"; fi
    [[ "$(git config core.hooksPath || true)" == ".githooks" ]] && echo "  ok   githooks installed" || { echo "  MISS githooks (run: just hooks-install)"; fail=1; }
    exit $fail

# Static gates: SSOT freshness, mod manifests, sheet order packages, buildifier.
check: ssot-check metadata-check sheet-verify
    {{bazel}} run //:buildifier.check

# Full local CI.
ci: check test-tools test

# Generate CHANGELOG.md from conventional commits.
changelog:
    git-cliff -o CHANGELOG.md

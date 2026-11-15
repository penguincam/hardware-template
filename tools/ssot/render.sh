#!/usr/bin/env bash
# Render every SSOT output from ssot/ and mods/*/*/{mod,params}.dhall.
# Usage: tools/ssot/render.sh            (from anywhere; writes in the repo)
# A private overlay at ssot/.agents/ (absent from the public tree) may add its own
# outputs through ssot/.agents/render.sh, run last with lib.sh already sourced.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SSOT_ROOT"

ssot_need dhall dhall-to-json dhall-to-yaml jq
ssot_import_gate

# 1. Constants and materials as JSON for scripts and Bazel macros (bed_fit,
# laser_export, dxf_lint, features.py read ssot/generated/*.json; Python cannot
# import Dhall).
dhall-to-json --file ssot/constants/package.dhall | ssot_write "$SSOT_ROOT/ssot/generated/constants.json"
dhall-to-json --file ssot/materials/package.dhall | ssot_write "$SSOT_ROOT/ssot/generated/materials.json"

# 2. Mods: .metadata.yml, params.json, params.csv
while IFS= read -r d; do
  [[ -n "$d" ]] || continue
  rel="${d#"$SSOT_ROOT"/}"
  if [[ -f "$d/mod.dhall" ]]; then
    { echo "$SSOT_HEADER_YAML Source: $rel/mod.dhall"
      # --quoted: dhall-to-yaml 1.7.12 leaves "a demo: b" as a plain scalar, which is not valid
      # YAML (mapping values are not allowed here); quoting every string keeps any text safe.
      dhall-to-yaml --quoted <<<"./ssot/render/metadata_yml.dhall (./$rel/mod.dhall : ./ssot/types/Mod.dhall)"
    } | ssot_write "$d/.metadata.yml"
  fi
  if [[ -f "$d/params.dhall" ]]; then
    # Type gate: params.dhall must be a flat record of Double.
    dhall type <<<"(./ssot/render/params.dhall).rows (toMap ./$rel/params.dhall)" >/dev/null
    dhall-to-json --file "$d/params.dhall" | ssot_write "$d/params.json"
    ssot_params_csv "$rel/params.dhall" <"$d/params.json" | ssot_write "$d/params.csv"
  fi
done < <(ssot_mod_dirs)

# 3. Optional private overlay.
if [[ -f "$SSOT_OVERLAY/render.sh" ]]; then
  # shellcheck source=/dev/null
  . "$SSOT_OVERLAY/render.sh"
fi

echo "ssot: render complete"

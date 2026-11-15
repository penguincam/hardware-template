#!/usr/bin/env bash
# Type-check every SSOT entry point, vendor profile and mod (dhall 1.42.3).
set -euo pipefail
# shellcheck source-path=SCRIPTDIR source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SSOT_ROOT"
ssot_need dhall

n=0
check() { dhall type <<<"$1" >/dev/null || { echo "ssot-type: FAILED: $1" >&2; exit 1; }; n=$((n + 1)); }

check ./ssot/package.dhall
for f in ssot/materials/*.dhall; do
  case "$f" in */package.dhall) continue ;; esac
  check "./$f : ./ssot/types/Material.dhall"
done
# Every laser vendor (built-in and repo-local) is a LaserVendor; the shop constructor yields one.
check "toMap ./ssot/constants/laser_vendors.dhall : List { mapKey : Text, mapValue : ./ssot/types/LaserVendor.dhall }"
check "./ssot/constants/laser_vendors/shop.dhall { slug = \"t\", name = \"t\", bed_mm = { x = 1.0, y = 1.0 }, kerf_mm = 0.1, source = \"t\" } : ./ssot/types/LaserVendor.dhall"
while IFS= read -r d; do
  [[ -n "$d" ]] || continue
  rel="${d#"$SSOT_ROOT"/}"
  [[ -f "$d/mod.dhall" ]] && check "./$rel/mod.dhall : ./ssot/types/Mod.dhall"
  [[ -f "$d/params.dhall" ]] && check "(./ssot/render/params.dhall).rows (toMap ./$rel/params.dhall)"
  [[ -f "$d/sheet_order.dhall" ]] && check "./$rel/sheet_order.dhall : (./ssot/types/SheetOrder.dhall).Type"
done < <(ssot_mod_dirs)
if [[ -f "$SSOT_OVERLAY/type.sh" ]]; then
  bash "$SSOT_OVERLAY/type.sh" "$SSOT_ROOT"
fi
echo "ssot-type: ok ($n expressions)"

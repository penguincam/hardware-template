# just/sheet.just: sheet-part quote packages (laser_sheet DXF, sheet_order.dhall).
# Nothing here orders, uploads or logs in.

sheet_py := "uv run --quiet --python-preference only-system --python 3.12 --with ezdxf python"

# Build MOD's sheet order package (order/) from its sheet_order.dhall; fails and writes nothing on any rule.
sheet-quote mod:
    {{sheet_py}} tools/laser/sheet_quote.py {{mod}}

# Check every mod's committed order package against its sheet_order.dhall and DXF (no writes).
sheet-verify:
    #!/usr/bin/env bash
    set -euo pipefail
    n=0
    for spec in mods/*/*/sheet_order.dhall; do
      [[ -f "$spec" ]] || continue
      m="$(dirname "$spec")"; n=$((n + 1))
      {{sheet_py}} tools/laser/sheet_quote.py "$m" --verify | jq -c '{mod, ok, errors, stale}'
    done
    echo "sheet-verify: $n order package(s) current"

#!/usr/bin/env bash
# Advisory format lint; never rewrites tracked files and always exits 0.
# `dhall format` drops comments in some positions (inside let bindings), so
# each file is formatted in a transient copy and classified:
#   safe   formatting differs and every `--` comment survives: run `dhall format FILE`
#   unsafe formatting would drop comments: reformat by hand or leave as is
set -uo pipefail
# shellcheck source-path=SCRIPTDIR source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SSOT_ROOT" || exit 0
ssot_need dhall || exit 0
tmp="$(mktemp -d "${TMPDIR:-/tmp}/ssot-fmt.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
safe=0
unsafe=0
while IFS= read -r f; do
  dhall format --check "$f" >/dev/null 2>&1 && continue
  mkdir -p "$tmp/$(dirname "$f")"
  cp "$f" "$tmp/$f"
  dhall format "$tmp/$f" >/dev/null 2>&1 || continue
  if [[ "$(grep -c -- '--' "$f")" == "$(grep -c -- '--' "$tmp/$f")" ]]; then
    echo "ssot-fmt: safe   $f (dhall format keeps its comments)"
    safe=$((safe + 1))
  else
    echo "ssot-fmt: unsafe $f (dhall format would drop comments; leave or fix by hand)"
    unsafe=$((unsafe + 1))
  fi
done < <(find ssot tools/ssot/fixtures -name '*.dhall' -type f | sort)
echo "ssot-fmt: $safe safe, $unsafe unsafe (advisory)"
exit 0

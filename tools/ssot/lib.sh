# shellcheck shell=bash
# Shared helpers for tools/ssot/*.sh. Source after `set -euo pipefail`.

SSOT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC2034 # used by render.sh
SSOT_HEADER_YAML="# GENERATED from ssot/ by just ssot-render; do not hand-edit."
# Optional private overlay: a contributor's fork may place extra Dhall sources and
# render steps here (see docs/ARCHITECTURE.md, "Private overlay"). The public tree
# never contains it, and every step below works without it.
# shellcheck disable=SC2034 # used by render.sh, check.sh and type.sh
SSOT_OVERLAY="$SSOT_ROOT/ssot/.agents"

ssot_need() {
  local t missing=0
  for t in "$@"; do
    if ! command -v "$t" >/dev/null 2>&1; then
      printf 'ssot: missing tool %s (run inside: nix develop -c ...)\n' "$t" >&2
      missing=1
    fi
  done
  return "$missing"
}

# Write stdin to $1 only when the content changed (keeps mtimes stable).
ssot_write() {
  local dest="$1" tmp
  mkdir -p "$(dirname "$dest")"
  tmp="$(mktemp "${dest}.XXXXXX")"
  cat >"$tmp"
  chmod 0644 "$tmp"
  if [[ -f "$dest" ]] && cmp -s "$tmp" "$dest"; then
    rm -f "$tmp"
  else
    mv "$tmp" "$dest"
    printf 'ssot: wrote %s\n' "${dest#"$SSOT_ROOT"/}"
  fi
}

# Remote (http/https) and env: imports are forbidden in ssot/ and mods/.
# Pass 1 is a lexical scan: drop `--` comments and double-quoted strings,
# then look for an import-shaped token. Pass 2 asks dhall for the resolved
# import graph of each entry point.
# Print import-shaped remote/env tokens in one Dhall file (lexical pass).
ssot_scan_imports() {
  # env:"QUOTED" is checked before strings are dropped (it is a string token).
  sed -E -e 's/--.*$//' "$1" | grep -nE '(^|[^A-Za-z0-9_])env:"' || true
  sed -E -e 's/--.*$//' -e 's/"([^"\\]|\\.)*"//g' "$1" |
    grep -nE '(https?://|(^|[^A-Za-z0-9_])env:[A-Za-z_])' || true
}

ssot_import_gate() {
  local bad=0 f hits
  while IFS= read -r f; do
    hits="$(ssot_scan_imports "$f")"
    if [[ -n "$hits" ]]; then
      printf 'ssot: remote or env import in %s:\n%s\n' "${f#"$SSOT_ROOT"/}" "$hits" >&2
      bad=1
    fi
  done < <(find "$SSOT_ROOT/ssot" "$SSOT_ROOT/mods" "$SSOT_ROOT/tools/ssot" -name '*.dhall' -type f 2>/dev/null | sort)
  [[ "$bad" -eq 0 ]] || return 1
  local entries=(ssot/package.dhall) d
  [[ -f "$SSOT_OVERLAY/package.dhall" ]] && entries+=(ssot/.agents/package.dhall)
  # Mods are entry points too: render imports them directly.
  while IFS= read -r d; do
    [[ -n "$d" ]] || continue
    d="${d#"$SSOT_ROOT"/}"
    [[ -f "$SSOT_ROOT/$d/mod.dhall" ]] && entries+=("$d/mod.dhall")
    [[ -f "$SSOT_ROOT/$d/params.dhall" ]] && entries+=("$d/params.dhall")
    [[ -f "$SSOT_ROOT/$d/sheet_order.dhall" ]] && entries+=("$d/sheet_order.dhall")
  done < <(ssot_mod_dirs)
  for f in "${entries[@]}"; do
    hits="$( (cd "$SSOT_ROOT" && dhall resolve --transitive-dependencies --file "$f") |
      grep -E '^(https?://|env:)' || true)"
    if [[ -n "$hits" ]]; then
      printf 'ssot: %s resolves non-local imports:\n%s\n' "$f" "$hits" >&2
      bad=1
    fi
  done
  return "$bad"
}

# Mod directories: mods/<creator>/<mod>/ holding mod.dhall or params.dhall.
ssot_mod_dirs() {
  find "$SSOT_ROOT/mods" -mindepth 3 -maxdepth 3 -type f \( -name mod.dhall -o -name params.dhall \) 2>/dev/null |
    sed 's#/[^/]*$##' | sort -u
}

# Every generated path, repo-relative, for check.sh. A private overlay adds its
# own outputs through ssot/.agents/paths.sh (one path per line).
ssot_generated_paths() {
  local d
  printf '%s\n' ssot/generated/constants.json ssot/generated/materials.json
  while IFS= read -r d; do
    [[ -n "$d" ]] || continue
    d="${d#"$SSOT_ROOT"/}"
    [[ -f "$SSOT_ROOT/$d/mod.dhall" ]] && printf '%s/.metadata.yml\n' "$d"
    [[ -f "$SSOT_ROOT/$d/params.dhall" ]] && printf '%s/params.json\n%s/params.csv\n' "$d" "$d"
  done < <(ssot_mod_dirs)
  if [[ -f "$SSOT_OVERLAY/paths.sh" ]]; then
    bash "$SSOT_OVERLAY/paths.sh" "$SSOT_ROOT"
  fi
  return 0
}

# params.json on stdin -> params.csv on stdout, in Fusion's own userParameters
# layout (Name,Unit,Expression,Value,Comments,Favorite) so a CAD tool's
# parameter import can read it. Units come from the field-name suffix; an
# unsuffixed field is an error.
ssot_params_csv() {
  local comment="$1"
  jq -r --arg c "$comment" '
    def unit: if test("_mm$") then "mm"
      elif test("_cm$") then "cm"
      elif test("_in$") then "in"
      elif test("_deg$") then "deg"
      elif test("_mpa$") then "MPa"
      elif test("_n$") then "N"
      elif test("_g$") then "g"
      elif test("_count$") or test("_flag$") then ""
      else error("param \(.) needs a unit suffix (_mm _cm _in _deg _mpa _n _g _count _flag)") end;
    (["Name","Unit","Expression","Value","Comments","Favorite"] | @csv),
    (to_entries[] | (.key | unit) as $u
      | [.key, $u, (if $u == "" then (.value | tostring) else "\(.value) \($u)" end),
         (.value | tostring), $c, "FALSE"] | @csv)'
}

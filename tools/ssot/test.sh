#!/usr/bin/env bash
# Renderer tests: render the fixtures in tools/ssot/fixtures/ into a
# transient directory and assert on the parsed output.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SSOT_ROOT"
ssot_need dhall dhall-to-json dhall-to-yaml jq yq

t="$(mktemp -d "${TMPDIR:-/tmp}/ssot-test.XXXXXX")"
trap 'rm -rf "$t"' EXIT
fail=0
pass=0
ok() { pass=$((pass + 1)); }
no() { printf 'FAIL: %s\n' "$1" >&2; fail=1; }
chk() { local m="$1"; shift; if "$@"; then ok; else no "$m"; fi; }
eq() { if [[ "$2" == "$3" ]]; then ok; else no "$1: expected [$3] got [$2]"; fi; }
fx=./tools/ssot/fixtures

# .metadata.yml
dhall-to-yaml --quoted <<<"./ssot/render/metadata_yml.dhall $fx/mod.dhall" >"$t/meta.yml"
eq "mod process" "$(yq '.process | join(",")' "$t/meta.yml")" "fdm,laser"
eq "mod issue omitted" "$(yq 'has("issue")' "$t/meta.yml")" "false"
eq "mod empty list kept" "$(yq '.dxf | length' "$t/meta.yml")" "0"
# A description with ": " must stay one valid YAML string (dhall-to-yaml plain-scalar bug).
dhall-to-yaml --quoted <<<"./ssot/render/metadata_yml.dhall (($fx/mod.dhall) // { description = \"demo: a sheet-only mod\" })" >"$t/meta2.yml"
eq "mod description with colon" "$(yq '.description' "$t/meta2.yml")" "demo: a sheet-only mod"
eq "mod version stays a number" "$(yq '.mod_version | tag' "$t/meta2.yml")" "!!int"

# params.json / params.csv
chk "params type gate" dhall type <<<"(./ssot/render/params.dhall).rows (toMap $fx/params.dhall)" >/dev/null
if dhall type <<<"(./ssot/render/params.dhall).rows (toMap { a_mm = 1.0, b = \"x\" })" >/dev/null 2>&1; then
  no "params gate accepted a Text field"
else ok; fi
dhall-to-json --file "$fx/params.dhall" >"$t/params.json"
eq "params json" "$(jq -c . "$t/params.json")" '{"clamp_n":500,"draft_deg":1.5,"insert_count":4,"wall_mm":3.2}'
ssot_params_csv "fx/params.dhall" <"$t/params.json" >"$t/params.csv"
eq "csv header" "$(head -1 "$t/params.csv")" '"Name","Unit","Expression","Value","Comments","Favorite"'
chk "csv mm row" grep -qx '"wall_mm","mm","3.2 mm","3.2","fx/params.dhall","FALSE"' "$t/params.csv"
chk "csv deg row" grep -qx '"draft_deg","deg","1.5 deg","1.5","fx/params.dhall","FALSE"' "$t/params.csv"
chk "csv N row" grep -qx '"clamp_n","N","500 N","500","fx/params.dhall","FALSE"' "$t/params.csv"
chk "csv unitless row" grep -qx '"insert_count","","4","4","fx/params.dhall","FALSE"' "$t/params.csv"
if ssot_params_csv x <<<'{"wall": 3}' >/dev/null 2>&1; then
  no "csv accepted an unsuffixed param"
else ok; fi

# Import gate: lexical scan
printf 'let P = https://prelude.dhall-lang.org/v23.0.0/package.dhall in P\n' >"$t/remote.dhall"
printf 'let H = env:HOME as Text in H\n' >"$t/env.dhall"
printf -- '-- see https://example.com\n{ url = "https://example.com", e = "env:HOME" }\n' >"$t/clean.dhall"
chk "gate missed remote import" test -n "$(ssot_scan_imports "$t/remote.dhall")"
chk "gate missed env import" test -n "$(ssot_scan_imports "$t/env.dhall")"
printf 'let U = env:"USER" as Text in U\n' >"$t/envq.dhall"
chk "gate missed quoted env import" test -n "$(ssot_scan_imports "$t/envq.dhall")"
chk "gate flagged strings or comments" test -z "$(ssot_scan_imports "$t/clean.dhall")"

# The real constants render and carry the example vendor and printers.
dhall-to-json --file ssot/constants/package.dhall >"$t/constants.json"
eq "constants vendor" "$(jq -r '.laser_vendors | keys | join(",")' "$t/constants.json")" "example_service"
eq "constants printers" "$(jq -r '[.printers | to_entries[] | select(.value | type == "object") | .key] | join(",")' "$t/constants.json")" "example_large,example_small"

echo "ssot-test: $pass passed"
exit "$fail"

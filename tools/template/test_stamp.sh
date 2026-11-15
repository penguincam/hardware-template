#!/usr/bin/env bash
# Test tools/template/stamp.sh: stamp the committed HEAD into a temporary directory and
# check the renames, the dropped example, the origin note and the refusals.
# Run from a checkout with at least one commit: just stamp-test.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/stamp-test.XXXXXX")"
trap 'rm -rf "$work"' EXIT
pass=0
fail=0
ok() { pass=$((pass + 1)); printf 'ok   %s\n' "$1"; }
no() { fail=$((fail + 1)); printf 'FAIL %s\n' "$1"; }
chk() { local m="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$m"; else no "$m"; fi; }
not() { ! "$@"; }

PATH="$work/nodhall:$PATH" bash "$here/stamp.sh" cam-box --dest "$work/cam-box" >"$work/out" 2>&1 || { cat "$work/out"; no "stamp ran"; }
d="$work/cam-box"
chk "repo renamed in just/hooks.just" grep -qx 'repo := "cam-box"' "$d/just/hooks.just"
chk "owner defaults to penguincam" grep -qx 'org := "penguincam"' "$d/just/hooks.just"
chk "module renamed" grep -q 'name = "cam_box"' "$d/MODULE.bazel"
chk "README title renamed" grep -qx '# cam-box' "$d/README.md"
chk "example mod dropped" not test -e "$d/mods/example"
chk "mods directory kept" test -f "$d/mods/.gitattributes"
chk "origin note written" grep -qF "intended visibility \`private\`" "$d/TEMPLATE_ORIGIN.md"
chk "git initialised on main" test "$(git -C "$d" symbolic-ref --short HEAD)" = main
chk "hooks path set" test "$(git -C "$d" config core.hooksPath)" = .githooks
chk "no commit made" not git -C "$d" rev-parse -q --verify HEAD
chk "no agent file exported" not test -e "$d/AGENTS.md"

bash "$here/stamp.sh" other --owner someone --visibility public --keep-example --dest "$work/other" >/dev/null 2>&1
chk "owner flag applied" grep -qx 'org := "someone"' "$work/other/just/hooks.just"
chk "visibility recorded" grep -qF "intended visibility \`public\`" "$work/other/TEMPLATE_ORIGIN.md"
chk "example kept on request" test -f "$work/other/mods/example/sealed_box/mod.dhall"

chk "bad name refused" not bash "$here/stamp.sh" Bad_Name --dest "$work/x"
chk "bad visibility refused" not bash "$here/stamp.sh" ok-name --visibility internal --dest "$work/y"
chk "existing destination refused" not bash "$here/stamp.sh" cam-box --dest "$d"

printf '\nstamp-test: %s passed, %s failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]

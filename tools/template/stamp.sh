#!/usr/bin/env bash
# Stamp a new hardware repository from this template.
#
#   tools/template/stamp.sh NAME [--owner OWNER] [--visibility private|public]
#                                [--dest DIR] [--keep-example] [--gh]
#
#   NAME          new repository name, lowercase [a-z0-9-]
#   --owner       GitHub owner (default: penguincam)
#   --visibility  intended visibility (default: private)
#   --dest        target directory (default: ../NAME next to this checkout)
#   --keep-example  keep mods/example/sealed_box (default: drop it)
#   --gh          also create the GitHub repository, always private first
#
# Exports the committed HEAD (git archive, so no untracked or ignored file leaks),
# renames the project, writes TEMPLATE_ORIGIN.md, renders the SSOT when dhall is on
# PATH, and runs git init on main. It makes no commit and never
# pushes: review the tree, then make the first signed commit yourself.
# A public repository cannot be taken back, so --gh creates it private even with
# --visibility public, and prints the command that makes it public after review.
set -euo pipefail

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

name="" dest="" owner="penguincam" visibility="private" keep_example=0 use_gh=0
while (($#)); do
  case "$1" in
    --owner) owner="${2:?--owner needs a value}"; shift 2 ;;
    --visibility) visibility="${2:?--visibility needs a value}"; shift 2 ;;
    --dest) dest="${2:?--dest needs a value}"; shift 2 ;;
    --keep-example) keep_example=1; shift ;;
    --gh) use_gh=1; shift ;;
    -h | --help) usage 0 ;;
    -*) echo "stamp: unknown flag: $1" >&2; usage 2 ;;
    *) [[ -z "$name" ]] || usage 2; name="$1"; shift ;;
  esac
done
[[ -n "$name" ]] || usage 2
[[ "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "stamp: name must be lowercase [a-z0-9-]: $name" >&2; exit 2; }
[[ "$owner" =~ ^[A-Za-z0-9][A-Za-z0-9-]*$ ]] || { echo "stamp: bad owner: $owner" >&2; exit 2; }
case "$visibility" in
  private | public) ;;
  *) echo "stamp: --visibility must be private or public: $visibility" >&2; exit 2 ;;
esac

src="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
dest="${dest:-$(dirname "$src")/$name}"
module="${name//-/_}"
[[ ! -e "$dest" ]] || { echo "stamp: refusing: $dest already exists" >&2; exit 1; }
rev="$(git -C "$src" rev-parse HEAD)"

echo "template : $src @ ${rev:0:12}"
echo "new repo : $dest ($owner/$name, $visibility)"

mkdir -p "$dest"
git -C "$src" archive --format=tar HEAD | tar -x -C "$dest"

# Identity lines only. Each edit is checked, so a template change that moves a line
# fails here instead of leaving the old name behind.
rename() {
  local file="$1" expr="$2" want="$3"
  sed -i.bak -e "$expr" "$dest/$file"
  rm -f "$dest/$file.bak"
  grep -qF -- "$want" "$dest/$file" || { echo "stamp: failed to rename $file" >&2; exit 1; }
}
rename just/hooks.just "s/^repo := \"hardware-template\"$/repo := \"$name\"/" "repo := \"$name\""
rename just/hooks.just "s/^org := \"penguincam\"$/org := \"$owner\"/" "org := \"$owner\""
rename MODULE.bazel "s/name = \"hardware_template\"/name = \"$module\"/" "name = \"$module\""
rename README.md "1s/^# hardware-template$/# $name/" "# $name"
rename README.md "s#penguincam/hardware-template#$owner/$name#g; s#hardware-template-contrib#$name-contrib#g" "$owner/$name"
rename docs/LICENSING.md "s#https://github.com/penguincam/hardware-template#https://github.com/$owner/$name#" "https://github.com/$owner/$name"
# Bazel rebuilds the lockfile for the new module name on its first run.
rm -f "$dest/MODULE.bazel.lock"

if ((keep_example == 0)); then
  rm -rf "$dest/mods/example"
  rmdir "$dest/mods" 2>/dev/null || true
  mkdir -p "$dest/mods"
  [[ -e "$dest/mods/.gitattributes" ]] || git -C "$src" show HEAD:mods/.gitattributes >"$dest/mods/.gitattributes"
fi

cat >"$dest/TEMPLATE_ORIGIN.md" <<ORIGIN
# Template origin

Stamped from the hardware template at commit \`$rev\` on $(date -u +%Y-%m-%d).
Owner \`$owner\`, intended visibility \`$visibility\`.

To take later template changes, compare this repository with a newer template tag
and copy the changed tool files by hand on a feature branch, then run \`just ssot-render\`
and \`just check\`.
ORIGIN

cd "$dest"
if command -v dhall >/dev/null && command -v dhall-to-json >/dev/null && command -v dhall-to-yaml >/dev/null; then
  tools/ssot/render.sh >/dev/null || echo "stamp: warn: ssot-render failed; run just ssot-render in the devShell" >&2
else
  echo "stamp: warn: dhall not on PATH; run just ssot-render in the devShell before the first commit" >&2
fi

git init -q -b main
git config core.hooksPath .githooks

if ((use_gh)); then
  gh repo create "$owner/$name" --private --description "Hardware repository stamped from the hardware template"
  git remote add upstream "https://github.com/$owner/$name.git"
  git remote set-url --push upstream DISABLED
  echo "stamp: created $owner/$name as private; upstream added with push DISABLED; nothing pushed"
  if [[ "$visibility" == public ]]; then
    echo "stamp: after the owner has reviewed the first push, make it public with:"
    echo "  gh repo edit $owner/$name --visibility public --accept-visibility-change-consequences"
  fi
fi

echo "stamp: done. Next, in $dest:"
echo "  just doctor && just hooks-install"
echo "  edit ssot/constants/printers.dhall and ssot/constants/laser_vendors/ for your printers and vendor"
echo "  git add -A && git commit -S -m \"chore: stamp $name from the hardware template\""
echo "  git switch -c dev"

#!/usr/bin/env bash
# Freshness gate: re-render, then fail if any generated file differs from git
# or is untracked. Also warns on em dashes in generated output.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR source=lib.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
cd "$SSOT_ROOT"

"$SSOT_ROOT/tools/ssot/type.sh"

paths=()
while IFS= read -r p; do paths+=("$p"); done < <(ssot_generated_paths)

# Refuse to render over unstaged edits to generated files: a hand edit would
# be silently overwritten and the check would then pass. Stage a fresh render
# (just ssot-render && git add) or move the edit into the Dhall source.
if ! git diff --quiet -- "${paths[@]}"; then
  git diff --stat -- "${paths[@]}" >&2
  echo "ssot-check: unstaged changes to generated files (hand edit or unstaged render)." >&2
  echo "ssot-check: move hand edits into ssot/*.dhall; for a fresh render: just ssot-render && git add the files above" >&2
  exit 1
fi

"$SSOT_ROOT/tools/ssot/render.sh" >/dev/null

paths=()
while IFS= read -r p; do paths+=("$p"); done < <(ssot_generated_paths)

status=0
if [[ -f "$SSOT_OVERLAY/check.sh" ]]; then
  bash "$SSOT_OVERLAY/check.sh" "$SSOT_ROOT" || status=1
fi
if ! git diff --exit-code --stat -- "${paths[@]}"; then
  echo "ssot-check: generated files are stale; run: just ssot-render, then commit" >&2
  status=1
fi
untracked="$(git ls-files --others --exclude-standard -- "${paths[@]}")"
if [[ -n "$untracked" ]]; then
  printf 'ssot-check: untracked generated files (git add them):\n%s\n' "$untracked" >&2
  status=1
fi

em="$(printf '\342\200\224')"
if grep -lF "$em" -- "${paths[@]}" 2>/dev/null; then
  echo "ssot-check: warning: em dash in generated output above; fix the Dhall source" >&2
fi

[[ "$status" -eq 0 ]] && echo "ssot-check: ok (${#paths[@]} generated paths fresh)"
exit "$status"

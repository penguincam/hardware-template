# just/ssot.just: the Dhall source of truth under ssot/ and mods/. Run inside the Nix
# devShell (direnv, or prefix with `nix develop -c`).

# Render constants, materials and every mod's .metadata.yml, params.json and params.csv.
ssot-render:
    tools/ssot/render.sh

# Type-check, re-render, and fail if any generated file is stale or untracked.
ssot-check:
    tools/ssot/check.sh

# Type-check every SSOT entry point, vendor profile and mod (dhall 1.42.3).
ssot-type:
    tools/ssot/type.sh

# Advisory format lint; never rewrites (dhall format drops comments).
ssot-fmt:
    tools/ssot/fmt-lint.sh

# Renderer tests against tools/ssot/fixtures/.
ssot-test:
    tools/ssot/test.sh

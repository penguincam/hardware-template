# Licensing

This repository carries two licences. Each path falls under exactly one.

| Licence | Text | Covers |
|---|---|---|
| CERN-OHL-W-2.0 | `LICENSE-CERN-OHL-W-2.0.txt` | Designs and documentation: everything under `mods/`, `ssot/constants/`, `ssot/materials/` and `docs/`, `README.md`, and the files rendered from them (`ssot/generated/`, each mod's `.metadata.yml`, `params.json` and `params.csv`, and its STEP, STL, 3MF and DXF exports) |
| GPL-3.0-or-later | `LICENSE` | Tool code: everything else, including `tools/`, `ssot/types/`, `ssot/render/`, `.githooks/`, `tests/`, `just/`, `justfile`, the Bazel files and `flake.nix` |

The tool code comes from an earlier private template that its copyright holder licensed under GPL-3.0-or-later. It keeps that licence. The designs and documentation in this repository are offered under CERN-OHL-W-2.0 by their copyright holder.

## What CERN-OHL-W-2.0 asks of you

CERN-OHL-W-2.0 is a weakly reciprocal hardware licence. In short, and the licence text governs:

- You may use, study, modify, make and distribute the design and products made from it.
- If you distribute a modified design or a product made from it, you make the source of the covered parts available under the same licence.
- A product that only uses an unmodified covered part as one component of a larger design does not bring the rest of that design under the licence.
- Keep the licence notice and mark products with the Source Location, the place where the design source can be found.

Source Location for this repository: <https://github.com/penguincam/hardware-template>

## Third-party files

The template ships no third-party design files. A repository stamped from it adds a third-party file only when its licence allows redistribution, and records it in `third_party/README.md`. A vendor CAD download with no stated licence stays out of the repository: keep a fetch step with its URL and sha256 instead.

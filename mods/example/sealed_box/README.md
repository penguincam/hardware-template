# Sealed box with lid

A small parametric box for a newcomer to build and change. It shows the repo flow end to end: Dhall parameters, a build123d module, Bazel exports and checks.

| Part | Builder | Material | Prints |
|---|---|---|---|
| `sealed_box` | `build` | ASA | opening up |
| `sealed_box_lid` | `build_lid` | ASA | flat |
| `sealed_box_gasket` | `build_gasket` | TPU 95A | flat, then pressed into the groove |

The body has four corner pillars for M3 heat-set inserts, a gasket groove in the rim and a teardrop hole for a PG9 cable gland in the front wall. The lid screws sit outside the gasket ring, so no screw hole crosses the seal.

## Build

```sh
just ssot-render                              # params.dhall -> params.json, params.csv
just export-print mods/example/sealed_box     # STEP, STL and 3MF into CAD/, STLs/, 3MF/
bazelisk test //mods/example/sealed_box:all   # check rules, ray measurements, bed fit, metadata
```

Change a size in `params.dhall`, render, and build again. `check()` in `CAD/sealed_box.py` names every rule a change breaks.

## Status

Nothing in this mod has been printed. The gasket, the gland hole and the insert bores are catalogue or design values. Print a coupon of each before trusting them. Nothing here is proven for outdoor, waterproof or solar use.

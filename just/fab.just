# just/fab.just: fabrication outputs for one mod. MOD is a mod directory, for example
# mods/example/sealed_box. Run inside the Nix devShell (direnv, or prefix with `nix develop -c`).

fab_py := "uv run --quiet --python-preference only-system --python 3.12 --with-requirements tools/python/requirements.in python"

# Build a mod and copy STEP/STL/3MF into CAD/, STLs/, 3MF/ (Voron names), then mesh-check them.
export-print mod printer="example_large":
    python3 tools/bazel/materialize.py {{mod}} --kind print --bazel {{bazel}}
    python3 tools/print/mesh_check.py --printer {{printer}} $(ls {{mod}}/STLs/*.stl {{mod}}/3MF/*.3mf 2>/dev/null)

# Examples: just export-laser MOD example_service AL-2.3; a shop profile: MOD my_shop ""; no vendor: MOD "" "" 400x300.
# Build a mod's laser_sheet targets, copy DXF into DXF/, then lint each file.
export-laser mod vendor="" sku="" bed="":
    python3 tools/bazel/materialize.py {{mod}} --kind laser --bazel {{bazel}}
    for f in {{mod}}/DXF/*.dxf; do {{fab_py}} tools/laser/dxf_lint.py "$f" {{ if bed == "" { "" } else { "--bed " + bed } }} {{ if vendor == "" { "" } else { "--vendor " + vendor } }} {{ if sku == "" { "" } else { "--sku " + sku } }} | jq -c '{file, ok, extents, vendor, sku, errors}'; done

# Build a mod and copy only STEP into CAD/ (interchange, CAD import).
export-step mod:
    python3 tools/bazel/materialize.py {{mod}} --kind step --bazel {{bazel}}

# Check print exports: just mesh-check --printer example_small mods/example/sealed_box/STLs/*.stl
[positional-arguments]
mesh-check *args:
    @python3 tools/print/mesh_check.py "$@"

# Run the mod's slice_check tests (skip with a reason when no OrcaSlicer CLI is present).
slice mod:
    {{bazel}} test --test_tag_filters=slice --test_output=all //{{mod}}:all

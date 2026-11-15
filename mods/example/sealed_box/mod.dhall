-- Example mod: a small sealed box with a lid, a cable gland hole and a gasket groove.
-- Renders to .metadata.yml. After `just export-print mods/example/sealed_box`, list the new
-- STEP, STL and 3MF files below and run `just ssot-render`.
let T = ../../../ssot/types/package.dhall

in    { title = "Sealed box with lid"
      , creator = "example"
      , slug = "sealed_box"
      , description =
          "A parametric printed box with a screwed lid, a PG9 cable gland hole and a TPU gasket in a rim groove. A starting point, not a tested enclosure."
      , mod_version = 1
      , process = [ T.Process.Fdm ]
      , materials = [ "ASA", "TPU95A" ]
      , printers = [ "example_small", "example_large" ]
      , issue = None Text
      , cad = [ "CAD/sealed_box.py" ]
      , stls = [] : List Text
      , threemf = [] : List Text
      , dxf = [] : List Text
      , images = [] : List Text
      , docs = [] : List Text
      }
    : T.Mod

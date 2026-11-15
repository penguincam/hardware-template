-- Test fixture for render/metadata_yml.dhall (tools/ssot/test.sh).
let T = ../../../ssot/types/package.dhall

in    { title = "Fixture coupon"
      , creator = "fixture"
      , slug = "coupon"
      , description = "Fit coupon used only by the renderer tests."
      , mod_version = 1
      , process = [ T.Process.Fdm, T.Process.Laser ]
      , materials = [ "PETG" ]
      , printers = [ "example_large", "example_small" ]
      , issue = None Text
      , cad = [ "CAD/coupon.py", "CAD/coupon.step" ]
      , stls = [ "STLs/coupon.stl" ]
      , threemf = [] : List Text
      , dxf = [] : List Text
      , images = [] : List Text
      , docs = [] : List Text
      }
    : T.Mod

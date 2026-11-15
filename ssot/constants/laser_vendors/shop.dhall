-- Constructor for a shop laser profile (kind "shop"). The template ships no shop record: lasers are
-- shop specific. A new repo builds its own in ssot/constants/laser_vendors_local.dhall:
--
--   let shop = ./laser_vendors/shop.dhall
--   in  { my_shop =
--           shop
--             { slug = "my_shop"
--             , name = "Shop CO2 laser"
--             , bed_mm = { x = 600.0, y = 400.0 }
--             , kerf_mm = 0.15
--             , source = "bed: measured on the machine; kerf: kerf coupon, see the mod docs/"
--             }
--       }
--
-- bed_mm is the usable cut area (not the nominal bed); kerf_mm comes from a kerf coupon
-- for the stock you cut most. Per-stock kerf: override skus with `// { skus = [ ... ] }` using
-- LaserSku rows whose kerf_mm is Some <measured>. Shop profiles compensate kerf in CAD
-- (kerf_in_cad = True) and allow SCORE and ENGRAVE layers.
let T = ../../types/package.dhall

in  \(shop : { slug : Text, name : Text, bed_mm : T.SizeMm, kerf_mm : Double, source : Text }) ->
        { slug = shop.slug
        , name = shop.name
        , kind = "shop"
        , processes = [ "laser_co2" ]
        , formats = [ "DXF", "SVG" ]
        , units = [ "mm" ]
        , kerf_in_cad = True
        , kerf_mm = shop.kerf_mm
        , layers = [ "CUT", "SCORE", "ENGRAVE" ]
        , text_allowed = True
        , one_part_per_file = False
        , islands_allowed = True
        , min_part_mm = { x = 0.0, y = 0.0 }
        , max_part_mm = shop.bed_mm
        , min_hole_factor_t = 0.0
        , warn_hole_factor_t = 0.0
        , warn_edge_factor_t = 0.0
        , inside_corner_r_mm = 0.0
        , finish_windows =
            [] : List { process : Text, min_mm : T.SizeMm, max_mm : T.SizeMm }
        , tap_drills = [] : List { thread : Text, drill_mm : Double }
        , finish_min_hole_mm = 0.0
        , hang_hole_mm = 0.0
        , tap_min_t_mm = 0.0
        , countersink_min_t_mm = 0.0
        , skus = [] : List T.LaserSku
        , source = shop.source
        }
      : T.LaserVendor
